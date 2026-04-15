import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from config import (
    API_KEY, MODEL_LOW, MODEL_HIGH, MAX_TOKENS,
    FREQUENCY_THRESHOLD, ROLE_THRESHOLD,
    WORKFLOWS_PER_CALL, ITERATIONS_PER_ROLE, ROLES,
)
from utils import clean_json_response
from agents.scope_agents import ScopeAgent, ScopeAgentOutput, ScopeWorkflow
from agents.canonicalizer_agents import CanonicalizerAgent, CanonicalizerOutput
from agents.translator_agents import TranslatorAgent, TranslatorOutput
from agents.auditor_agents import AuditorAgent, AuditorOutput
from agents.pm_agents import PMAgent, PMOutput
from agents.spec_writer_agents import SpecWriterAgent

console = Console()

STATE_DIR = Path("state")
MANIFEST_PATH = Path("manifest/vireo_manifest.json")
OUTPUT_DIR = Path("output")
FREQUENCY_LOG_PATH = STATE_DIR / "frequency_log.json"
DEFER_QUEUE_PATH = STATE_DIR / "defer_queue.json"


def load_json(path: Path, default=None):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default if default is not None else {}


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def update_frequency_log(
    log: dict,
    gap_primitives: list[str],
    contributing_roles: set[str],
    canonical_label: str,
) -> dict:
    now = datetime.now().isoformat()
    for prim in gap_primitives:
        if prim not in log:
            log[prim] = {
                "count": 0,
                "roles": [],
                "canonical_labels": [],
                "first_seen": now,
                "last_seen": now,
            }
        entry = log[prim]
        entry["count"] += 1
        entry["roles"] = list(set(entry["roles"]) | contributing_roles)
        if canonical_label not in entry["canonical_labels"]:
            entry["canonical_labels"].append(canonical_label)
        entry["last_seen"] = now
    return log


def gaps_above_threshold(log: dict) -> list[dict]:
    result = []
    for prim, data in log.items():
        if data["count"] >= FREQUENCY_THRESHOLD and len(data["roles"]) >= ROLE_THRESHOLD:
            result.append({
                "gap_primitive": prim,
                "count": data["count"],
                "roles": data["roles"],
                "canonical_labels": data["canonical_labels"],
            })
    return result


def already_deferred(primitive: str, defer_queue: list[dict], log: dict) -> bool:
    """Check if a primitive is deferred and its frequency hasn't increased."""
    for item in defer_queue:
        if item["primitive"] == primitive:
            current_count = log.get(primitive, {}).get("count", 0)
            if current_count <= item.get("frequency_at_deferral", 0):
                return True
    return False


