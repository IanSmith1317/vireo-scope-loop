import json
from pydantic import BaseModel

from agents.base_agent import BaseAgent


class TranslatorAgent(BaseAgent):
    def __init__(self, model: str, max_tokens: int | None = None):
        super().__init__(model=model, max_tokens=max_tokens or 8192)

        example_output = json.dumps({
            "results": [
                {
                    "canonical_label": "import-lookup-compare-format",
                    "input_schemas": [
                        {
                            "table_name": "actuals_export",
                            "columns": [
                                {"name": "period", "dtype": "date", "description": "Month-end date for the accounting period"},
                                {"name": "account_code", "dtype": "string", "description": "GL account identifier"},
                                {"name": "amount", "dtype": "currency", "description": "Actual spend for the period"}
                            ]
                        },
                        {
                            "table_name": "budget_reference",
                            "columns": [
                                {"name": "period", "dtype": "date", "description": "Budget period"},
                                {"name": "account_code", "dtype": "string", "description": "GL account identifier"},
                                {"name": "budgeted_amount", "dtype": "currency", "description": "Approved budget for the period"}
                            ]
                        }
                    ],
                    "output_schemas": [
                        {
                            "table_name": "variance_report",
                            "columns": [
                                {"name": "period", "dtype": "date", "description": "Reporting period"},
                                {"name": "account_code", "dtype": "string", "description": "GL account identifier"},
                                {"name": "actual", "dtype": "currency", "description": "Actual amount"},
                                {"name": "budget", "dtype": "currency", "description": "Budgeted amount"},
                                {"name": "variance", "dtype": "currency", "description": "Actual minus budget"},
                                {"name": "variance_pct", "dtype": "float", "description": "Variance as percentage of budget"}
                            ]
                        }
                    ],
                    "transformation_steps": [
                        {
                            "step_order": 1,
                            "primitive": "import",
                            "description": "Load actuals export from ERP system",
                            "input_tables": ["actuals_export"],
                            "output_table": "actuals_cleaned",
                            "logic": "Read CSV/Excel file, parse dates, validate account codes are non-null",
                            "assumptions": ["File is exported monthly from ERP", "Account codes are consistent between actuals and budget"]
                        },
                        {
                            "step_order": 2,
                            "primitive": "lookup",
                            "description": "Match each actual line to its budget counterpart",
                            "input_tables": ["actuals_cleaned", "budget_reference"],
                            "output_table": "matched_data",
                            "logic": "JOIN actuals_cleaned ON budget_reference WHERE actuals.account_code = budget.account_code AND actuals.period = budget.period",
                            "assumptions": ["One-to-one match on account_code + period"]
                        },
                        {
                            "step_order": 3,
                            "primitive": "compare",
                            "description": "Calculate variance between actual and budget",
                            "input_tables": ["matched_data"],
                            "output_table": "variance_report",
                            "logic": "variance = actual - budget; variance_pct = variance / budget",
                            "assumptions": ["Budget is never zero for active accounts"]
                        },
                        {
                            "step_order": 4,
                            "primitive": "format",
                            "description": "Apply conditional formatting to highlight material variances",
                            "input_tables": ["variance_report"],
                            "output_table": "variance_report",
                            "logic": "Highlight rows where ABS(variance_pct) > 0.10 in red; positive variances in green",
                            "assumptions": ["10% materiality threshold is standard for this organization"]
                        }
                    ],
                    "assumptions": [
                        "Actuals are available by the 5th business day of the following month",
                        "Budget file is locked and does not change mid-year",
                        "Account code taxonomy is shared between GL and budget systems"
                    ]
                }
            ]
        }, indent=2)

        self.system_prompt = f"""You are an expert at extracting precise data schemas and transformation logic from spreadsheet workflow descriptions.

Your task is to take canonical clusters of spreadsheet workflows — each cluster defined by a primitive chain and a set of source workflow descriptions — and produce:
1. Precise input table schemas (what data enters the workflow)
2. Precise output table schemas (what the workflow produces)
3. Ordered transformation steps mapping each primitive in the chain to a concrete operation
4. Explicit assumptions for anything inferred but not stated

Schema extraction rules:
- Read the source workflows' task_description, inputs, outputs, and common_excel_elements fields to determine realistic column names, data types, and table structures.
- Use domain-appropriate column names. Financial workflows should have columns like account_code, period, amount, department — not generic col1, col2.
- Data types must be one of: string, integer, float, currency, date, boolean, percentage.
- Each table schema must have a table_name that is referenced consistently across transformation steps.
- If a workflow mentions multiple input files or data sources, create separate input table schemas for each.

Transformation step rules:
- One step per primitive in the cluster's primitive_chain, in the same order.
- Each step must reference its input_tables and output_table by name.
- The logic field should contain a pseudo-formula, SQL-like expression, or clear rule — not vague prose. For example: "SUM(amount) GROUP BY department" not "aggregate the data".
- The assumptions field on each step captures things you inferred to make the logic specific (e.g., "assumes monthly granularity", "assumes unique key on account_code + period").

Cluster-level assumptions:
- Capture any cross-cutting assumptions that apply to the workflow as a whole, not just one step.

Here is an example of the expected output format with realistic financial data:

{example_output}

Do not wrap the JSON in code fences, backticks, or any markdown formatting. Return raw JSON only."""

    def build_user_prompt(self, clusters: list[dict], workflows: list[dict]) -> str:
        enriched = []
        for cluster in clusters:
            source_workflows = [workflows[i] for i in cluster["source_indices"] if i < len(workflows)]
            enriched.append({
                "canonical_label": cluster["canonical_label"],
                "primitive_chain": cluster["primitive_chain"],
                "source_workflows": source_workflows
            })

        return f"Extract precise input/output schemas and transformation steps for the following {len(enriched)} canonical clusters:\n\n{json.dumps(enriched, indent=2)}"


class ColumnDef(BaseModel):
    name: str
    dtype: str
    description: str


class TableSchema(BaseModel):
    table_name: str
    columns: list[ColumnDef]


class TransformationStep(BaseModel):
    step_order: int
    primitive: str
    description: str
    input_tables: list[str]
    output_table: str
    logic: str
    assumptions: list[str]


class TranslatorResult(BaseModel):
    canonical_label: str
    input_schemas: list[TableSchema]
    output_schemas: list[TableSchema]
    transformation_steps: list[TransformationStep]
    assumptions: list[str]


class TranslatorOutput(BaseModel):
    results: list[TranslatorResult]
