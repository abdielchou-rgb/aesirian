"""
LLM 引擎 — 接入 DeepSeek/Claude 生成续写建议和场景文本

⚠️ DEPRECATED（M1-4 · engineering-plan-v11.md §3.1 M1-4）
    本模块为旧单发式 LLM 引擎（requests 直连多供应商 + 规则降级）。
    统一生成入口为 core/pydantic_ai_engine.py（Pydantic AI 门面：
    Agent / 结构化输出 / 多供应商 gateway / 流式 / 工具调用）。
    本模块仅因既有调用方保留兼容（bridge/api_server、core/orchestrator、
    planning、generation、style/voice_profile、旧 mcp_server 等），
    不再承担新入口职责，也不得新增第二套生成路径；
    新代码统一走 pydantic_ai_engine 门面；
    计划于 V1.2 由薄适配（pydantic_ai_engine.LLMEngineCompat）完全接管后移除。

设计原则：
1. 纯规则引擎已经能提供基础建议（ToM张力点+冷却矩阵+读者模型）
2. LLM 引擎作为"增强层"——在规则建议基础上添加真正的创作性建议
3. 可降级：LLM 不可用时自动回退到纯规则模式
4. 建议结构统一为 {type, text, rationale, source} 四字段
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """LLM提供者配置"""

    provider: str = "deepseek"  # deepseek / openai / anthropic / ollama
    api_key: str = ""
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.7
    max_tokens: int = 1024


# 合法建议类型
_SUGGESTION_TYPES = frozenset({"tension", "character", "reader", "pattern", "llm"})


@dataclass
class LLMSuggestion:
    """LLM生成的续写建议"""

    type: str = "llm"  # tension / character / reader / pattern / llm
    text: str = ""  # 续写开头（max 40字）
    rationale: str = ""  # 为什么（max 20字）
    source: str = ""  # 方法论来源

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "text": self.text[:40],
            "rationale": self.rationale[:20],
            "source": self.source[:30] if self.source else "LLM",
        }


class LLMEngine:
    """
    LLM引擎 — 多供应商支持，优雅降级

    环境变量:
      DEEPSEEK_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.configs: list[LLMConfig] = []
        self._init_from_env()

    def _init_from_env(self):
        """从环境变量加载配置"""
        # DeepSeek
        dk_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if dk_key:
            self.configs.append(
                LLMConfig(
                    provider="deepseek",
                    api_key=dk_key,
                    model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
                )
            )

        # OpenAI
        oa_key = os.environ.get("OPENAI_API_KEY", "")
        if oa_key:
            self.configs.append(
                LLMConfig(
                    provider="openai",
                    api_key=oa_key,
                    model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                )
            )

        # 智谱 Zhipu/GLM（OpenAI 兼容格式）
        zp_key = os.environ.get("ZHIPU_API_KEY", "")
        if zp_key:
            self.configs.append(
                LLMConfig(
                    provider="zhipu",
                    api_key=zp_key,
                    model=os.environ.get("ZHIPU_MODEL", "glm-4-flash"),
                    base_url="https://open.bigmodel.cn/api/paas/v4",
                )
            )

        # Anthropic
        an_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if an_key:
            self.configs.append(
                LLMConfig(
                    provider="anthropic",
                    api_key=an_key,
                    model=os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
                )
            )

        # Ollama 本地
        ollama_host = os.environ.get("OLLAMA_HOST", "")
        if ollama_host:
            self.configs.append(
                LLMConfig(
                    provider="ollama",
                    api_key="ollama",
                    model=os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
                    base_url=f"{ollama_host}/v1",
                )
            )

    def available(self) -> bool:
        """是否有可用的LLM"""
        return len(self.configs) > 0

    def _call_llm(self, messages: list[dict], config: LLMConfig) -> str | None:
        """调用LLM API"""
        try:
            if config.provider == "ollama":
                import requests

                r = requests.post(
                    config.base_url + "/chat/completions",
                    json={
                        "model": config.model,
                        "messages": messages,
                        "temperature": config.temperature,
                        "max_tokens": config.max_tokens,
                    },
                    timeout=30,
                )
                return r.json()["choices"][0]["message"]["content"]
            import requests

            r = requests.post(
                config.base_url + "/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.model,
                    "messages": messages,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                },
                timeout=30,
            )
            return r.json()["choices"][0]["message"]["content"]
        except Exception:
            return None

    def generate_suggestions(self, context: dict) -> list[LLMSuggestion]:
        """基于上下文生成3-5个续写建议

        Parameters
        ----------
        context : dict
            包含 premise, characters, tension_points,
            transportation_trend, current_chapter 等字段

        Returns
        -------
        list[LLMSuggestion]
            解析后的建议列表（3-5条），失败时返回空列表
        """
        if not self.available():
            return []

        from core.strategies.narrative_prompt import (
            SYSTEM_PROMPT,
            build_user_prompt,
        )

        user_prompt = build_user_prompt(
            premise=context.get("premise", ""),
            characters=context.get("characters", []),
            tensions=context.get("tension_points", []),
            trends={"transportation_trend": context.get("transportation_trend", "→ 平稳")},
            chapter=context.get("current_chapter", 0),
        )

        config = self.configs[0]

        for attempt in range(min(2, len(self.configs))):
            response = self._call_llm(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                config,
            )

            if response:
                suggestions = self._parse_response(response)
                if suggestions:
                    return suggestions

            # 尝试下一个配置
            if len(self.configs) > attempt + 1:
                config = self.configs[attempt + 1]

        return []

    def _parse_response(self, text: str) -> list[LLMSuggestion]:
        """解析LLM响应为结构化建议列表"""
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if not json_match:
            return []

        try:
            items = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return []

        suggestions: list[LLMSuggestion] = []
        for item in items[:5]:
            if not isinstance(item, dict):
                continue
            raw_type = item.get("type", "llm")
            if raw_type not in _SUGGESTION_TYPES:
                raw_type = "llm"
            suggestions.append(
                LLMSuggestion(
                    type=raw_type,
                    text=str(item.get("text", ""))[:40],
                    rationale=str(item.get("rationale", ""))[:20],
                    source=str(item.get("source", "LLM"))[:30],
                )
            )

        return suggestions

    def enhance_scene_constraints(self, rules: dict) -> str:
        """LLM增强的场景约束描述——用于写作提示"""
        if not self.available():
            return ""

        prompt = (
            f"故事当前状态：\n"
            f"张力点：{[t.get('description', '')[:40] for t in rules.get('tension_points', [])]}\n"
            f"角色倾向：{[t.get('action', '')[:30] for t in rules.get('character_tendencies', [])]}\n"
            f"推荐叙事模式：{rules.get('recommended_patterns', [])}\n\n"
            f"请用一句话描述这场戏应该怎么推进（强调角色信念和情感变化，不写具体对话）："
        )

        config = self.configs[0] if self.configs else None
        if not config:
            return ""
        return (
            self._call_llm(
                [
                    {
                        "role": "system",
                        "content": "你是一个叙事设计师。用一句不超过40字的话描述一场戏的情感核心。",
                    },
                    {"role": "user", "content": prompt},
                ],
                config,
            )
            or ""
        )

    def generate_chapter(
        self, premise: str, context: dict | None = None, word_target: int = 300
    ) -> str:
        """从一句话灵感生成完整章节文本（200-500字）

        Parameters
        ----------
        premise : str
            一句话灵感/前提句
        context : dict, optional
            项目上下文（characters, tension_points, current_chapter 等）
        word_target : int
            目标字数（默认300，范围200-500）

        Returns
        -------
        str
            生成的章节文本；LLM不可用时返回空串
        """
        if not self.available():
            return ""

        context = context or {}
        characters = context.get("characters", [])
        tensions = context.get("tension_points", [])
        chapter = context.get("current_chapter", 1)

        char_desc = "、".join(characters[:6]) if characters else "主角"
        tension_desc = ""
        if tensions:
            top = tensions[0]
            tension_desc = f"核心张力：{str(top.get('description', ''))[:60]}\n"

        system_prompt = (
            "你是一位中文小说家。根据用户给定的灵感，写出一段完整的小说正文。"
            "要求：\n"
            "1. 直接输出正文，不要任何标题、解释或元信息\n"
            "2. 有具体的场景、动作、对话或心理描写，不要空洞概述\n"
            "3. 结尾留一个钩子，让读者想继续读下去\n"
            f"4. 字数约{word_target}字"
        )

        user_prompt = (
            f"灵感：{premise}\n"
            f"出场角色：{char_desc}\n"
            f"第{chapter}章\n"
            f"{tension_desc}"
            "请写出这一章的正文。"
        )

        config = self.configs[0]
        for attempt in range(min(2, len(self.configs))):
            response = self._call_llm(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                config,
            )
            # 基本质量门槛：至少100字才算成功
            if response and len(response.strip()) >= 100:
                return response.strip()
            if len(self.configs) > attempt + 1:
                config = self.configs[attempt + 1]

        return ""

    def generate_variant(
        self,
        context_text: str,
        instruction: str,
        word_target: int = 500,
        temperature: float | None = None,
    ) -> str:
        """多变体生成（Sudowrite 模式）：注入完整上下文 + 生成指令 + 温度扰动

        Returns: 生成的正文；失败返回空串
        """
        if not self.available():
            return ""
        system_prompt = (
            "你是一位中文小说家。基于给定的故事上下文，写出接下来的正文。"
            "要求：\n"
            "1. 直接输出正文，不要标题、解释、元信息\n"
            "2. 与上下文的角色信念、语气、节奏保持连续\n"
            "3. 有具体场景与感官细节，结尾留钩子\n"
            f"4. 字数约{word_target}字"
        )
        user_prompt = f"{context_text}\n\n{instruction}" if context_text else instruction
        for _i, config in enumerate(self.configs[:2]):
            cfg = config
            if temperature is not None and hasattr(cfg, "temperature"):
                import copy as _copy

                cfg = _copy.copy(cfg)
                cfg.temperature = temperature
            response = self._call_llm(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                cfg,
            )
            if response and len(response.strip()) >= 100:
                return response.strip()
        return ""


# 全局单例
def get_llm_engine() -> LLMEngine:
    """DEPRECATED（M1-4）兼容门面：保留仅供既有调用方使用，不新增消费方。

    统一生成入口为 core.pydantic_ai_engine.get_llm_engine()（Pydantic AI 门面，
    返回 LLMEngineCompat 同构兼容层）。本函数计划于 V1.2 移除。
    """
    return LLMEngine()
