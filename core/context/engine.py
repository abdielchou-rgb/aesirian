"""上下文层级定义 — NovelAI 分层注入 + Morpheus 三层记忆"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class ContextLayer(IntEnum):
    PROJECT = 0  # 项目元信息（始终注入）
    CHARACTERS = 1  # 角色档案（始终注入）
    RECENT = 2  # 最近 N 章摘要（按相关性检索）
    EPISODIC = 3  # 情景记忆（Morpheus L2：章节状态变更）
    DERIVED = 4  # 派生记忆（Morpheus L3：RUNTIME_STATE + OPEN_THREADS）
    USER = 5  # 用户当前输入（最高优先级）


@dataclass
class ContextConfig:
    max_tokens: int = 32000
    layers: dict = field(
        default_factory=lambda: {
            ContextLayer.PROJECT: True,
            ContextLayer.CHARACTERS: True,
            ContextLayer.RECENT: True,
            ContextLayer.EPISODIC: True,
            ContextLayer.DERIVED: True,
            ContextLayer.USER: True,
        }
    )
    recent_chapters: int = 3
    character_detail_level: str = "full"  # full / summary / names_only
    enable_retrieval: bool = True  # Morpheus L2 关键词检索


@dataclass
class AssembledContext:
    """组装结果 + 分层计量（可观测）"""

    text: str = ""
    sections: dict = field(default_factory=dict)  # layer -> section 文本
    token_estimates: dict = field(default_factory=dict)  # layer -> tokens
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "total_tokens": self.total_tokens,
            "layers": {
                k.name: {
                    "tokens": self.token_estimates.get(k.name, 0),
                    "chars": len(self.sections.get(k.name, "")),
                }
                for k in ContextLayer
            },
            "text": self.text,
        }
