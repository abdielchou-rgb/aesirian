from __future__ import annotations

"""悬念递进门禁 — Bell《冲突与悬念》原理。

悬念不是"有或没有"，而是"在升级还是衰减"。
每个悬念需要持续递进的紧绷度、合理的数量控制、峰值释放。
"""

from wenjian.models import GateSeverity

from .base import BaseGate


class SPN01_TensionEscalation(BaseGate):
    """已建立的悬念紧绷度应随时间递增。"""

    gate_id = "SPN-01"
    name = "悬念升级门禁"
    description = "已建立的悬念紧绷度应随时间递增而非递减——如果读者正在遗忘，说明悬念在衰减"
    severity = GateSeverity.WARN

    def evaluate(
        self,
        gap_id: str,
        current_tension: float,
        previous_tension: float,
        chapters_since_intro: int,
    ) -> GateResult:
        if current_tension < previous_tension and chapters_since_intro >= 2:
            return self.fail_result(
                message=f"悬念'{gap_id}'紧绷度从 {previous_tension} 降到 {current_tension}——悬念在衰减而非升级",
                details={
                    "gap_id": gap_id,
                    "tension_drop": previous_tension - current_tension,
                    "chapters_since": chapters_since_intro,
                },
            )
        if chapters_since_intro >= 5 and current_tension < 4:
            return self.fail_result(
                message=f"悬念'{gap_id}'存在 {chapters_since_intro} 章但紧绷度仅 {current_tension}/10——读者可能已经忘了",
                details={
                    "gap_id": gap_id,
                    "tension": current_tension,
                    "chapters_since": chapters_since_intro,
                },
            )
        return self.pass_result(
            details={"tension": current_tension, "chapters_since": chapters_since_intro}
        )


class SPN02_SuspenseDensity(BaseGate):
    """同时活跃悬念不超过 5 个。"""

    gate_id = "SPN-02"
    name = "悬念密度门禁"
    description = "同时活跃的悬念不超过 5 个，否则读者注意力被稀释"
    severity = GateSeverity.WARN

    def evaluate(self, active_suspense_count: int) -> GateResult:
        if active_suspense_count > 5:
            return self.fail_result(
                message=f"同时有 {active_suspense_count} 个活跃悬念，建议不超过 5 个——读者可能跟不上",
                details={"active_count": active_suspense_count, "max": 5},
            )
        return self.pass_result(details={"active_count": active_suspense_count})


class SPN03_PeakBeforeRelease(BaseGate):
    """悬念释放前应有紧绷度峰值。"""

    gate_id = "SPN-03"
    name = "悬念释放门禁"
    description = "每个悬念在释放前应达到紧绷度峰值——不能草率收掉"
    severity = GateSeverity.WARN

    def evaluate(
        self, gap_id: str, tension_before_release: float, release_satisfaction: int = 3
    ) -> GateResult:
        if tension_before_release < 7:
            return self.fail_result(
                message=f"悬念'{gap_id}'释放时紧绷度仅 {tension_before_release}/10——读者会觉得'就这？'",
                details={"gap_id": gap_id, "tension": tension_before_release, "recommended_min": 7},
            )
        return self.pass_result(details={"tension": tension_before_release})


class SPN04_MultipleSuspense(BaseGate):
    """存在多个层次的悬念交织。"""

    gate_id = "SPN-04"
    name = "悬念层次门禁"
    description = "故事应在不同时间尺度上同时运作多个悬念（短期/中期/长期）"
    severity = GateSeverity.WARN

    def evaluate(self, short_term: int, mid_term: int, long_term: int) -> GateResult:
        if short_term == 0 or (mid_term == 0 and long_term == 0):
            return self.fail_result(
                message=f"短期悬念 {short_term} 个，中期 {mid_term} 个，长期 {long_term} 个——需要覆盖至少两个时间尺度",
                details={"short": short_term, "mid": mid_term, "long": long_term},
            )
        return self.pass_result(details={"short": short_term, "mid": mid_term, "long": long_term})
