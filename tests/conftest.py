import json
import pytest
from unittest.mock import MagicMock


def make_text_block(text: str):
    """Create a mock Anthropic text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_tool_use_block():
    """Create a mock Anthropic tool_use content block (no .text)."""
    block = MagicMock(spec=["type", "id", "name", "input"])
    block.type = "tool_use"
    return block


def make_api_response(text: str):
    """Create a mock Anthropic messages.create() return value."""
    message = MagicMock()
    message.content = [make_text_block(text)]
    return message


# ---------------------------------------------------------------------------
# Reusable sample data
# ---------------------------------------------------------------------------

SAMPLE_WORKFLOW = {
    "role": "FP&A Analyst",
    "task_title": "Monthly Budget Variance Report",
    "task_description": "Compare actuals against budget using VLOOKUP and variance formulas",
    "inputs": ["GL actuals export", "Annual budget file"],
    "outputs": ["Budget variance report"],
    "common_excel_elements": ["VLOOKUP", "SUM", "conditional formatting"],
    "frequency": "monthly",
    "complexity": "medium",
    "recurring": True,
}

SAMPLE_CLUSTER = {
    "primitive_chain": ["import", "compare"],
    "canonical_label": "import-compare",
    "source_indices": [0],
    "rationale": "Both import external data and compare values",
}

SAMPLE_TRANSLATOR_RESULT = {
    "canonical_label": "import-compare",
    "input_schemas": [
        {"table_name": "actuals", "columns": [{"name": "amount", "dtype": "currency", "description": "Amount"}]}
    ],
    "output_schemas": [
        {"table_name": "variance", "columns": [{"name": "diff", "dtype": "currency", "description": "Difference"}]}
    ],
    "transformation_steps": [
        {
            "step_order": 1,
            "primitive": "import",
            "description": "Load actuals",
            "input_tables": ["actuals"],
            "output_table": "loaded",
            "logic": "Read CSV",
            "assumptions": [],
        },
        {
            "step_order": 2,
            "primitive": "compare",
            "description": "Compare values",
            "input_tables": ["loaded"],
            "output_table": "variance",
            "logic": "actual - budget",
            "assumptions": [],
        },
    ],
    "assumptions": [],
}

SAMPLE_AUDIT_FAIL = {
    "canonical_label": "import-compare",
    "passed": False,
    "step_results": [
        {"step_order": 1, "primitive": "import", "supported": False, "manifest_match": None, "failure_reason": "Not supported"},
        {"step_order": 2, "primitive": "compare", "supported": True, "manifest_match": "compare", "failure_reason": None},
    ],
    "gap_primitives": ["import"],
}

SAMPLE_AUDIT_PASS = {
    "canonical_label": "compare-validate",
    "passed": True,
    "step_results": [
        {"step_order": 1, "primitive": "compare", "supported": True, "manifest_match": "compare", "failure_reason": None},
    ],
    "gap_primitives": [],
}

SAMPLE_PM_ACCEPT = {
    "gap_primitive": "import",
    "canonical_labels": ["import-compare"],
    "decision": "accept",
    "reasoning": "Foundational primitive needed by all roles for data ingestion into the modeling layer",
    "frequency_count": 5,
    "distinct_roles": 3,
}

SAMPLE_PM_REJECT = {
    "gap_primitive": "distribute",
    "canonical_labels": ["import-format-distribute"],
    "decision": "reject",
    "reasoning": "Distribution is ERP territory, not financial modeling",
    "frequency_count": 4,
    "distinct_roles": 3,
}

SAMPLE_PM_DEFER = {
    "gap_primitive": "chart",
    "canonical_labels": ["import-aggregate-chart"],
    "decision": "defer",
    "reasoning": "Visualization is valuable but not core to modeling identity at this stage",
    "frequency_count": 3,
    "distinct_roles": 2,
}

SAMPLE_MANIFEST = {
    "version": "0.1.0",
    "primitives": {
        "compare": {
            "supported": True,
            "partial": False,
            "node_types": ["CompareNode"],
            "description": "Compare two values",
            "constraints": [],
            "not_covered": [],
            "notes": "",
        },
        "import": {
            "supported": False,
            "partial": False,
            "node_types": [],
            "description": "",
            "constraints": [],
            "not_covered": [],
            "notes": "",
        },
    },
    "compositions": [
        {
            "name": "budget-variance",
            "description": "Compare actuals to budget",
            "primitive_chain": ["lookup", "calculate", "compare"],
            "node_sequence": ["LookupNode", "CalcNode", "CompareNode"],
            "example_use_case": "Monthly budget variance",
        }
    ],
}


@pytest.fixture
def sample_workflow():
    return SAMPLE_WORKFLOW.copy()


@pytest.fixture
def sample_cluster():
    return SAMPLE_CLUSTER.copy()


@pytest.fixture
def mock_anthropic():
    """Patch the Anthropic class in base_agent so .ask() never hits the real API."""
    from unittest.mock import patch

    with patch("agents.base_agent.Anthropic") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        client.messages.create.return_value = make_api_response("{}")
        yield client
