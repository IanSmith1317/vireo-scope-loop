import json
import pytest
from pydantic import ValidationError

from agents.auditor_agents import (
    AuditorAgent,
    StepAuditResult,
    ClusterAuditResult,
    AuditorOutput,
)
from tests.conftest import SAMPLE_TRANSLATOR_RESULT, SAMPLE_MANIFEST, SAMPLE_AUDIT_FAIL, SAMPLE_AUDIT_PASS


class TestAuditorAgentInit:
    def test_sets_system_prompt(self):
        agent = AuditorAgent(model="test")
        assert "strict capability auditor" in agent.system_prompt
        assert "PASS/FAIL" in agent.system_prompt

    def test_system_prompt_has_example(self):
        agent = AuditorAgent(model="test")
        assert "import-lookup-compare-format" in agent.system_prompt
        assert "gap_primitives" in agent.system_prompt

    def test_custom_max_tokens(self):
        agent = AuditorAgent(model="test", max_tokens=16384)
        assert agent.max_tokens == 16384


class TestBuildUserPrompt:
    def test_includes_manifest_and_translator_output(self):
        agent = AuditorAgent(model="test")
        prompt = agent.build_user_prompt(
            translator_output=[SAMPLE_TRANSLATOR_RESULT],
            manifest=SAMPLE_MANIFEST,
        )
        assert "Capability Manifest" in prompt
        assert "compare" in prompt
        assert "import-compare" in prompt
        assert "Translated Clusters to Audit" in prompt


class TestStepAuditResult:
    def test_supported_step(self):
        s = StepAuditResult(
            step_order=1, primitive="compare", supported=True,
            manifest_match="compare", failure_reason=None,
        )
        assert s.supported is True

    def test_unsupported_step(self):
        s = StepAuditResult(
            step_order=1, primitive="import", supported=False,
            manifest_match=None, failure_reason="Not supported",
        )
        assert s.supported is False
        assert s.failure_reason == "Not supported"


class TestClusterAuditResult:
    def test_failed_cluster(self):
        r = ClusterAuditResult(**SAMPLE_AUDIT_FAIL)
        assert r.passed is False
        assert "import" in r.gap_primitives

    def test_passed_cluster(self):
        r = ClusterAuditResult(**SAMPLE_AUDIT_PASS)
        assert r.passed is True
        assert r.gap_primitives == []

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            ClusterAuditResult(canonical_label="x", passed=True)


class TestAuditorOutput:
    def test_valid_output(self):
        out = AuditorOutput(results=[
            ClusterAuditResult(**SAMPLE_AUDIT_FAIL),
            ClusterAuditResult(**SAMPLE_AUDIT_PASS),
        ])
        assert len(out.results) == 2

    def test_round_trip(self):
        out = AuditorOutput(results=[ClusterAuditResult(**SAMPLE_AUDIT_FAIL)])
        raw = json.dumps(out.model_dump())
        restored = AuditorOutput.model_validate(json.loads(raw))
        assert restored.results[0].passed is False
