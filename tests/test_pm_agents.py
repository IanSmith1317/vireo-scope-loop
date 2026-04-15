import json
import pytest
from pydantic import ValidationError

from agents.pm_agents import PMAgent, PMDecision, PMOutput
from tests.conftest import (
    SAMPLE_MANIFEST, SAMPLE_PM_ACCEPT, SAMPLE_PM_REJECT, SAMPLE_PM_DEFER,
)


class TestPMAgentInit:
    def test_sets_system_prompt(self):
        agent = PMAgent(model="test")
        assert "product management gate" in agent.system_prompt
        assert "Vireo" in agent.system_prompt

    def test_system_prompt_has_decision_framework(self):
        agent = PMAgent(model="test")
        assert "ACCEPT" in agent.system_prompt
        assert "REJECT" in agent.system_prompt
        assert "DEFER" in agent.system_prompt
        assert "ERP" in agent.system_prompt

    def test_system_prompt_has_example(self):
        agent = PMAgent(model="test")
        assert "import" in agent.system_prompt
        assert "distribute" in agent.system_prompt

    def test_custom_max_tokens(self):
        agent = PMAgent(model="test", max_tokens=16384)
        assert agent.max_tokens == 16384


class TestBuildUserPrompt:
    def test_includes_all_context(self):
        agent = PMAgent(model="test")
        prompt = agent.build_user_prompt(
            gaps=[{"gap_primitive": "import", "count": 5, "roles": ["FP&A"], "canonical_labels": ["import-compare"]}],
            manifest=SAMPLE_MANIFEST,
            compositions=SAMPLE_MANIFEST["compositions"],
            defer_queue=[],
        )
        assert "Capability Manifest" in prompt
        assert "Compositions" in prompt
        assert "Deferred Gaps" in prompt
        assert "Gaps to Evaluate" in prompt
        assert "import" in prompt


class TestPMDecision:
    def test_accept(self):
        d = PMDecision(**SAMPLE_PM_ACCEPT)
        assert d.decision == "accept"
        assert d.frequency_count == 5

    def test_reject(self):
        d = PMDecision(**SAMPLE_PM_REJECT)
        assert d.decision == "reject"

    def test_defer(self):
        d = PMDecision(**SAMPLE_PM_DEFER)
        assert d.decision == "defer"

    def test_invalid_decision(self):
        data = {**SAMPLE_PM_ACCEPT, "decision": "maybe"}
        with pytest.raises(ValidationError):
            PMDecision(**data)

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            PMDecision(gap_primitive="x", decision="accept")


class TestPMOutput:
    def test_mixed_decisions(self):
        out = PMOutput(decisions=[
            PMDecision(**SAMPLE_PM_ACCEPT),
            PMDecision(**SAMPLE_PM_REJECT),
            PMDecision(**SAMPLE_PM_DEFER),
        ])
        assert len(out.decisions) == 3
        decisions = {d.decision for d in out.decisions}
        assert decisions == {"accept", "reject", "defer"}

    def test_round_trip(self):
        out = PMOutput(decisions=[PMDecision(**SAMPLE_PM_ACCEPT)])
        raw = json.dumps(out.model_dump())
        restored = PMOutput.model_validate(json.loads(raw))
        assert restored.decisions[0].gap_primitive == "import"
