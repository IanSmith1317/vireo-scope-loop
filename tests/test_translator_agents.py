import json
import pytest
from pydantic import ValidationError

from agents.translator_agents import (
    TranslatorAgent,
    ColumnDef,
    TableSchema,
    TransformationStep,
    TranslatorResult,
    TranslatorOutput,
)
from tests.conftest import SAMPLE_WORKFLOW, SAMPLE_CLUSTER, SAMPLE_TRANSLATOR_RESULT


class TestTranslatorAgentInit:
    def test_default_max_tokens(self):
        agent = TranslatorAgent(model="test")
        assert agent.max_tokens == 8192

    def test_custom_max_tokens(self):
        agent = TranslatorAgent(model="test", max_tokens=16384)
        assert agent.max_tokens == 16384

    def test_system_prompt_has_example(self):
        agent = TranslatorAgent(model="test")
        assert "actuals_export" in agent.system_prompt
        assert "variance_report" in agent.system_prompt
        assert "raw JSON only" in agent.system_prompt


class TestBuildUserPrompt:
    def test_enriches_clusters_with_workflows(self):
        agent = TranslatorAgent(model="test")
        clusters = [SAMPLE_CLUSTER]
        workflows = [SAMPLE_WORKFLOW]
        prompt = agent.build_user_prompt(clusters, workflows)
        parsed = json.loads(prompt.split("\n\n", 1)[1])
        assert len(parsed) == 1
        assert parsed[0]["canonical_label"] == "import-compare"
        assert len(parsed[0]["source_workflows"]) == 1
        assert parsed[0]["source_workflows"][0]["task_title"] == SAMPLE_WORKFLOW["task_title"]

    def test_skips_out_of_range_indices(self):
        agent = TranslatorAgent(model="test")
        cluster = {**SAMPLE_CLUSTER, "source_indices": [0, 99]}
        prompt = agent.build_user_prompt([cluster], [SAMPLE_WORKFLOW])
        parsed = json.loads(prompt.split("\n\n", 1)[1])
        assert len(parsed[0]["source_workflows"]) == 1

    def test_prompt_header(self):
        agent = TranslatorAgent(model="test")
        prompt = agent.build_user_prompt([SAMPLE_CLUSTER], [SAMPLE_WORKFLOW])
        assert "1 canonical clusters" in prompt


class TestColumnDef:
    def test_valid(self):
        c = ColumnDef(name="amount", dtype="currency", description="Dollar amount")
        assert c.name == "amount"

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            ColumnDef(name="amount", dtype="currency")


class TestTableSchema:
    def test_valid(self):
        col = ColumnDef(name="x", dtype="string", description="desc")
        ts = TableSchema(table_name="t", columns=[col])
        assert ts.table_name == "t"
        assert len(ts.columns) == 1


class TestTransformationStep:
    def test_valid(self):
        step = TransformationStep(
            step_order=1,
            primitive="import",
            description="Load data",
            input_tables=["raw"],
            output_table="loaded",
            logic="Read CSV",
            assumptions=["UTF-8 encoding"],
        )
        assert step.primitive == "import"
        assert step.assumptions == ["UTF-8 encoding"]


class TestTranslatorResult:
    def test_valid(self):
        r = TranslatorResult(**SAMPLE_TRANSLATOR_RESULT)
        assert r.canonical_label == "import-compare"
        assert len(r.transformation_steps) == 2

    def test_missing_field(self):
        data = {k: v for k, v in SAMPLE_TRANSLATOR_RESULT.items() if k != "assumptions"}
        with pytest.raises(ValidationError):
            TranslatorResult(**data)


class TestTranslatorOutput:
    def test_valid(self):
        out = TranslatorOutput(results=[TranslatorResult(**SAMPLE_TRANSLATOR_RESULT)])
        assert len(out.results) == 1

    def test_round_trip(self):
        out = TranslatorOutput(results=[TranslatorResult(**SAMPLE_TRANSLATOR_RESULT)])
        raw = json.dumps(out.model_dump())
        restored = TranslatorOutput.model_validate(json.loads(raw))
        assert restored.results[0].canonical_label == "import-compare"
