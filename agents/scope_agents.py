from pydantic import BaseModel
from typing import Literal

from agents.base_agent import BaseAgent

class ScopeAgent(BaseAgent):
    
    def __init__(self, model:str, role: str):
        super().__init__(model=model)
        self.role = role
        self.system_prompt = """
            You are an expert analyst of how professionals use Microsoft Excel in real day-to-day work.

            Your task is to generate realistic natural-language descriptions of common Excel-centered workflows performed by a specified job function.

            Core instructions:
            - Focus on work primarily done in Microsoft Excel, including spreadsheet-based analysis, modeling, reporting, reconciliation, and dashboard preparation.
            - Use realistic Excel terminology naturally, such as workbook, worksheet, tab, formula, cell reference, pivot table, lookup, filter, sort, refresh, linked workbook, template, tracker, reconciliation, rollforward, variance analysis, summary tab, source data, and export.
            - Describe workflows the way a real employee would explain them, not like a software specification or abstract job description.
            - Keep workflows concrete, practical, and believable.
            - Emphasize what the user is trying to accomplish in Excel, what they do in the workbook, and why the workflow matters.
            - Include realistic spreadsheet work where appropriate, such as updating formulas, rolling forward files, cleaning exported data, checking tie-outs, validating totals, tracing broken links, reviewing tabs, maintaining trackers, and preparing summary outputs for review.
            - Do not focus on advanced Excel features unless they are genuinely typical for the role.
            - Do not mention Python, databases, APIs, automation tools, or BI tools unless explicitly requested.
            - Only mention other systems when they are the source of a file or export that is then brought into Excel.
            - Do not invent unrealistic responsibilities for the role.
            - Avoid generic statements like "supports decision-making" unless they are tied to a specific Excel workflow.

            Output requirements:
            Generate the specified number of unique workflow descriptions from the user prompt. Return ONLY valid JSON matching this schema, no other text:
            {
            "workflows": [
                {
                "role": "...",
                "task_title": "....",
                "task_description": "...",
                "inputs" : ["...","..."],
                "outputs" : ["...","..."],
                "common_excel_elements": ["...","..."],
                "frequency": "monthly",
                "complexity": "medium",
                "recurring": true
                }
            ]
            }

            Note: List-type elements like "inputs" and "outputs" may be of any length greater than or equal to one. Do not wrap the JSON in code fences, backticks, or any markdown formatting. Return raw JSON only.

            Quality bar:
            - Each workflow should feel like a distinct, common, real-world task.
            - Prefer workflows that are frequent, important, or especially characteristic of the role in Excel.
            - Use clear Microsoft Excel verbiage throughout.
            - Avoid buzzwords, fluff, and vague abstractions.
            """

class ScopeWorkflow(BaseModel):
    role: str
    task_title: str
    task_description: str
    inputs: list[str]
    outputs : list[str]
    common_excel_elements: list[str]
    frequency: Literal["daily", "weekly", "monthly", "quarterly", "annually"]
    complexity: Literal["low", "medium", "high"]
    recurring: bool

class ScopeAgentOutput(BaseModel):
    workflows: list[ScopeWorkflow]
                    