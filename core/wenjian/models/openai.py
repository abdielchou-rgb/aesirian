"""OpenAI model provider."""

import json
import httpx
from .base import BaseModelProvider, ModelResponse


class OpenAIProvider(BaseModelProvider):
    def chat(self, system: str = "", messages=None, max_tokens=4096, temperature=0.3) -> ModelResponse:
        if messages is None:
            messages = []
        full_messages = [{"role": "system", "content": system}] + messages if system else messages
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": full_messages,
        }
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        with httpx.Client(timeout=120) as client:
            resp = client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return ModelResponse(
            content=data["choices"][0]["message"]["content"],
            model=data["model"],
            provider="openai",
            usage={"input_tokens": data["usage"]["prompt_tokens"], "output_tokens": data["usage"]["completion_tokens"]},
        )

    def chat_json(self, system: str = "", messages=None, max_tokens=4096, temperature=0.3) -> dict:
        resp = self.chat(system, messages, max_tokens, temperature)
        text = resp.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()
        return json.loads(text)


from .base import registry as _reg
_reg.register("openai", OpenAIProvider)