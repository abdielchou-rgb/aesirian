"""文鉴 WenJian 配置管理。"""

import os
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    provider: str  # "anthropic" | "openai" | "ollama"
    model: str
    api_key: str | None = None
    base_url: str | None = None


@dataclass
class ProjectConfig:
    title: str = "untitled"
    platform: str = "webnovel"
    genre: str = "xianxia_modern"
    estimated_chapters: int = 30


@dataclass
class WenJianConfig:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    models: dict[str, ModelConfig] = field(default_factory=dict)
    api_keys: dict[str, str] = field(default_factory=dict)
    ledger_dir: str = "./wenjian_ledger"
    verbose: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "WenJianConfig":
        cfg = cls()
        if "project" in data:
            cfg.project = ProjectConfig(**data["project"])
        if "ledger" in data:
            cfg.ledger_dir = data["ledger"].get("directory", "./wenjian_ledger")
        models = {}
        for tier, mc in data.get("models", {}).items():
            models[tier] = ModelConfig(**mc)
        cfg.models = models
        cfg.api_keys = data.get("api_keys", {})
        cfg.verbose = data.get("verbose", False)
        return cfg

    @classmethod
    def load(cls, path: str) -> "WenJianConfig":
        import yaml

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    def get_model(self, tier: str) -> ModelConfig:
        mc = self.models.get(tier)
        if mc is None:
            raise ValueError(f"Model tier '{tier}' not configured")
        if not mc.api_key and mc.provider != "ollama":
            mc.api_key = self.api_keys.get(
                mc.provider, os.environ.get(f"{mc.provider.upper()}_API_KEY", "")
            )
        return mc

    DEFAULT_CONFIG_YAML = """project:
  title: "untitled"
  platform: webnovel
  genre: xianxia_modern
  estimated_chapters: 30

models:
  tier_1_light:
    provider: openai
    model: gpt-4o-mini
  tier_2_medium:
    provider: anthropic
    model: claude-sonnet-4-20250514
  tier_3_strong:
    provider: anthropic
    model: claude-haiku-4-20250514
  tier_4_expert:
    provider: anthropic
    model: claude-opus-4-20250514

api_keys:
  anthropic: ""
  openai: ""

ledger:
  directory: "./wenjian_ledger"
"""
