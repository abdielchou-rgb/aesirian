from __future__ import annotations

"""断章卡点门禁 — 网文实战技巧。

网文读者翻页成本极低，断章质量决定追读率。
好断章 = 让读者必须点下一章。
"""

from wenjian.models import GateSeverity

from .base import BaseGate


class BRK01_ChapterEndHook(BaseGate):
    """每章结尾必须有未解决的问题或即将发生的事。"""

    gate_id = "BRK-01"
    name = "章末钩子门禁"
    description = "每章结尾必须有未解决的问题或即将发生的事——让读者必须点下一章"
    severity = GateSeverity.WARN

    def evaluate(
        self, has_cliffhanger: bool, has_unresolved: bool, end_type: str = ""
    ) -> GateResult:
        if not has_cliffhanger and not has_unresolved:
            return self.fail_result(
                message="章末没有钩子也没有未解决的问题——读者没有理由点下一章",
                details={"has_cliffhanger": False, "has_unresolved": False},
            )
        if has_cliffhanger and has_unresolved:
            return self.pass_result(
                details={"end_type": "cliffhanger+unresolved", "strength": "strong"}
            )
        return self.pass_result(details={"end_type": end_type, "strength": "ok"})


class BRK02_BreakTiming(BaseGate):
    """不能在平淡或最激烈处断章。"""

    gate_id = "BRK-02"
    name = "断章节奏门禁"
    description = "断章位置应在小高潮之后、大高潮之前——不在平淡处断，不在最激烈时突然断"
    severity = GateSeverity.WARN

    def evaluate(self, break_position: str, immediate_follow_up: str = "") -> GateResult:
        valid_positions = ["高潮后新线索", "反转后", "决定做出前", "揭示前", "战斗开场前"]
        invalid_positions = ["平淡描述中", "战斗中途", "解释说明中", "回忆中", "吐槽闲聊中"]

        if break_position in invalid_positions:
            return self.fail_result(
                message=f"断章在'{break_position}'——读者要么不想追（平淡），要么觉得被耍（突然断）",
                details={"position": break_position},
            )
        if break_position in valid_positions:
            return self.pass_result(details={"position": break_position})

        return self.pass_result(details={"position": break_position})


class BRK03_ChapterLength(BaseGate):
    """网文章节 2000-3000 字为最佳。"""

    gate_id = "BRK-03"
    name = "章节长度门禁"
    description = "网文章节 2000-3000 字为最佳窗口，过长或过短都影响体验"
    severity = GateSeverity.WARN

    def evaluate(self, char_count: int, genre: str = "xianxia_modern") -> GateResult:
        issues = []
        if char_count < 1500:
            issues.append(f"章节 {char_count} 字偏短（建议 2000-3000）——读者觉得'就这么点？'")
        elif char_count > 4000:
            issues.append(f"章节 {char_count} 字偏长（建议 2000-3000）——手机阅读时读者会感觉压力大")
        if issues:
            return self.fail_result(
                message="；".join(issues),
                details={"char_count": char_count, "min": 2000, "max": 3000},
            )
        return self.pass_result(details={"char_count": char_count})


class BRK04_FiveWHook(BaseGate):
    """章末使用 FIVE W 钩子法。"""

    gate_id = "BRK-04"
    name = "章末钩子类型门禁"
    description = "断章时使用五类经典钩子之一：后果/发现/决定/危机/悬念"
    severity = GateSeverity.WARN

    def evaluate(self, hook_type: str, hook_strength: int = 3) -> GateResult:
        valid_types = ["consequence", "discovery", "decision", "crisis", "cliffhanger"]
        type_names = {
            "consequence": "后果钩",
            "discovery": "发现钩",
            "decision": "决定钩",
            "crisis": "危机钩",
            "cliffhanger": "悬念钩",
        }

        if hook_type not in valid_types:
            return self.fail_result(
                message="章末钩子类型不明——使用五类钩子之一：后果/发现/决定/危机/悬念",
                details={"hook_type": hook_type, "valid_types": valid_types},
            )
        if hook_strength < 3:
            name = type_names.get(hook_type, hook_type)
            return self.fail_result(
                message=f"{name}强度 {hook_strength}/5——钩子不够有力，读者可能不会追",
                details={"hook_type": hook_type, "strength": hook_strength},
            )
        return self.pass_result(
            details={
                "hook_type": hook_type,
                "type_name": type_names.get(hook_type),
                "strength": hook_strength,
            }
        )
