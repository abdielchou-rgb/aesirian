from __future__ import annotations

from wenjian.models import GateResult

"""黄金三章门禁 — 网文前 3 章专项审计。

网文生死就在前三章，独立于其他门禁单独运行。
"""

from wenjian.models import GateSeverity

from .base import BaseGate


class G3_01_FirstChapterConflict(BaseGate):
    """第一章前 500 字出现冲突。"""

    gate_id = "G3-01"
    name = "首章冲突门禁"
    description = "第一章前 500 字内必须出现冲突或悬念"
    severity = GateSeverity.BLOCK

    def evaluate(self, conflict_position: int) -> GateResult:
        if conflict_position > 500:
            return self.fail_result(
                message=f"首次冲突出现在第 {conflict_position} 字，应在前 500 字内",
                details={
                    "position": conflict_position,
                    "deadline": 500,
                    "overdue_by": conflict_position - 500,
                },
            )
        return self.pass_result(details={"position": conflict_position})


class G3_02_ProtagonistIntro(BaseGate):
    """主角必须在第一章出场。"""

    gate_id = "G3-02"
    name = "主角出场门禁"
    description = "主角必须在第一章内出场"
    severity = GateSeverity.BLOCK

    def evaluate(self, appears_in_chapter_1: bool) -> GateResult:
        if not appears_in_chapter_1:
            return self.fail_result(
                message="主角未在第一章出场——读者不知道谁是主角", details={"appears": False}
            )
        return self.pass_result()


class G3_03_WhyQuestion(BaseGate):
    """第一章至少留下一个"为什么"。"""

    gate_id = "G3-03"
    name = "悬念驱动门禁"
    description = "第一章至少留下一个让读者想追问'为什么'的悬念"
    severity = GateSeverity.WARN

    def evaluate(self, hook_count: int) -> GateResult:
        if hook_count < 1:
            return self.fail_result(
                message="第一章没有留下让读者追问的悬念", details={"hook_count": 0}
            )
        if hook_count == 1:
            return self.pass_result(
                details={"hook_count": 1, "note": "刚好达标，建议增加到 2 个以上"}
            )
        return self.pass_result(details={"hook_count": hook_count})


class G3_04_Chapter2Goal(BaseGate):
    """第二章建立短期目标。"""

    gate_id = "G3-04"
    name = "第二章目标门禁"
    description = "第二章结束时主角应建立明确的短期目标"
    severity = GateSeverity.WARN

    def evaluate(self, has_short_term_goal: bool, goal_clarity: int = 3) -> GateResult:
        if not has_short_term_goal:
            return self.fail_result(
                message="第二章结束时主角没有明确的短期目标——读者不知道主角要做什么",
                details={"has_goal": False},
            )
        if goal_clarity < 3:
            return self.fail_result(
                message=f"目标明确度 {goal_clarity}/5，建议让目标更具体",
                details={"clarity": goal_clarity},
            )
        return self.pass_result(details={"clarity": goal_clarity})


class G3_05_Chapter3Pleasure(BaseGate):
    """第三章出现第一个正式爽点。"""

    gate_id = "G3-05"
    name = "第三章爽点门禁"
    description = "第三章必须出现第一个正式的爽点（小成功/小逆袭/小发现）"
    severity = GateSeverity.WARN

    def evaluate(self, has_first_pleasure: bool, pleasure_type: str = "") -> GateResult:
        if not has_first_pleasure:
            return self.fail_result(
                message="第三章没有爽点——三章了读者还没尝到甜头，可能会弃书",
                details={"has_pleasure": False},
            )
        return self.pass_result(details={"type": pleasure_type})


class G3_06_Chapter3Cliffhanger(BaseGate):
    """第三章结尾强钩子。"""

    gate_id = "G3-06"
    name = "第三章强钩子门禁"
    description = "第三章结尾必须有强钩子——让读者必须点下一章"
    severity = GateSeverity.BLOCK

    def evaluate(self, hook_strength: int, hook_type: str = "") -> GateResult:
        if hook_strength < 3:
            return self.fail_result(
                message=f"章末钩子强度 {hook_strength}/5，需要至少 3/5——三章读完了没有非追不可的理由",
                details={"strength": hook_strength, "type": hook_type},
            )
        return self.pass_result(details={"strength": hook_strength, "type": hook_type})


class G3_07_NoInfoDump(BaseGate):
    """前三章不可出现大段世界观倾倒。"""

    gate_id = "G3-07"
    name = "前三章信息倾泻门禁"
    description = "前三章不应出现超过 200 字的纯设定描述"
    severity = GateSeverity.WARN

    def evaluate(self, longest_exposition_block: int) -> GateResult:
        if longest_exposition_block > 200:
            return self.fail_result(
                message=f"最长的纯设定段落 {longest_exposition_block} 字，建议不超过 200 字。世界观应在剧情中自然展开。",
                details={"max_exposition": longest_exposition_block},
            )
        return self.pass_result(details={"max_exposition": longest_exposition_block})