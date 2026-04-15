import json
import pytest
from pydantic import ValidationError

from agents.canonicalizer_agents import (
    CanonicalizerAgent,
    CanonicalCluster,
    CanonicalizerOutput,
    PRIMITIVES,
)
from tests.conftest import SAMPLE_WORKFLOW, SAMPLE_CLUSTER


class TestCanonicalizerAgentInit:
    def test_default_primitives(self):
        agent = CanonicalizerAgent(model="test")
        assert agent.primitives == PRIMITIVES
        assert "import" in agent.system_prompt
        assert "lookup" in agent.system_prompt

    def test_custom_primitives(self):
        custom = ["import", "calculate"]
        agent = CanonicalizerAgent(model="test", primitives=custom)
        assert agent.primitives == custom
        assert "calculate" in agent.system_prompt

    def test_system_prompt_has_json_example(self):
        agent = CanonicalizerAgent(model="test")
        assert "clusters" in agent.system_prompt
        assert "primitive_chain" in agent.system_prompt


class TestBuildUserPrompt:
    def test_prompt_contains_workflow_data(self):
        agent = CanonicalizerAgent(model="test")
        workflows = [SAMPLE_WORKFLOW]
        prompt = agent.build_user_prompt(workflows)
        assert "1 workflows" in prompt
        assert SAMPLE_WORKFLOW["task_title"] in prompt

    def test_prompt_with_multiple_workflows(self):
        agent = CanonicalizerAgent(model="test")
        workflows = [SAMPLE_WORKFLOW, {**SAMPLE_WORKFLOW, "task_title": "Second Task"}]
        prompt = agent.build_user_prompt(workflows)
        assert "2 workflows" in prompt


class TestCanonicalCluster:
    def test_valid_cluster(self):
        c = CanonicalCluster(**SAMPLE_CLUSTER)
        assert c.canonical_label == "import-compare"
        assert c.source_indices == [0]

    def test_missing_field(self):
        data = {k: v for k, v in SAMPLE_CLUSTER.items() if k != "rationale"}
        with pytest.raises(ValidationError):
            CanonicalCluster(**data)


class TestCanonicalizerOutput:
    def test_valid_output(self):
        out = CanonicalizerOutput(clusters=[CanonicalCluster(**SAMPLE_CLUSTER)])
        assert len(out.clusters) == 1

    def test_empty_clusters(self):
        out = CanonicalizerOutput(clusters=[])
        assert len(out.clusters) == 0

    def test_round_trip(self):
        out = CanonicalizerOutput(clusters=[CanonicalCluster(**SAMPLE_CLUSTER)])
        raw = json.dumps(out.model_dump())
        restored = CanonicalizerOutput.model_validate(json.loads(raw))
        assert restored.clusters[0].canonical_label == "import-compare"
