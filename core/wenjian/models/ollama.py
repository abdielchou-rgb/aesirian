"""Ollama model provider (local)."""

import json
import httpx
from .base import BaseModelProvider, ModelResponse


class OllamaProvider(BaseModelProvider):
    def __init__(self, model: str, api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key, base_url or "http://localhost:11434")

    def chat(self, system: str = "", messages=None, max_tokens=4096, temperature=0.3) -> ModelResponse:
        if messages is None:
            messages = []
        full_messages = [{"role": "system", "content": system}] + messages if system else messages
        body = {
            "model": self.model,
            "messages": full_messages,
            "options": {"num_predict": max_tokens, "temperature": temperature},
            "stream": False,
        }
        url = f"{self.base_url}/api/chat"
        with httpx.Client(timeout=300) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
        return ModelResponse(
            content=data["message"]["content"],
            model=data.get("model", self.model),
            provider="ollama",
        )

    def chat_json(self, system: str = "", messages=None, max_tokens=4096, temperature=0.3) -> dict:
        resp = self.chat(system, messages, max_tokens, temperature)
        text = resp.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()
        return json.loads(text)


from .base import registry as _reg
_reg.register("ollama", OllamaProvider)