from __future__ import annotations
"""Revelation Index gates (RVI-01 to RVI-05)."""

from .base import BaseGate
from wenjian.models import GateResult, GateSeverity


class RVI01_CuriosityStarvation(BaseGate):
    gate_id = "RVI-01"
    name = "好奇引擎熄火门禁"
    description = "连续4章无新信息缺口创建"
    severity = GateSeverity.WARN

    def evaluate(self, chapters_since_new_gap: int) -> GateResult:
        if chapters_since_new_gap >= 4:
            return self.fail_result(
                message=f"连续{chapters_since_new_gap}章无新信息缺口",
                details={"chapters_since_new_gap": chapters_since_new_gap},
            )
        return self.pass_result(details={"chapters_since_new_gap": chapters_since_new_gap})


class RVI02_FrustrationBuildup(BaseGate):
    gate_id = "RVI-02"
    name = "挫败累积门禁"
    description = "连续5章无缺口被解决"
    severity = GateSeverity.WARN

    def evaluate(self, chapters_since_last_resolution: int) -> GateResult:
        if chapters_since_last_resolution >= 5:
            return self.fail_result(
                message=f"连续{chapters_since_last_resolution}章无缺口被解决",
                details={"chapters_since_last_resolution": chapters_since_last_resolution},
            )
        return self.pass_result(details={"chapters_since_last_resolution": chapters_since_last_resolution})


class RVI03_DeusExMachina(BaseGate):
    gate_id = "RVI-03"
    name = "机械降神风险门禁"
    description = "缺口揭晓前暗示数必须>=1"
    severity = GateSeverity.BLOCK

    def evaluate(self, gap_id: str, hint_count: int) -> GateResult:
        if hint_count == 0:
            return self.fail_result(
                message=f"缺口'{gap_id}'揭晓前暗示数为0（机械降神风险）",
                details={"gap_id": gap_id, "hint_count": hint_count},
            )
        return self.pass_result(details={"gap_id": gap_id, "hint_count": hint_count})


class RVI04_GapOverload(BaseGate):
    gate_id = "RVI-04"
    name = "超载门禁"
    description = "缺口总数超过上限或新增净速率超过上限"
    severity = GateSeverity.WARN

    def evaluate(self, total_open: int, net_rate: float = 0, max_open: int = 15, max_rate: float = 0.8) -> GateResult:
        if total_open > max_open or net_rate > max_rate:
            return self.fail_result(
                message=f"缺口{total_open}个（上限{max_open}），净速率{net_rate:.2f}/章（上限{max_rate}）",
                details={"total_open": total_open, "max_open": max_open, "net_rate": round(net_rate, 2), "max_rate": max_rate},
            )
        return self.pass_result(details={"total_open": total_open, "net_rate": round(net_rate, 2)})


class RVI05_GapForgotten(BaseGate):
    gate_id = "RVI-05"
    name = "缺口遗忘门禁"
    description = "缺口紧绷度<3且未被触及超过5章"
    severity = GateSeverity.WARN

    def evaluate(self, gap_id: str, tension: float, chapters_unmentioned: int) -> GateResult:
        if tension < 3 and chapters_unmentioned >= 5:
            return self.fail_result(
                message=f"缺口'{gap_id}'紧绷度{tension}且{chapters_unmentioned}章未触及",
                details={"gap_id": gap_id, "tension": tension, "chapters_unmentioned": chapters_unmentioned},
            )
        return self.pass_result(details={"gap_id": gap_id, "tension": tension, "chapters_unmentioned": chapters_unmentioned})