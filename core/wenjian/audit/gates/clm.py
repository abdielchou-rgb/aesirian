from __future__ import annotations
"""Conflict Layer Matrix gates (CLM-01 to CLM-03)."""

from .base import BaseGate
from wenjian.models import GateResult, GateSeverity


class CLM01_SingleLayer(BaseGate):
    gate_id = "CLM-01"
    name = "单层冲突门禁"
    description = "对抗力至少应在2个层次上运作"
    severity = GateSeverity.WARN

    def evaluate(self, active_layers: list) -> GateResult:
        if len(active_layers) < 2:
            return self.fail_result(
                message=f"对抗力仅在{len(active_layers)}层运作：{active_layers}",
                details={"active_layers": active_layers, "count": len(active_layers)},
            )
        return self.pass_result(details={"active_layers": active_layers, "count": len(active_layers)})


class CLM02_NoCrossover(BaseGate):
    gate_id = "CLM-02"
    name = "交错缺失门禁"
    description = "故事超过50%篇幅仍无任何2层以上的交汇场景"
    severity = GateSeverity.WARN

    def evaluate(self, position_percent: float, has_crossover: bool) -> GateResult:
        if position_percent > 50 and not has_crossover:
            return self.fail_result(
                message=f"在{position_percent:.0f}%处仍无层间交汇场景",
                details={"position": position_percent, "has_crossover": False},
            )
        return self.pass_result(details={"position": position_percent, "has_crossover": has_crossover})


class CLM03_Mismatch(BaseGate):
    gate_id = "CLM-03"
    name = "维度不匹配门禁"
    description = "内外冲突强度应大致匹配"
    severity = GateSeverity.WARN

    def evaluate(self, external_intensity: float, internal_intensity: float) -> GateResult:
        if abs(external_intensity - internal_intensity) > 3.0:
            return self.fail_result(
                message=f"外部冲突强度({external_intensity})与内部冲突强度({internal_intensity})不匹配（差异{abs(external_intensity - internal_intensity):.1f}）",
                details={"external": external_intensity, "internal": internal_intensity, "gap": round(abs(external_intensity - internal_intensity), 1)},
            )
        return self.pass_result(details={"external": external_intensity, "internal": internal_intensity})