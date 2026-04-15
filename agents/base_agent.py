from anthropic import Anthropic
from config import MAX_TOKENS, API_KEY


class BaseAgent:
    max_tokens = MAX_TOKENS
    api_key = API_KEY
    system_prompt = None
    tools = None

    def __init__(self, model: str, max_tokens: int | None = None):
        self.model = model
        if max_tokens is not None:
            self.max_tokens = max_tokens

    def build_payload(self, user_prompt:str):
        payload = {
            "max_tokens": self.max_tokens,
            "model": self.model,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }

        if self.system_prompt:
            payload["system"] = self.system_prompt

        if self.tools:
            payload["tools"] = self.tools

        return payload

    def ask(self, user_prompt: str):
        client = Anthropic(
        api_key=self.api_key
        )

        message = client.messages.create(
            **self.build_payload(user_prompt=user_prompt)
        )

        text_parts = [
            block.text for block in message.content
            if getattr(block, "type", None) == "text"
        ]
        return "".join(text_parts)

