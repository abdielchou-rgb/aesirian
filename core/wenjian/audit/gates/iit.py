from __future__ import annotations
"""Inciting Incident Timer gates (IIT-01 to IIT-03)."""

from .base import BaseGate
from wenjian.models import GateResult, GateSeverity


class IIT01_Timing(BaseGate):
    gate_id = "IIT-01"
    name = "激励事件时机门禁"
    description = "激励事件必须在总篇幅的前25%（出版）/前15%（流媒体）内发生"
    severity = GateSeverity.BLOCK

    def evaluate(self, position_percent: float, deadline: float = 25.0) -> GateResult:
        if position_percent > deadline:
            return self.fail_result(
                message=f"激励事件在{position_percent:.0f}%处发生，超过{deadline:.0f}%的时限",
                details={"position": position_percent, "deadline": deadline, "overdue_by": round(position_percent - deadline, 1)},
            )
        margin = deadline - position_percent
        status = "临界" if margin < 5 else "正常"
        return self.pass_result(details={"position": position_percent, "deadline": deadline, "margin": round(margin, 1), "status": status})


class IIT02_DualDesire(BaseGate):
    gate_id = "IIT-02"
    name = "双重欲望声明门禁"
    description = "激励事件必须在主角身上同时激发自觉和不自觉欲望"
    severity = GateSeverity.WARN

    def evaluate(self, has_conscious: bool, has_unconscious: bool) -> GateResult:
        missing = []
        if not has_conscious:
            missing.append("自觉欲望")
        if not has_unconscious:
            missing.append("不自觉欲望")
        if missing:
            return self.fail_result(
                message=f"缺少：{'、'.join(missing)}",
                details={"has_conscious": has_conscious, "has_unconscious": has_unconscious},
            )
        return self.pass_result(details={"has_conscious": True, "has_unconscious": True})


class IIT03_Irreversibility(BaseGate):
    gate_id = "IIT-03"
    name = "不可逆性门禁"
    description = "激励事件造成的平衡破坏必须是不可逆的"
    severity = GateSeverity.BLOCK

    def evaluate(self, is_reversible: bool) -> GateResult:
        if is_reversible:
            return self.fail_result(
                message="激励事件可逆——主角可以恢复原状",
                details={"is_reversible": True},
            )
        return self.pass_result(details={"is_reversible": False})