def main():
    console.print(Panel("VIREO SCOPE LOOP — SESSION START", style="bold green"))

    # ------------------------------------------------------------------
    # Load state and manifest
    # ------------------------------------------------------------------
    manifest = load_json(MANIFEST_PATH)
    if not manifest:
        console.print("[bold red]ERROR: manifest/vireo_manifest.json not found or empty.[/bold red]")
        console.print("Run the manifest generation prompt in the Vireo repo first.")
        return

    compositions = manifest.get("compositions", [])
    frequency_log = load_json(FREQUENCY_LOG_PATH, default={})
    defer_queue_data = load_json(DEFER_QUEUE_PATH, default={"deferred": []})
    defer_queue = defer_queue_data.get("deferred", [])

    # ------------------------------------------------------------------
    # Instantiate agents
    # ------------------------------------------------------------------
    console.print("Instantiating agents...")
    canonicalizer = CanonicalizerAgent(model=MODEL_LOW)
    translator = TranslatorAgent(model=MODEL_LOW)
    auditor = AuditorAgent(model=MODEL_HIGH)
    pm = PMAgent(model=MODEL_HIGH)
    spec_writer = SpecWriterAgent(model=MODEL_LOW)
    console.print("[green]...OK![/green]")

    # ==================================================================
    # PHASE 1: Scope Generation
    # ==================================================================
    console.print(Panel("PHASE 1: Scope Generation", style="bold cyan"))

    all_workflows: list[ScopeWorkflow] = []

    for role, weight in ROLES:
        console.print(f"\n[bold]Role: {role}[/bold] (weight {weight})")
        scope = ScopeAgent(model=MODEL_LOW, role=role)
        previously_generated: list[str] = []

        for i in range(ITERATIONS_PER_ROLE):
            console.print(f"  Iteration {i + 1}/{ITERATIONS_PER_ROLE}...")
            user_prompt = scope.build_user_prompt(
                count=WORKFLOWS_PER_CALL,
                previously_generated=previously_generated,
            )
            try:
                resp = scope.ask(user_prompt)
                parsed = ScopeAgentOutput.model_validate(
                    json.loads(clean_json_response(resp))
                )
                all_workflows.extend(parsed.workflows)
                previously_generated.extend(w.task_title for w in parsed.workflows)
                console.print(f"    [green]{len(parsed.workflows)} workflows generated[/green]")
            except (json.JSONDecodeError, Exception) as e:
                console.print(f"    [red]Error: {e}[/red]")
                continue

    console.print(f"\n[bold]Total workflows generated: {len(all_workflows)}[/bold]")

    if not all_workflows:
        console.print("[bold red]No workflows generated. Exiting.[/bold red]")
        return

    # ==================================================================
    # PHASE 2: Canonicalization
    # ==================================================================
    console.print(Panel("PHASE 2: Canonicalization", style="bold cyan"))

    canonical_input = [w.model_dump() for w in all_workflows]
    canonical_prompt = canonicalizer.build_user_prompt(canonical_input)

    try:
        canonical_resp = canonicalizer.ask(canonical_prompt)
        canonical_result = CanonicalizerOutput.model_validate(
            json.loads(clean_json_response(canonical_resp))
        )
        console.print(f"[green]{len(canonical_result.clusters)} clusters identified[/green]")
    except (json.JSONDecodeError, Exception) as e:
        console.print(f"[bold red]Canonicalization failed: {e}[/bold red]")
        return

    # ==================================================================
    # PHASE 3: Translation
    # ==================================================================
    console.print(Panel("PHASE 3: Translation", style="bold cyan"))

    translator_prompt = translator.build_user_prompt(
        clusters=[c.model_dump() for c in canonical_result.clusters],
        workflows=canonical_input,
    )

    try:
        translator_resp = translator.ask(translator_prompt)
        translator_result = TranslatorOutput.model_validate(
            json.loads(clean_json_response(translator_resp))
        )
        console.print(f"[green]{len(translator_result.results)} clusters translated[/green]")
    except (json.JSONDecodeError, Exception) as e:
        console.print(f"[bold red]Translation failed: {e}[/bold red]")
        return

    # ==================================================================
    # PHASE 4: Audit
    # ==================================================================
    console.print(Panel("PHASE 4: Audit", style="bold cyan"))

    auditor_prompt = auditor.build_user_prompt(
        translator_output=[r.model_dump() for r in translator_result.results],
        manifest=manifest,
    )

    try:
        auditor_resp = auditor.ask(auditor_prompt)
        auditor_result = AuditorOutput.model_validate(
            json.loads(clean_json_response(auditor_resp))
        )
    except (json.JSONDecodeError, Exception) as e:
        console.print(f"[bold red]Audit failed: {e}[/bold red]")
        return

    passed = sum(1 for r in auditor_result.results if r.passed)
    failed = sum(1 for r in auditor_result.results if not r.passed)
    console.print(f"[green]Passed: {passed}[/green]  [red]Failed: {failed}[/red]")

    # ==================================================================
    # PHASE 5: Frequency Tracking
    # ==================================================================
    console.print(Panel("PHASE 5: Frequency Tracking", style="bold cyan"))

    for cluster_audit in auditor_result.results:
        if cluster_audit.passed:
            continue

        # Find the canonical cluster to get source_indices
        matching_cluster = next(
            (c for c in canonical_result.clusters
             if c.canonical_label == cluster_audit.canonical_label),
            None,
        )
        if not matching_cluster:
            continue

        contributing_roles = {
            all_workflows[i].role
            for i in matching_cluster.source_indices
            if i < len(all_workflows)
        }

        frequency_log = update_frequency_log(
            frequency_log,
            cluster_audit.gap_primitives,
            contributing_roles,
            cluster_audit.canonical_label,
        )

    save_json(FREQUENCY_LOG_PATH, frequency_log)

    # Print frequency summary
    for prim, data in sorted(frequency_log.items(), key=lambda x: x[1]["count"], reverse=True):
        status = "[green]ABOVE THRESHOLD[/green]" if (
            data["count"] >= FREQUENCY_THRESHOLD and len(data["roles"]) >= ROLE_THRESHOLD
        ) else "[dim]below threshold[/dim]"
        console.print(f"  {prim}: count={data['count']}, roles={len(data['roles'])} {status}")

    # ==================================================================
    # PHASE 6: PM Gate
    # ==================================================================
    console.print(Panel("PHASE 6: PM Gate", style="bold cyan"))

    escalated = gaps_above_threshold(frequency_log)

    # Filter out already-deferred gaps whose frequency hasn't increased
    escalated = [
        g for g in escalated
        if not already_deferred(g["gap_primitive"], defer_queue, frequency_log)
    ]

    if not escalated:
        console.print("[dim]No gaps above threshold to evaluate. Session complete.[/dim]")
        save_json(DEFER_QUEUE_PATH, {"deferred": defer_queue})
        console.print(Panel("SESSION END", style="bold green"))
        return

    console.print(f"[bold]{len(escalated)} gaps escalated to PM[/bold]")

    pm_prompt = pm.build_user_prompt(
        gaps=escalated,
        manifest=manifest,
        compositions=compositions,
        defer_queue=defer_queue,
    )

    try:
        pm_resp = pm.ask(pm_prompt)
        pm_result = PMOutput.model_validate(
            json.loads(clean_json_response(pm_resp))
        )
    except (json.JSONDecodeError, Exception) as e:
        console.print(f"[bold red]PM gate failed: {e}[/bold red]")
        save_json(DEFER_QUEUE_PATH, {"deferred": defer_queue})
        return

    accepted = []
    for decision in pm_result.decisions:
        console.print(f"  {decision.gap_primitive}: [bold]{decision.decision.upper()}[/bold]")
        console.print(f"    {decision.reasoning[:120]}...")

        if decision.decision == "defer":
            defer_queue.append({
                "primitive": decision.gap_primitive,
                "reason": decision.reasoning,
                "deferred_at": datetime.now().isoformat(),
                "frequency_at_deferral": decision.frequency_count,
                "roles_at_deferral": frequency_log.get(decision.gap_primitive, {}).get("roles", []),
            })
        elif decision.decision == "accept":
            accepted.append(decision)

    save_json(DEFER_QUEUE_PATH, {"deferred": defer_queue})

    if not accepted:
        console.print("[dim]No gaps accepted. Session complete.[/dim]")
        console.print(Panel("SESSION END", style="bold green"))
        return

    # ==================================================================
    # PHASE 7: Spec Writing
    # ==================================================================
    console.print(Panel("PHASE 7: Spec Writing", style="bold cyan"))

    OUTPUT_DIR.mkdir(exist_ok=True)

    for decision in accepted:
        console.print(f"\nWriting spec for [bold]{decision.gap_primitive}[/bold]...")

        # Find translator results relevant to this gap
        relevant_results = [
            r.model_dump() for r in translator_result.results
            if any(
                step.primitive == decision.gap_primitive
                for step in (
                    next(
                        (tr for tr in translator_result.results
                         if tr.canonical_label == r.canonical_label),
                        r,
                    )
                ).transformation_steps
            )
        ]

        spec_prompt = spec_writer.build_user_prompt(
            gap_primitive=decision.gap_primitive,
            pm_decision=decision.model_dump(),
            translator_results=relevant_results,
            manifest=manifest,
            compositions=compositions,
        )

        try:
            spec_text = spec_writer.ask(spec_prompt)
            output_path = OUTPUT_DIR / f"{decision.gap_primitive}_spec.md"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(spec_text)
            console.print(f"  [green]Spec written: {output_path}[/green]")
        except Exception as e:
            console.print(f"  [red]Spec writing failed for {decision.gap_primitive}: {e}[/red]")

    console.print(Panel("SESSION END", style="bold green"))


if __name__ == "__main__":
    main()
