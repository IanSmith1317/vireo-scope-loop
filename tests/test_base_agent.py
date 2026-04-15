import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_clients_start_as_none(self):
        agent = BaseAgent(model="test-model")
        assert agent._sync_client is None
        assert agent._async_client is None

    def test_cache_system_prompt_default_false(self):
        agent = BaseAgent(model="test-model")
        assert agent.cache_system_prompt is False


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

    def test_with_system_prompt_cached(self):
        agent = BaseAgent(model="test-model")
        agent.system_prompt = "You are helpful."
        agent.cache_system_prompt = True
        payload = agent.build_payload("Hello")
        assert isinstance(payload["system"], list)
        assert len(payload["system"]) == 1
        block = payload["system"][0]
        assert block["type"] == "text"
        assert block["text"] == "You are helpful."
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_cache_flag_ignored_without_system_prompt(self):
        agent = BaseAgent(model="test-model")
        agent.cache_system_prompt = True
        payload = agent.build_payload("Hello")
        assert "system" not in payload

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


class TestClientReuse:
    def test_sync_client_created_once(self, mock_anthropic):
        sync_client, _ = mock_anthropic
        agent = BaseAgent(model="test-model")
        c1 = agent._get_sync_client()
        c2 = agent._get_sync_client()
        assert c1 is c2

    def test_async_client_created_once(self, mock_anthropic):
        _, async_client = mock_anthropic
        agent = BaseAgent(model="test-model")
        c1 = agent._get_async_client()
        c2 = agent._get_async_client()
        assert c1 is c2


class TestAsk:
    def test_returns_text(self, mock_anthropic):
        sync_client, _ = mock_anthropic
        sync_client.messages.create.return_value = make_api_response("hello world")
        agent = BaseAgent(model="test-model")
        result = agent.ask("prompt")
        assert result == "hello world"
        sync_client.messages.create.assert_called_once()

    def test_concatenates_multiple_text_blocks(self, mock_anthropic):
        sync_client, _ = mock_anthropic
        msg = MagicMock()
        msg.content = [make_text_block("part1"), make_text_block("part2")]
        sync_client.messages.create.return_value = msg
        agent = BaseAgent(model="test-model")
        assert agent.ask("prompt") == "part1part2"

    def test_skips_non_text_blocks(self, mock_anthropic):
        sync_client, _ = mock_anthropic
        msg = MagicMock()
        msg.content = [make_tool_use_block(), make_text_block("only text")]
        sync_client.messages.create.return_value = msg
        agent = BaseAgent(model="test-model")
        assert agent.ask("prompt") == "only text"

    def test_empty_content(self, mock_anthropic):
        sync_client, _ = mock_anthropic
        msg = MagicMock()
        msg.content = []
        sync_client.messages.create.return_value = msg
        agent = BaseAgent(model="test-model")
        assert agent.ask("prompt") == ""


class TestAskAsync:
    async def test_returns_text(self, mock_anthropic):
        _, async_client = mock_anthropic
        async_client.messages.create = AsyncMock(return_value=make_api_response("async hello"))
        agent = BaseAgent(model="test-model")
        result = await agent.ask_async("prompt")
        assert result == "async hello"
        async_client.messages.create.assert_awaited_once()

    async def test_concatenates_multiple_text_blocks(self, mock_anthropic):
        _, async_client = mock_anthropic
        msg = MagicMock()
        msg.content = [make_text_block("a"), make_text_block("b")]
        async_client.messages.create = AsyncMock(return_value=msg)
        agent = BaseAgent(model="test-model")
        assert await agent.ask_async("prompt") == "ab"

    async def test_skips_non_text_blocks(self, mock_anthropic):
        _, async_client = mock_anthropic
        msg = MagicMock()
        msg.content = [make_tool_use_block(), make_text_block("only")]
        async_client.messages.create = AsyncMock(return_value=msg)
        agent = BaseAgent(model="test-model")
        assert await agent.ask_async("prompt") == "only"

    async def test_empty_content(self, mock_anthropic):
        _, async_client = mock_anthropic
        msg = MagicMock()
        msg.content = []
        async_client.messages.create = AsyncMock(return_value=msg)
        agent = BaseAgent(model="test-model")
        assert await agent.ask_async("prompt") == ""
