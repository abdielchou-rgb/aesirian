"""Anthropic model provider."""

import json

import httpx

from .base import BaseModelProvider, ModelResponse


class AnthropicProvider(BaseModelProvider):
    def chat(
        self, system: str = "", messages=None, max_tokens=4096, temperature=0.3
    ) -> ModelResponse:
        if messages is None:
            messages = []
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": messages,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        url = self.base_url or "https://api.anthropic.com/v1/messages"
        with httpx.Client(timeout=120) as client:
            resp = client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return ModelResponse(
            content=data["content"][0]["text"],
            model=data["model"],
            provider="anthropic",
            usage={
                "input_tokens": data["usage"]["input_tokens"],
                "output_tokens": data["usage"]["output_tokens"],
            },
        )

    def chat_json(self, system: str = "", messages=None, max_tokens=4096, temperature=0.3) -> dict:
        resp = self.chat(system, messages, max_tokens, temperature)
        # Strip markdown fence if present
        text = resp.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()
        return json.loads(text)


from .base import registry as _reg

_reg.register("anthropic", AnthropicProvider)
