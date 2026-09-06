"""Voice Profile — Novel-Engine 引导式访谈捕获作者声音

流程：8 问访谈 → LLM 提取结构化档案 → 持久化 → 注入生成指令。
LLM 不可用时提供规则式降级（从用户已写文本统计近似档案）。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from core.llm_engine import get_llm_engine

VOICE_INTERVIEW_QUESTIONS = [
    "你最喜欢的作家是谁？为什么？",
    "读一段你最喜欢的小说开头。",
    "你的句子通常偏短还是偏长？",
    "你喜欢用对话还是叙述推动故事？",
    "你的角色通常更内向还是外向？",
    "你偏好快节奏还是慢节奏？",
    "你常用第一人称还是第三人称？",
    "你的对话风格是直接的还是含蓄的？",
]

_VOICE_FIELDS = (
    "sentence_rhythm",
    "vocabulary_level",
    "dialogue_style",
    "pacing",
    "pov_preference",
    "tone_preference",
    "description_style",
    "dialogue_ratio_target",
)


@dataclass
class VoiceProfile:
    sentence_rhythm: str = ""  # "短句为主，偶尔长句"
    vocabulary_level: str = ""  # "通俗，偶尔文言"
    dialogue_style: str = ""  # "潜台词多，直接表达少"
    pacing: str = ""  # "快慢交替"
    pov_preference: str = ""  # "第三人称限知"
    tone_preference: str = ""  # "冷静克制"
    description_style: str = ""  # "感官细节"
    dialogue_ratio_target: float = 0.3
    source: str = "interview"  # interview / heuristic

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> VoiceProfile:
        data = json.loads(raw) if raw else {}
        data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**data)

    def to_prompt(self) -> str:
        """转生成指令段（空字段自动跳过）"""
        parts = []
        if self.sentence_rhythm:
            parts.append(f"句式节奏：{self.sentence_rhythm}")
        if self.dialogue_style:
            parts.append(f"对话风格：{self.dialogue_style}")
        if self.pov_preference:
            parts.append(f"人称视角：{self.pov_preference}")
        if self.tone_preference:
            parts.append(f"整体基调：{self.tone_preference}")
        if self.description_style:
            parts.append(f"描写偏好：{self.description_style}")
        if self.pacing:
            parts.append(f"节奏偏好：{self.pacing}")
        if self.dialogue_ratio_target:
            parts.append(f"对话占比目标：约{self.dialogue_ratio_target:.0%}")
        if not parts:
            return ""
        return "## 作者声音（Voice Profile）\n" + "；".join(parts)


class VoiceProfileInterview:
    """引导式访谈 → LLM 提取 → VoiceProfile"""

    def get_questions(self) -> list[str]:
        return list(VOICE_INTERVIEW_QUESTIONS)

    def extract_from_answers(self, answers: list[str]) -> VoiceProfile:
        """从 8 问回答提取结构化档案（LLM，降级规则式）"""
        llm = get_llm_engine()
        if llm.available() and answers:
            prompt = (
                "根据以下作者访谈回答，提取结构化写作风格档案。\n"
                "输出 JSON（只输出 JSON）：\n"
                '{"sentence_rhythm": "", "vocabulary_level": "", '
                '"dialogue_style": "", "pacing": "", "pov_preference": "", '
                '"tone_preference": "", "description_style": "", '
                '"dialogue_ratio_target": 0.3}\n\n'
                + "\n".join(f"Q{i + 1}: {a}" for i, a in enumerate(answers))
            )
            raw = llm.generate_chapter(prompt, {"characters": []}, word_target=400)
            if raw:
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(0))
                        data = {k: v for k, v in data.items() if k in _VOICE_FIELDS}
                        # 关键字段非空才采用（防空档案穿透）
                        if data and (data.get("pov_preference") or data.get("sentence_rhythm")):
                            return VoiceProfile(source="interview", **data)
                    except json.JSONDecodeError:
                        pass
        return self._heuristic_profile("\n".join(answers))

    def extract_from_text(self, text: str) -> VoiceProfile:
        """降级路径：从作者已写文本统计近似档案"""
        if not text or len(text.strip()) < 60:
            # 信息不足：返回默认档案（不猜 POV）
            return VoiceProfile(source="heuristic")
        return self._heuristic_profile(text)

    def _heuristic_profile(self, text: str) -> VoiceProfile:
        sents = [s for s in re.split(r"[。！？]", text) if len(s.strip()) > 2]
        avg_len = sum(len(s) for s in sents) / max(len(sents), 1)
        dialogue_lines = sum(1 for ln in text.splitlines() if any(m in ln for m in '「」""'))
        total_lines = max(len([ln for ln in text.splitlines() if ln.strip()]), 1)
        ratio = min(dialogue_lines / total_lines, 1.0)
        pov = "第一人称" if text.count("我") > text.count("他") * 0.8 else "第三人称"
        return VoiceProfile(
            sentence_rhythm="短句为主"
            if avg_len < 20
            else ("长句为主" if avg_len > 40 else "长短句均衡"),
            dialogue_style="对话偏多"
            if ratio > 0.4
            else ("叙述为主" if ratio < 0.1 else "对话叙述均衡"),
            pacing="快节奏" if avg_len < 18 else ("慢节奏" if avg_len > 42 else "中速"),
            pov_preference=pov,
            dialogue_ratio_target=round(ratio, 2),
            source="heuristic",
        )
