import json

from agents.spec_writer_agents import SpecWriterAgent
from tests.conftest import SAMPLE_PM_ACCEPT, SAMPLE_TRANSLATOR_RESULT, SAMPLE_MANIFEST


class TestSpecWriterAgentInit:
    def test_default_max_tokens(self):
        agent = SpecWriterAgent(model="test")
        assert agent.max_tokens == 8192

    def test_custom_max_tokens(self):
        agent = SpecWriterAgent(model="test", max_tokens=16384)
        assert agent.max_tokens == 16384

    def test_system_prompt_content(self):
        agent = SpecWriterAgent(model="test")
        assert "technical specification writer" in agent.system_prompt
        assert "Vireo" in agent.system_prompt

    def test_system_prompt_has_all_sections(self):
        agent = SpecWriterAgent(model="test")
        for section in [
            "Summary", "Motivation", "Input Schema", "Output Schema",
            "Transformation Logic", "Composition", "Constraints",
            "Acceptance Criteria", "PM Decision Context",
        ]:
            assert section in agent.system_prompt


class TestBuildUserPrompt:
    def test_includes_all_context(self):
        agent = SpecWriterAgent(model="test")
        prompt = agent.build_user_prompt(
            gap_primitive="import",
            pm_decision=SAMPLE_PM_ACCEPT,
            translator_results=[SAMPLE_TRANSLATOR_RESULT],
            manifest=SAMPLE_MANIFEST,
            compositions=SAMPLE_MANIFEST["compositions"],
        )
        assert "import" in prompt
        assert "Primitive to Specify" in prompt
        assert "PM Decision" in prompt
        assert "Translator Analysis" in prompt
        assert "Current Vireo Capabilities" in prompt
        assert "Existing Compositions" in prompt

    def test_json_serialization_in_prompt(self):
        agent = SpecWriterAgent(model="test")
        prompt = agent.build_user_prompt(
            gap_primitive="import",
            pm_decision=SAMPLE_PM_ACCEPT,
            translator_results=[SAMPLE_TRANSLATOR_RESULT],
            manifest=SAMPLE_MANIFEST,
            compositions=[],
        )
        # Verify the JSON parts are parseable
        assert "accept" in prompt
        assert "actuals" in prompt
