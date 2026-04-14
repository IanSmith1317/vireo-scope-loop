from pydantic import BaseModel
import json
from agents.base_agent import BaseAgent


PRIMITIVES = [
    "import",           # paste/load external data
    "lookup",           # VLOOKUP, INDEX-MATCH, XLOOKUP
    "filter",           # filter rows by condition
    "sort",             # reorder rows
    "aggregate",        # SUMIF, SUMIFS, COUNTIF, subtotals
    "pivot",            # pivot table or manual pivot layout
    "unpivot",          # melt wide-format to long
    "join",             # combine two tables on a key
    "calculate",        # arithmetic, formulas, derived columns
    "compare",          # variance, diff, tie-out, reconciliation
    "reshape",          # transpose, rearrange structure
    "format",           # conditional formatting, styling
    "chart",            # graphs, sparklines, visualizations
    "validate",         # checks, balances, tie-outs
    "rollforward",      # shift time window, insert/delete period
    "scenario",         # toggle assumptions, what-if, data tables
    "protect",          # lock cells, protect sheets
    "distribute",       # save copies, email, PDF export
    "actualize",
    "trim",
    "replace",
    "split",
    "standardize",
    "flag",
    "rank"
]



class CanonicalizerAgent(BaseAgent):
    def __init__(self, model:str, primitives: list[str] | None = None):
        super().__init__(model=model)
        self.primitives = primitives or PRIMITIVES
        primitive_list = ", ".join(self.primitives)
        self.system_prompt = f"""You are an expert at decomposing spreadsheet workflows into structural primitives.

                                Your task is to take a list of workflow descriptions and:
                                1. Decompose each workflow into an ordered chain of spreadsheet primitives.
                                2. Cluster workflows that share the same core primitive chain.
                                3. Return the clusters with references back to the original workflow indices.

                                Primitive vocabulary (use ONLY these terms):
                                {primitive_list}

                                Decomposition rules:
                                - Read each workflow's task_description and common_excel_elements fields to determine what the spreadsheet is structurally doing.
                                - Ignore domain language. "Budget variance analysis" and "cash position reconciliation" may both be import → compare. Focus on the spreadsheet operations, not the financial context.
                                - Order the primitives in the sequence a user would perform them. Import almost always comes first. Format, chart, and distribute almost always come last.
                                - Use the fewest primitives that accurately capture the workflow. Do not pad chains with trivial steps. If a workflow is just pasting data and making a chart, that is import → chart, not import → filter → sort → calculate → format → chart.
                                - A primitive must appear in the chain only if the workflow explicitly describes that operation or it is clearly implied by the described output.

                                Clustering rules:
                                - Two workflows belong in the same cluster if their primitive chains are identical.
                                - If two chains differ by only a trailing step like format, chart, or distribute, they are still the same cluster. Use the longer chain as the canonical one.
                                - If two chains differ by a core step in the middle (e.g., one has lookup and the other does not), they are separate clusters.
                                - When in doubt, keep them separate. The auditor will handle nuance.

                                For each cluster, provide:
                                - primitive_chain: the ordered list of primitives
                                - canonical_label: a short hyphenated label joining the key primitives (e.g., "import-lookup-compare-format")
                                - source_indices: list of integer indices from the input array
                                - rationale: one sentence explaining why these workflows cluster together

                                Do not wrap the JSON in code fences, backticks, or any markdown formatting. Return raw JSON only, matching this schema:
                                {{
                                "clusters": [
                                    {{
                                    "primitive_chain": ["import", "compare", "format"],
                                    "canonical_label": "import-compare-format",
                                    "source_indices": [0, 3, 7],
                                    "rationale": "All three workflows import external data and compare against a reference."
                                    }}
                                ]
                                }}"""

    def build_user_prompt(self, workflows_json: list[dict]) -> str:
        return f"Decompose and cluster the following {len(workflows_json)} workflows:\n\n{json.dumps(workflows_json, indent=2)}"
    


    
class CanonicalCluster(BaseModel):
    primitive_chain: list[str]
    canonical_label: str
    source_indices: list[int]
    rationale: str

class CanonicalizerOutput(BaseModel):
    clusters: list[CanonicalCluster]