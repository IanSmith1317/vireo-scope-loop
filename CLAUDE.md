# CLAUDE.md — vireo-scope-loop

## Project identity

This is the **vireo-scope-loop**, a standalone Python project that implements an agentic discovery and validation loop for Vireo. It lives in its own repo, separate from the Vireo product codebase. It is a meta-tool that operates *on* Vireo — it should never be a dependency of Vireo itself.

**Vireo** is a desktop financial modeling application (separate repo). It uses node-based programming to make structural change in recurring FP&A models safe, visible, and fast. Vireo is not an Excel replacement — it is modern financial modeling infrastructure. See the Vireo project docs for full context on product philosophy, ICP, and positioning.

This loop's purpose is to systematically discover what spreadsheet workflows real finance professionals perform, determine whether Vireo can handle them, identify gaps, and prioritize what to build — without the product becoming bloated or niche to one role.

## Repo structure

```
vireo-scope-loop/
├── orchestrator.py              # Main loop control
├── config.py                    # API keys, model selection, role weights
├── utils.py                     # Shared helpers (clean_json_response, etc.)
├── agents/
│   ├── base_agent.py            # BaseAgent class — all agents inherit from this
│   ├── scope_agents.py          # ScopeAgent — generates role-based Excel workflows
│   ├── canonicalizer_agents.py  # CanonicalizerAgent — dedup + cluster into primitives
│   ├── translator_agents.py     # TranslatorAgent — extract input/output schemas
│   ├── auditor_agents.py        # AuditorAgent — check against capability manifest
│   ├── pm_agents.py             # PMAgent — accept/reject/defer gate
│   ├── spec_writer_agents.py    # SpecWriterAgent — write implementation specs
│   ├── executor_agents.py       # ExecutorAgent — Claude Code bridge
│   └── reviewer_agents.py       # ReviewerAgent — test + regression
├── manifest/
│   └── vireo_manifest.json      # Vireo capabilities: primitives + compositions in one file
├── state/
│   ├── frequency_log.json       # Gap frequency counter across iterations
│   ├── defer_queue.json         # Gaps marked "valid but not priority"
│   └── regression_suite.json    # Passing scope descriptions for regression testing
└── requirements.txt
```

## Agent architecture

All agents inherit from `BaseAgent` in `agents/base_agent.py`. BaseAgent handles:
- Anthropic API client instantiation
- Payload construction (model, max_tokens, system prompt, messages, tools)
- Response text extraction via the `ask(user_prompt)` method

Each agent subclass sets its own `self.system_prompt` in `__init__` and exposes a `build_user_prompt(...)` method that the orchestrator calls to construct the user message.

### Agent flow

```
Scope agents (generate Excel workflow descriptions per role)
    ↓
Canonicalizer (cluster by underlying spreadsheet primitives)
    ↓
Translator (extract precise input/output schemas per cluster)
    ↓
Auditor (check each cluster against Vireo capability manifest)
    ↓  PASS → loop restarts
    ↓  FAIL ↓
Frequency counter (track how often each gap surfaces)
    ↓
PM agent (accept / reject / defer the gap)
    ↓  REJECT → loop restarts
    ↓  DEFER  → defer queue
    ↓  ACCEPT ↓
Spec writer (write implementation spec) → HUMAN REVIEW GATE
    ↓
Executor (implement via Claude Code)
    ↓
Reviewer (test new feature + run regression on prior passing workflows)
```

### Agent details

**Scope agents** — Role-parameterized. Generate batches of 8-12 workflow descriptions per API call. Output is structured JSON parsed into `ScopeWorkflow` Pydantic models. Roles are weighted by ICP priority: FP&A analyst (40%), FP&A manager (20%), treasury (10%), credit (10%), project finance (10%), corp dev (5%), controller (5%). Each call receives a `previously_generated` list to prevent duplication across batches.

**Canonicalizer** — Receives a flat list of `ScopeWorkflow` dicts. Decomposes each into an ordered chain of spreadsheet primitives from a fixed vocabulary, then clusters workflows with matching chains. Output is `CanonicalizerOutput` containing `CanonicalCluster` objects with `source_indices` referencing back to the input list.

**Translator** — Receives canonical clusters plus the original workflow dicts. Produces precise `TableSchema` objects for inputs/outputs, ordered `TransformationStep` objects, and an `assumptions` list for things inferred but not stated. `build_user_prompt` embeds source workflows directly into each cluster payload so the model doesn't have to cross-reference indices.

**Auditor** — Receives translator output plus the Vireo capability manifest. Maps each transformation step to a Vireo primitive or composition. Binary PASS/FAIL — does not attempt creative workarounds. Use Opus model for this agent.

**PM agent** — The most critical gate. Receives the gap, frequency data, capability manifest with compositions, defer queue, and Vireo strategic positioning docs. Makes accept/reject/defer decisions. Use Opus model for this agent. Rejection criteria: would this make Vireo more like an ERP? Reject. Serves only one niche role? Defer. Adds a composable primitive? Accept.

**Spec writer** — Outputs structured markdown specs for human review. No code is written until a human approves the spec.

**Executor** — Bridges to Claude Code (with PowerShell tool enabled on Windows) via subprocess. Points at the Vireo repo directory configured in `config.py`.

**Reviewer** — Two checks: (1) new feature handles the spec's input/output correctly, (2) random sample of 10-20 previously passing scope descriptions still pass the auditor after the change.

## Spreadsheet primitive vocabulary

