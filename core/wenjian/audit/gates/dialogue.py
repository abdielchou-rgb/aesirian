from __future__ import annotations

from wenjian.models import GateResult

"""对话质量门禁 — McKee《对白的解剖》核心原理。

三层对白分析：
  - 表层：角色说了什么（推进剧情/传递信息）
  - 次层：角色真正在表达什么（潜台词、回避、攻击）
  - 深层：对话透露了角色什么（性格、背景、价值观）
"""

from wenjian.models import GateSeverity

from .base import BaseGate


class DLG01_DialogueFunction(BaseGate):
    """每段对话必须有功能。"""

    gate_id = "DLG-01"
    name = "对话功能门禁"
    description = "每段对话必须至少完成一项：推进剧情 / 塑造角色 / 传达信息"
    severity = GateSeverity.WARN

    def evaluate(self, functional_lines: int, total_lines: int) -> GateResult:
        if total_lines < 2:
            return self.pass_result(message="对话过短，跳过检查")
        ratio = functional_lines / total_lines if total_lines else 0
        if ratio < 0.5:
            return self.fail_result(
                message=f"仅 {functional_lines}/{total_lines} 句对话有实质功能（{ratio:.0%}）",
                details={
                    "functional": functional_lines,
                    "total": total_lines,
                    "ratio": round(ratio, 2),
                },
            )
        return self.pass_result(details={"ratio": round(ratio, 2)})


class DLG02_Subtext(BaseGate):
    """对白不能直接说出内心想法。"""

    gate_id = "DLG-02"
    name = "潜台词门禁"
    description = "角色的对白不能直接说出内心真实想法（需通过暗示/回避/动作传递）"
    severity = GateSeverity.WARN

    def evaluate(self, direct_feelings: int, dialogue_lines: int) -> GateResult:
        if dialogue_lines < 2:
            return self.pass_result()
        if direct_feelings > 0:
            return self.fail_result(
                message=f"{direct_feelings} 处角色直接说出了内心感受——建议通过潜台词和动作暗示",
                details={"direct_statements": direct_feelings, "total_lines": dialogue_lines},
            )
        return self.pass_result()


class DLG03_DialogueRhythm(BaseGate):
    """不能连续超过 5 轮纯对话。"""

    gate_id = "DLG-03"
    name = "对话节奏门禁"
    description = "不能连续超过 5 轮对白无动作描写或叙述插入"
    severity = GateSeverity.WARN

    def evaluate(self, max_consecutive_rounds: int) -> GateResult:
        if max_consecutive_rounds > 5:
            return self.fail_result(
                message=f"连续 {max_consecutive_rounds} 轮纯对话无动作穿插——读者会失去场景感",
                details={"consecutive_rounds": max_consecutive_rounds},
            )
        return self.pass_result(details={"max_rounds": max_consecutive_rounds})


class DLG04_InfoDumpDialogue(BaseGate):
    """不能让角色"如你所知"式倾倒信息。"""

    gate_id = "DLG-04"
    name = "信息对话门禁"
    description = "角色对话中不应出现'如你所知'式的信息倾倒"
    severity = GateSeverity.BLOCK

    def evaluate(self, expository_lines: int) -> GateResult:
        if expository_lines > 0:
            return self.fail_result(
                message=f"发现 {expository_lines} 处信息倾倒式对白——角色不应该互相告知已经知道的事",
                details={"expository_lines": expository_lines},
            )
        return self.pass_result()


class DLG05_CharacterVoice(BaseGate):
    """每个角色的说话方式应有区别。"""

    gate_id = "DLG-05"
    name = "角色声线门禁"
    description = "每个主要角色的说话方式应有可辨识的区别——用词、句式、语气"
    severity = GateSeverity.WARN

    def evaluate(self, dialogue_blocks: list[dict]) -> GateResult:
        if len(dialogue_blocks) < 4:
            return self.pass_result(message="对话样本不足")

        # 按角色分组
        voices: dict[str, list[str]] = {}
        for block in dialogue_blocks:
            char = block.get("character", "?")
            text = block.get("text", "")
            if char not in voices:
                voices[char] = []
            voices[char].append(text)

        # 检查是否有角色用词和其他角色完全一样
        if len(voices) >= 2:
            char_keys = list(voices.keys())
            if len(voices[char_keys[0]]) >= 2 and len(voices[char_keys[1]]) >= 2:
                avg_len_0 = sum(len(t) for t in voices[char_keys[0]]) / len(voices[char_keys[0]])
                avg_len_1 = sum(len(t) for t in voices[char_keys[1]]) / len(voices[char_keys[1]])
                if abs(avg_len_0 - avg_len_1) < 2:
                    return self.fail_result(
                        message=f"角色'{char_keys[0]}'和'{char_keys[1]}'的句子长度几乎相同——建议赋予不同说话风格",
                        details={
                            "characters": char_keys[:3],
                            "note": "至少在一个维度上区分：用词/句式/语气/节奏",
                        },
                    )

        return self.pass_result(details={"characters": list(voices.keys())})


class DLG06_ActionInterrupt(BaseGate):
    """对话中应有行为动作穿插。"""

    gate_id = "DLG-06"
    name = "对话动作穿插门禁"
    description = "长段对话中应有动作描写穿插——'说'之外角色还在做什么"
    severity = GateSeverity.WARN

    def evaluate(self, action_beats: int, dialogue_paragraphs: int) -> GateResult:
        if dialogue_paragraphs < 3:
            return self.pass_result()
        ratio = action_beats / dialogue_paragraphs if dialogue_paragraphs else 0
        if ratio < 0.2 and dialogue_paragraphs >= 5:
            return self.fail_result(
                message=f"动作穿插仅 {action_beats}/{dialogue_paragraphs}（{ratio:.0%}）——读者只知道角色在说，不知道角色在做",
                details={
                    "action_beats": action_beats,
                    "total_paragraphs": dialogue_paragraphs,
                    "ratio": round(ratio, 2),
                },
            )
        return self.pass_result(details={"ratio": round(ratio, 2)})