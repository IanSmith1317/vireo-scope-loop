from unittest.mock import MagicMock, patch

from agents.base_agent import BaseAgent
from config import MAX_TOKENS
from tests.conftest import make_text_block, make_tool_use_block, make_api_response


class TestBaseAgentInit:
    def test_default_max_tokens(self):
        agent = BaseAgent(model="test-model")
        assert agent.model == "test-model"
        assert agent.max_tokens == MAX_TOKENS

    def test_custom_max_tokens(self):
        agent = BaseAgent(model="test-model", max_tokens=2048)
        assert agent.max_tokens == 2048

    def test_none_max_tokens_keeps_default(self):
        agent = BaseAgent(model="test-model", max_tokens=None)
        assert agent.max_tokens == MAX_TOKENS


class TestBuildPayload:
    def test_basic_payload(self):
        agent = BaseAgent(model="test-model")
        payload = agent.build_payload("Hello")
        assert payload["model"] == "test-model"
        assert payload["max_tokens"] == MAX_TOKENS
        assert payload["messages"] == [{"role": "user", "content": "Hello"}]
        assert "system" not in payload
        assert "tools" not in payload

    def test_with_system_prompt(self):
        agent = BaseAgent(model="test-model")
        agent.system_prompt = "You are helpful."
        payload = agent.build_payload("Hello")
        assert payload["system"] == "You are helpful."

    def test_with_tools(self):
        agent = BaseAgent(model="test-model")
        agent.tools = [{"name": "test_tool"}]
        payload = agent.build_payload("Hello")
        assert payload["tools"] == [{"name": "test_tool"}]

    def test_with_system_prompt_and_tools(self):
        agent = BaseAgent(model="test-model")
        agent.system_prompt = "System"
        agent.tools = [{"name": "t"}]
        payload = agent.build_payload("Hi")
        assert "system" in payload
        assert "tools" in payload


class TestAsk:
    def test_returns_text(self, mock_anthropic):
        mock_anthropic.messages.create.return_value = make_api_response("hello world")
        agent = BaseAgent(model="test-model")
        result = agent.ask("prompt")
        assert result == "hello world"
        mock_anthropic.messages.create.assert_called_once()

    def test_concatenates_multiple_text_blocks(self, mock_anthropic):
        msg = MagicMock()
        msg.content = [make_text_block("part1"), make_text_block("part2")]
        mock_anthropic.messages.create.return_value = msg
        agent = BaseAgent(model="test-model")
        assert agent.ask("prompt") == "part1part2"

    def test_skips_non_text_blocks(self, mock_anthropic):
        msg = MagicMock()
        msg.content = [make_tool_use_block(), make_text_block("only text")]
        mock_anthropic.messages.create.return_value = msg
        agent = BaseAgent(model="test-model")
        assert agent.ask("prompt") == "only text"

    def test_empty_content(self, mock_anthropic):
        msg = MagicMock()
        msg.content = []
        mock_anthropic.messages.create.return_value = msg
        agent = BaseAgent(model="test-model")
        assert agent.ask("prompt") == ""
