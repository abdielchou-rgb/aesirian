from __future__ import annotations

"""语言门禁 — MRU 单元、POV 纪律、斯蒂芬金语言检测。

MRU 单元（Swain《卖座小说技巧》）：
  人的认知反应链：刺激→情感→思考→动作→言语。
  检查写作是否跳过了必要环节。

POV 纪律（Le Guin《修辞之术》）：
  无意识 POV 切换、角色不可能知道的信息、全知视角泄露。

斯蒂芬金语言（King《写作这回事》）：
  副词检测、被动语态检测、赘词检测。
"""

import re

from wenjian.models import GateSeverity

from .base import BaseGate


class LANG01_MRUChain(BaseGate):
    """MRU 反应链完整性检测。"""

    gate_id = "LANG-01"
    name = "MRU 反应链门禁"
    description = "人的认知反应链：刺激→情感→思考→动作→言语，不应跳"
    severity = GateSeverity.WARN

    def evaluate(self, text: str) -> GateResult:
        """检查文本中是否包含完整的反应链元素。"""
        has_stimulus = bool(re.search(r"(忽然|突然|看到|听到|闻到|感觉到|发现)", text))
        has_feeling = bool(re.search(r"(心里一|心头|心脏|呼吸|血液)", text))
        has_thought = bool(re.search(r"(心想|暗道|想道|意识到|明白了)", text))
        has_action = bool(re.search(r"(猛地|立刻|迅速|转身|跳起|冲出)", text))
        has_speech = bool(re.search(r"[「「『『]", text))

        score = sum([has_stimulus, has_feeling, has_thought, has_action, has_speech])
        if score < 3:
            return self.fail_result(
                message=f"MRU 反应链完整性 {score}/5——读者可能不理解角色的反应逻辑",
                details={
                    "score": score,
                    "elements": {
                        "stimulus": has_stimulus,
                        "feeling": has_feeling,
                        "thought": has_thought,
                        "action": has_action,
                        "speech": has_speech,
                    },
                },
            )
        return self.pass_result(details={"score": score})


class LANG02_POVDiscipline(BaseGate):
    """POV 纪律检测。"""

    gate_id = "LANG-02"
    name = "POV 纪律门禁"
    description = "检测无意识 POV 切换和角色不可能知道的信息"
    severity = GateSeverity.WARN

    def evaluate(self, text: str) -> GateResult:
        issues = []

        # 检测全知视角泄露模式
        omniscient_patterns = [
            r"他不知道的是",
            r"他不知道",
            r"他并不知道",
            r"他没想到的是",
            r"他永远也不会知道",
            r"而在另一个地方",
            r"与此同时",
        ]
        issues.extend(
            f"全知视角泄露：'{pattern}'——当前 POV 角色不可能知道这件事"
            for pattern in omniscient_patterns
            if re.search(pattern, text)
        )

        # 检测头内互换
        head_hop_patterns = [
            r"他想.*?[。！？].*?他[但可]又想",
        ]
        issues.extend(
            "可能在同一个段落内切换了角色视角"
            for pattern in head_hop_patterns
            if re.search(pattern, text)
        )

        if issues:
            return self.fail_result(message="；".join(issues[:2]), details={"issues": issues})
        return self.pass_result()


class LANG03_AdverbCheck(BaseGate):
    """副词滥用检测（Stephen King）。"""

    gate_id = "LANG-03"
    name = "副词滥用门禁"
    description = "对话标签中的副词通常不需要"
    severity = GateSeverity.WARN

    ADVERBS = [
        "悄悄",
        "默默",
        "缓缓",
        "轻轻",
        "狠狠",
        "冷冷",
        "淡淡",
        "静静",
        "慢慢",
        "快速",
        "迅速",
        "突然",
        "愤怒",
        "悲伤",
        "温柔",
        "冷漠",
        "冰冷",
    ]

    def evaluate(self, text: str) -> GateResult:
        count = sum(1 for adv in self.ADVERBS if adv in text)
        if count > 3:
            return self.fail_result(
                message=f"副词/情绪词出现 {count} 次，Stephen King 法则：对话标签中的副词通常是不信任读者的表现",
                details={"adverb_count": count, "threshold": 3},
            )
        return self.pass_result(details={"adverb_count": count})


class LANG04_PassiveVoice(BaseGate):
    """被动语态检测。"""

    gate_id = "LANG-04"
    name = "被动语态门禁"
    description = "被动语态弱化叙事力量"
    severity = GateSeverity.WARN

    def evaluate(self, passive_count: int, active_count: int) -> GateResult:
        if active_count + passive_count == 0:
            return self.pass_result()
        ratio = passive_count / (active_count + passive_count)
        if ratio > 0.3:
            return self.fail_result(
                message=f"被动语态占比 {ratio:.0%}，建议不超过 30%——被动语态弱化叙事力量",
                details={
                    "passive": passive_count,
                    "active": active_count,
                    "ratio": round(ratio, 2),
                },
            )
        return self.pass_result(details={"ratio": round(ratio, 2)})


class LANG05_FillerWords(BaseGate):
    """赘词检测。"""

    gate_id = "LANG-05"
    name = "赘词检测门禁"
    description = "检测不必要的冗词（King法则：删掉所有能删的词）"
    severity = GateSeverity.WARN

    FILLERS = [
        "基本上",
        "实际上",
        "本质上",
        "非常",
        "真的",
        "有点",
        "某种",
        "似乎",
        "好像",
        "几乎",
        "开始",
        "然后",
        "于是",
        "接着",
    ]

    def evaluate(self, filler_count: int, total_words: int) -> GateResult:
        density = filler_count / max(total_words / 1000, 1)
        if density > 2:
            return self.fail_result(
                message=f"赘词密度 {density:.1f}/千字，建议控制在 2/千字以下",
                details={"filler_count": filler_count, "density": round(density, 1)},
            )
        return self.pass_result(details={"density": round(density, 1)})
