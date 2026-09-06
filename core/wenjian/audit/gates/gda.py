from __future__ import annotations

"""Gap Density Audit gates (GDA-01 to GDA-04)."""

from wenjian.models import GateResult, GateSeverity

from .base import BaseGate


class GDA01_GapFamine(BaseGate):
    gate_id = "GDA-01"
    name = "平坦段门禁"
    description = "连续3个场景的鸿沟密度低于下限，阻断写回"
    severity = GateSeverity.BLOCK

    def evaluate(self, densities: list, floor: float = 1.0) -> GateResult:
        if len(densities) < 3:
            return self.pass_result(message="数据不足3个场景")
        last_3 = densities[-3:]
        below_threshold = all(d < floor for d in last_3)
        if below_threshold:
            return self.fail_result(
                message=f"连续3个场景鸿沟密度<{floor}：{last_3}",
                details={"recent_densities": last_3, "threshold": floor},
            )
        return self.pass_result(
            details={"recent_densities": last_3, "below_count": sum(1 for d in last_3 if d < floor)}
        )


class GDA02_GapOverload(BaseGate):
    gate_id = "GDA-02"
    name = "疲劳段门禁"
    description = "连续2个场景鸿沟密度超过上限"
    severity = GateSeverity.WARN

    def evaluate(self, densities: list, max_density: float = 6.0) -> GateResult:
        if len(densities) < 2:
            return self.pass_result()
        last_2 = densities[-2:]
        if all(d > max_density for d in last_2):
            return self.fail_result(
                message=f"连续2个场景密度>{max_density}：{last_2}",
                details={"recent_densities": last_2, "max_density": max_density},
            )
        return self.pass_result(details={"recent_densities": last_2})


class GDA03_GapMonotone(BaseGate):
    gate_id = "GDA-03"
    name = "鸿沟幅度单一门禁"
    description = "最近5个场景超过80%的鸿沟幅度相同"
    severity = GateSeverity.WARN

    def evaluate(self, intensities: list) -> GateResult:
        if len(intensities) < 5:
            return self.pass_result()
        last_5 = intensities[-5:]
        if not last_5:
            return self.pass_result()
        from collections import Counter

        counts = Counter(last_5)
        most_common, freq = counts.most_common(1)[0]
        ratio = freq / len(last_5)
        if ratio > 0.8:
            return self.fail_result(
                message=f"最近5个场景中{ratio:.0%}的鸿沟幅度均为{most_common}",
                details={"amplitudes": last_5, "dominant": most_common, "ratio": round(ratio, 2)},
            )
        return self.pass_result(details={"amplitudes": last_5})


class GDA04_GapDesert(BaseGate):
    gate_id = "GDA-04"
    name = "长段无鸿沟门禁"
    description = "连续超过2000字文本中无任何鸿沟"
    severity = GateSeverity.WARN

    def evaluate(self, word_count_since_last_gap: int) -> GateResult:
        if word_count_since_last_gap > 2000:
            return self.fail_result(
                message=f"已连续{word_count_since_last_gap}字无鸿沟",
                details={"words_since_last_gap": word_count_since_last_gap},
            )
        return self.pass_result(details={"words_since_last_gap": word_count_since_last_gap})
