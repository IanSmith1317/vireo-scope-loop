import json

from agents.base_agent import BaseAgent


class SpecWriterAgent(BaseAgent):
    def __init__(self, model: str, max_tokens: int | None = None):
        super().__init__(model=model, max_tokens=max_tokens or 8192)

        self.system_prompt = """You are a technical specification writer for Vireo, a desktop financial modeling application that uses node-based programming.

Your task is to write a detailed, actionable implementation specification for a new primitive (node type) to be added to Vireo. The spec must be precise enough that a developer can implement the feature without additional context.

Vireo context:
- Vireo uses a node-based graph where each node performs a discrete operation on tabular financial data.
- Nodes are composable — the output of one node feeds into the input of the next.
- Vireo's core primitives handle calculations, lookups, comparisons, scenarios, rollforwards, validations, and similar modeling operations.
- New primitives must be composable: they accept well-defined input schemas and produce well-defined output schemas that other nodes can consume.

Specification structure — include ALL of the following sections:

# <Primitive Name>

## Summary
One paragraph: what this primitive does, why it matters for financial modeling, and where it fits in Vireo's node graph.

## Motivation
- Which professional roles need this primitive and how frequently.
- Specific workflow examples that are currently blocked without it.
- Frequency and cross-role data from the discovery process.

## Input Schema
A markdown table defining every input the node accepts:
| Field | Type | Required | Description |
Include all columns, their data types, whether they are required or optional, and what they represent.

## Output Schema
A markdown table defining every output the node produces:
| Field | Type | Description |
Include all columns the node outputs after transformation.

## Transformation Logic
Step-by-step description of what the node does internally:
1. Validate inputs against schema
2. Perform the core operation (with pseudo-code or formulas where helpful)
3. Produce outputs
Be specific about edge cases: what happens with nulls, zero-division, missing keys, type mismatches.

## Composition
How this primitive composes with existing Vireo primitives:
- Which nodes typically feed into this one (upstream)
- Which nodes typically consume this one's output (downstream)
- Example 2-3 node chains that become possible with this primitive

## Constraints & Assumptions
- What this primitive explicitly does NOT handle
- Performance constraints (max rows, memory considerations)
- Data assumptions (e.g., "assumes input is sorted by date")
- What should be handled by a different primitive instead

## Acceptance Criteria
Bulleted list of testable conditions for "done":
- [ ] Each criterion should be specific and verifiable
- [ ] Include both happy-path and edge-case criteria
- [ ] Include composition tests (works correctly when chained with X node)

## PM Decision Context
Why the PM accepted this primitive for implementation:
- The strategic reasoning behind the accept decision
- How this aligns with Vireo's product identity
- What alternatives were considered

Write the specification in clean, well-formatted markdown. Use tables, code blocks, and bullet lists where appropriate. Be specific and actionable throughout — avoid vague language like "handles various cases" or "processes the data appropriately"."""

    def build_user_prompt(self, gap_primitive: str, pm_decision: dict, translator_results: list[dict], manifest: dict, compositions: list[dict]) -> str:
        return f"""Write an implementation specification for the following primitive.

## Primitive to Specify

{gap_primitive}

## PM Decision

{json.dumps(pm_decision, indent=2)}

## Translator Analysis (schemas and transformation logic from discovered workflows)

{json.dumps(translator_results, indent=2)}

## Current Vireo Capabilities (for composition context)

{json.dumps(manifest, indent=2)}

## Existing Compositions

{json.dumps(compositions, indent=2)}"""
