"""Base model provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ModelResponse:
    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})


class BaseModelProvider(ABC):
    def __init__(self, model: str, api_key: str = "", base_url: str = ""):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> ModelResponse: ...

    @abstractmethod
    def chat_json(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> dict: ...


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, type] = {}

    def register(self, name: str, cls: type):
        self._providers[name] = cls

    def create(
        self, name: str, model: str, api_key: str = "", base_url: str = ""
    ) -> BaseModelProvider:
        cls = self._providers.get(name)
        if cls is None:
            raise ValueError(f"Unknown provider: {name}")
        return cls(model, api_key, base_url)


registry = ProviderRegistry()
