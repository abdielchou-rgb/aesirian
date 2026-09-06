from __future__ import annotations

"""Dual Desire Tracker gates (DDT-01 to DDT-04)."""

from wenjian.models import GateResult, GateSeverity

from .base import BaseGate


class DDT01_SingleDesire(BaseGate):
    gate_id = "DDT-01"
    name = "单欲望人物门禁"
    description = "主要角色必须有自觉和不自觉双重欲望"
    severity = GateSeverity.WARN

    def evaluate(
        self, character_name: str, has_conscious: bool, has_unconscious: bool
    ) -> GateResult:
        if not has_conscious or not has_unconscious:
            missing = []
            if not has_conscious:
                missing.append("自觉欲望")
            if not has_unconscious:
                missing.append("不自觉欲望")
            return self.fail_result(
                message=f"角色'{character_name}'缺少{'、'.join(missing)}",
                details={
                    "character": character_name,
                    "has_conscious": has_conscious,
                    "has_unconscious": has_unconscious,
                },
            )
        return self.pass_result(details={"character": character_name})


class DDT02_DesireOverexposed(BaseGate):
    gate_id = "DDT-02"
    name = "欲望过度曝光门禁"
    description = "不自觉欲望不能由角色用对话直接说出"
    severity = GateSeverity.WARN

    def evaluate(self, character_name: str, desire_spoken: bool) -> GateResult:
        if desire_spoken:
            return self.fail_result(
                message=f"角色'{character_name}'直接说出了自己的不自觉欲望",
                details={"character": character_name},
            )
        return self.pass_result(details={"character": character_name})


class DDT03_ProgressTooSmooth(BaseGate):
    gate_id = "DDT-03"
    name = "进展过顺门禁"
    description = "自觉欲望的追逐过程不能连3次advance而无setback"
    severity = GateSeverity.WARN

    def evaluate(self, recent_progress: list) -> GateResult:
        """recent_progress: list of 'advance'/'setback'/'neutral'"""
        if len(recent_progress) < 3:
            return self.pass_result(message="数据不足3个点")
        last_3 = recent_progress[-3:]
        if all(d == "advance" for d in last_3):
            return self.fail_result(
                message="自觉欲望连续3次advance无setback",
                details={"recent_trend": last_3},
            )
        return self.pass_result(details={"recent_trend": last_3})


class DDT04_DesireLatentTooLong(BaseGate):
    gate_id = "DDT-04"
    name = "欲望激活过晚门禁"
    description = "不自觉欲望必须在总篇幅60%前从latent转为active"
    severity = GateSeverity.WARN

    def evaluate(self, current_position: float, desire_status: str) -> GateResult:
        if current_position > 0.6 and desire_status == "latent":
            return self.fail_result(
                message=f"不自觉欲望在{current_position:.0%}处仍为latent，超过60%阈值",
                details={"position": current_position, "desire_status": desire_status},
            )
        return self.pass_result(
            details={"position": current_position, "desire_status": desire_status}
        )
