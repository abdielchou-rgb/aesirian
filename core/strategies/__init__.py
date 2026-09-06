"""
叙事提示模板 — Æsirian 策略模块入口

"""

from core.strategies.narrative_prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
    build_user_prompt_from_constraints,
)

__all__ = [
    "SYSTEM_PROMPT",
    "build_user_prompt",
    "build_user_prompt_from_constraints",
]
