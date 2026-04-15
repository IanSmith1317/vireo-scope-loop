import json
import pytest
from pydantic import ValidationError

from agents.scope_agents import ScopeAgent, ScopeWorkflow, ScopeAgentOutput
from tests.conftest import SAMPLE_WORKFLOW, make_api_response


class TestScopeAgentInit:
    def test_sets_role(self):
        agent = ScopeAgent(model="test", role="Controller")
        assert agent.role == "Controller"

    def test_sets_system_prompt(self):
        agent = ScopeAgent(model="test", role="FP&A Analyst")
        assert agent.system_prompt is not None
        assert "Microsoft Excel" in agent.system_prompt
        assert len(agent.system_prompt) > 100


class TestBuildUserPrompt:
    def test_includes_role_and_count(self):
        agent = ScopeAgent(model="test", role="Treasury Analyst")
        prompt = agent.build_user_prompt(count=5)
        assert "5" in prompt
        assert "Treasury Analyst" in prompt

    def test_no_dedup_section_when_none(self):
        agent = ScopeAgent(model="test", role="Controller")
        prompt = agent.build_user_prompt(count=3, previously_generated=None)
        assert "Do NOT generate workflows with the following titles" not in prompt

    def test_no_dedup_section_when_empty_list(self):
        agent = ScopeAgent(model="test", role="Controller")
        prompt = agent.build_user_prompt(count=3, previously_generated=[])
        assert "Do NOT generate workflows with the following titles" not in prompt

    def test_includes_dedup_section(self):
        agent = ScopeAgent(model="test", role="Controller")
        prompt = agent.build_user_prompt(count=3, previously_generated=["Task A", "Task B"])
        assert "Do NOT generate workflows with the following titles" in prompt
        assert "- Task A" in prompt
        assert "- Task B" in prompt


class TestScopeWorkflow:
    def test_valid_workflow(self):
        wf = ScopeWorkflow(**SAMPLE_WORKFLOW)
        assert wf.role == "FP&A Analyst"
        assert wf.frequency == "monthly"
        assert wf.recurring is True

    def test_invalid_frequency(self):
        data = {**SAMPLE_WORKFLOW, "frequency": "biweekly"}
        with pytest.raises(ValidationError):
            ScopeWorkflow(**data)

    def test_invalid_complexity(self):
        data = {**SAMPLE_WORKFLOW, "complexity": "extreme"}
        with pytest.raises(ValidationError):
            ScopeWorkflow(**data)

    def test_missing_required_field(self):
        data = {k: v for k, v in SAMPLE_WORKFLOW.items() if k != "task_title"}
        with pytest.raises(ValidationError):
            ScopeWorkflow(**data)


class TestScopeAgentOutput:
    def test_valid_output(self):
        out = ScopeAgentOutput(workflows=[ScopeWorkflow(**SAMPLE_WORKFLOW)])
        assert len(out.workflows) == 1

    def test_empty_workflows(self):
        out = ScopeAgentOutput(workflows=[])
        assert len(out.workflows) == 0

    def test_round_trip_json(self):
        out = ScopeAgentOutput(workflows=[ScopeWorkflow(**SAMPLE_WORKFLOW)])
        raw = json.dumps(out.model_dump())
        restored = ScopeAgentOutput.model_validate(json.loads(raw))
        assert restored.workflows[0].task_title == SAMPLE_WORKFLOW["task_title"]
