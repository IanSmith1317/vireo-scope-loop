from anthropic import Anthropic, AsyncAnthropic
from config import MAX_TOKENS, API_KEY


class BaseAgent:
    max_tokens = MAX_TOKENS
    api_key = API_KEY
    system_prompt = None
    tools = None
    cache_system_prompt = False

    def __init__(self, model: str, max_tokens: int | None = None):
        self.model = model
        if max_tokens is not None:
            self.max_tokens = max_tokens
        self._sync_client: Anthropic | None = None
        self._async_client: AsyncAnthropic | None = None

    def _get_sync_client(self) -> Anthropic:
        if self._sync_client is None:
            self._sync_client = Anthropic(api_key=self.api_key)
        return self._sync_client

    def _get_async_client(self) -> AsyncAnthropic:
        if self._async_client is None:
            self._async_client = AsyncAnthropic(api_key=self.api_key)
        return self._async_client

    def build_payload(self, user_prompt: str):
        payload = {
            "max_tokens": self.max_tokens,
            "model": self.model,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }

        if self.system_prompt:
            if self.cache_system_prompt:
                payload["system"] = [{
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }]
            else:
                payload["system"] = self.system_prompt

        if self.tools:
            payload["tools"] = self.tools

        return payload

    @staticmethod
    def _extract_text(message) -> str:
        text_parts = [
            block.text for block in message.content
            if getattr(block, "type", None) == "text"
        ]
        return "".join(text_parts)

    def ask(self, user_prompt: str) -> str:
        client = self._get_sync_client()
        message = client.messages.create(
            **self.build_payload(user_prompt=user_prompt)
        )
        return self._extract_text(message)

    async def ask_async(self, user_prompt: str) -> str:
        client = self._get_async_client()
        message = await client.messages.create(
            **self.build_payload(user_prompt=user_prompt)
        )
        return self._extract_text(message)
