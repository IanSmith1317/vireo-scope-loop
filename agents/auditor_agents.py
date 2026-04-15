import json
from pydantic import BaseModel

from agents.base_agent import BaseAgent


class AuditorAgent(BaseAgent):
    def __init__(self, model: str, max_tokens: int | None = None):
        super().__init__(model=model, max_tokens=max_tokens)

        example_output = json.dumps({
            "results": [
                {
                    "canonical_label": "import-lookup-compare-format",
                    "passed": False,
                    "step_results": [
                        {
                            "step_order": 1,
                            "primitive": "import",
                            "supported": False,
                            "manifest_match": None,
                            "failure_reason": "Primitive 'import' is not supported in the manifest. No file ingestion nodes exist."
                        },
                        {
                            "step_order": 2,
                            "primitive": "lookup",
                            "supported": True,
                            "manifest_match": "lookup",
                            "failure_reason": None
                        },
                        {
                            "step_order": 3,
                            "primitive": "compare",
                            "supported": True,
                            "manifest_match": "compare",
                            "failure_reason": None
                        },
                        {
                            "step_order": 4,
                            "primitive": "format",
                            "supported": False,
                            "manifest_match": None,
                            "failure_reason": "Primitive 'format' is marked as partial. The specific operation (conditional formatting based on variance thresholds) exceeds the stated constraint: 'node output styling only, not cell-level conditional formatting'."
                        }
                    ],
                    "gap_primitives": ["import", "format"]
                }
            ]
        }, indent=2)

        self.system_prompt = f"""You are a strict capability auditor for a software application. Your job is to determine whether each transformation step in a workflow can be performed by the application, based solely on its capability manifest.

Audit rules:
- You will receive a list of translated workflow clusters, each containing ordered transformation steps with a primitive name, description, and logic.
- You will also receive the application's capability manifest, which lists each primitive with its support status, constraints, and limitations.
- For each transformation step, make a binary PASS/FAIL determination:
  - PASS: The primitive is marked as supported (supported: true) in the manifest AND the specific operation described in the step's logic and description falls within the manifest's stated constraints.
  - FAIL: The primitive is not supported (supported: false), OR the primitive is partially supported (partial: true) but the specific operation exceeds the stated constraints, OR the primitive is not listed in the manifest at all.
- Do NOT attempt creative workarounds. If a step requires "import" and import is not supported, it fails — even if the user could theoretically copy-paste data manually.
- Do NOT give partial credit. Each step is either fully supported or it is not.
- A cluster passes only if ALL of its transformation steps pass. If any single step fails, the cluster fails.

Manifest structure:
The manifest contains a "primitives" object where each key is a primitive name and the value has:
- "supported": boolean — whether the primitive is available at all
- "partial": boolean — whether it is supported but with significant limitations
- "constraints": list of strings — specific limitations on what the primitive can do
- "not_covered": list of strings — sub-operations explicitly marked as unsupported
- "description": string — what the application can do for this primitive

When a primitive is marked partial: true, you must check whether the specific operation in the transformation step falls within the constraints. If the step requires something listed in "not_covered" or something that exceeds the stated constraints, it is a FAIL.

For each cluster, return:
- canonical_label: the cluster's label
- passed: boolean (true only if ALL steps passed)
- step_results: list of per-step audit results
- gap_primitives: list of primitive names that failed (empty if all passed)

Here is an example of the expected output format:

{example_output}

Do not wrap the JSON in code fences, backticks, or any markdown formatting. Return raw JSON only."""

    def build_user_prompt(self, translator_output: list[dict], manifest: dict) -> str:
        return f"""Audit the following translated workflow clusters against the capability manifest.

## Capability Manifest

{json.dumps(manifest, indent=2)}

## Translated Clusters to Audit

{json.dumps(translator_output, indent=2)}"""


class StepAuditResult(BaseModel):
    step_order: int
    primitive: str
    supported: bool
    manifest_match: str | None
    failure_reason: str | None


class ClusterAuditResult(BaseModel):
    canonical_label: str
    passed: bool
    step_results: list[StepAuditResult]
    gap_primitives: list[str]


class AuditorOutput(BaseModel):
    results: list[ClusterAuditResult]