The canonical primitive set used by the canonicalizer and auditor:

```
import, lookup, filter, sort, aggregate, pivot, unpivot, join,
calculate, compare, reshape, format, chart, validate, rollforward,
scenario, protect, distribute, actualize, trim, replace, split,
standardize, flag, rank
```

This list is passed into the CanonicalizerAgent constructor and can be extended via config. When adding new primitives, also update the capability manifest.

## Data flow between agents

All inter-agent communication is JSON. The orchestrator serializes Pydantic models with `model_dump()`, passes them as part of user prompts, and parses responses back into Pydantic models with `model_validate(json.loads(...))`.

Pattern:
```python
workflows_json = [w.model_dump() for w in all_workflows]
user_prompt = agent.build_user_prompt(workflows_json)
response = agent.ask(user_prompt)
result = OutputModel.model_validate(json.loads(clean_json_response(response)))
```

All agent responses must be cleaned before parsing — models sometimes wrap JSON in markdown code fences. Use `clean_json_response()` from `utils.py` on every response.

## Pydantic models

Each agent file defines its own output schema as Pydantic BaseModel subclasses. Keep data models in the same file as their agent. Do not create a shared models file — agents should be self-contained.

Key models:
- `ScopeWorkflow`, `ScopeAgentOutput` — in scope_agents.py
- `CanonicalCluster`, `CanonicalizerOutput` — in canonicalizer_agents.py
- `ColumnDef`, `TableSchema`, `TransformationStep`, `TranslatorResult`, `TranslatorOutput` — in translator_agents.py
- `StepAuditResult`, `ClusterAuditResult`, `AuditorOutput` — in auditor_agents.py
- `PMDecision`, `PMOutput` — in pm_agents.py

## Model selection

- **Sonnet** (`claude-sonnet-4-20250514`): scope, canonicalizer, translator, spec writer, reviewer
- **Opus** (`claude-opus-4-6`): auditor, PM agent (judgment-heavy)

Model strings are configured in `config.py`. The project uses the Anthropic API directly via the `anthropic` Python SDK.

## System prompt conventions

- All system prompts are set in `__init__` as `self.system_prompt`
- System prompts use f-strings to inject dynamic content (primitive lists, role names)
- When f-strings contain JSON examples, define the JSON example as a separate string variable to avoid brace escaping issues. Do NOT use quadruple braces.
- Every system prompt ends with: "Do not wrap the JSON in code fences, backticks, or any markdown formatting. Return raw JSON only."
- JSON schema examples in system prompts must be valid JSON with realistic sample data

## Config

`config.py` contains:
```python
API_KEY = ...              # Anthropic API key, loaded from Windows keyring
MAX_TOKENS = ...           # Default max tokens for agent calls
MODEL_LOW = ...            # Sonnet model string
MODEL_HIGH = ...           # Opus model string
FREQUENCY_THRESHOLD = ...  # Min gap occurrences to escalate to PM (default 3)
ROLE_THRESHOLD = ...       # Min distinct roles to escalate to PM (default 2)
WORKFLOWS_PER_CALL = ...   # Workflows per scope agent call (default 10)
ITERATIONS_PER_ROLE = ...  # Scope agent calls per role (default 5)
ROLES = [...]              # (role_name, weight) tuples for ICP priority
```

Sensitive values come from `keyring` (Windows Credential Manager). Never hardcode API keys.

## Secrets and .gitignore

The Anthropic API key is stored in Windows Credential Manager via `keyring` and retrieved at runtime — it never appears in source. The `.gitignore` excludes:

- `.env` — not currently used but excluded as a safeguard
- `.claude/` — local Claude Code settings and plan files
- `output/` — generated spec markdown files (runtime artifacts)
- `state/frequency_log.json`, `state/defer_queue.json`, `state/regression_suite.json` — runtime state files regenerated by the orchestrator

The `manifest/vireo_manifest.json` IS committed — it is a curated input to the pipeline, not a generated artifact.

## Dependencies

```
anthropic
pydantic
python-dotenv
rich
keyring
```

Add `tiktoken` and `pandas` later if needed for token counting and batch analytics. Do not install langchain or any orchestration framework — plain functions calling the Anthropic API.

## Development conventions

- Python 3.12+
- Virtual environment in `.venv/`
- On Windows: `.venv\Scripts\activate` in PowerShell
- pip install with `--break-system-packages` is NOT needed inside a venv
- Type hints on all function signatures
- No classes for things that should be functions — agents are classes, utilities are functions
- State files in `state/` are plain JSON, not databases (upgrade to sqlite-utils later if needed)

## Important patterns

**Batch discovery before building.** Run 50-100 scope agent outputs through the discovery chain (scope → canonicalizer → translator → auditor) before enabling the build pipeline. Review the full gap report first.

**Manifest maintenance.** After every feature ships in Vireo (whether from this loop or not), update `vireo_manifest.json`. The auditor evaluates against the manifest, so stale manifests cause false gap reports.

**Frequency threshold.** Gaps escalate to the PM agent only after 3+ occurrences across 2+ roles. Single-occurrence gaps from niche roles are not worth evaluating.

## What this project is NOT

- Not part of the Vireo product — never import from or depend on Vireo code
- Not a general-purpose agent framework — it solves one specific discovery loop
- Not meant to run fully autonomously yet — the spec writer → executor path has a human review gate
- Not an Excel tool — it reasons about Excel workflows but never opens or manipulates spreadsheets
