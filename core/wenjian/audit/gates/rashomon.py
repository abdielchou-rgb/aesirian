from __future__ import annotations
"""Rashomon gates — 罗生门多视角不可靠叙述门禁.

核心原则（Ryan Murphy's "not a photograph, a painting"）：
同一事件从多个不可靠视角叙述，系统不裁决哪个版本为真。
"""

from .base import BaseGate
from wenjian.models import GateResult, GateSeverity


class RSM01_PovBeliefSystem(BaseGate):
    """每个参与视角的角色必须有自洽的信念系统。"""

    gate_id = "RSM-01"
    name = "视角信念系统门禁"
    description = "罗生门结构中，每个视角角色必须有自洽但可能互相冲突的信念系统"
    severity = GateSeverity.WARN

    def evaluate(self, character_name: str, has_belief_system: bool, conflicts_with_other_povs: bool) -> GateResult:
        if not has_belief_system:
            return self.fail_result(
                message=f"角色'{character_name}'缺少自洽的信念系统——罗生门结构中每个视角必须有独立的世界观",
                details={"character": character_name},
            )
        if not conflicts_with_other_povs:
            return self.fail_result(
                message=f"角色'{character_name}'的信念与其他视角无冲突——不是罗生门，只是多角度重复叙述",
                details={"character": character_name},
            )
        return self.pass_result(details={"character": character_name})


class RSM02_UnresolvedContradiction(BaseGate):
    """系统不裁决矛盾——如果系统暗示了"哪个版本是真"，则不是罗生门。"""

    gate_id = "RSM-02"
    name = "矛盾不裁决门禁"
    description = "系统不能判定哪一方的叙述为真——如果系统做出了裁决，则退化为悬疑结构而非罗生门"
    severity = GateSeverity.BLOCK

    def evaluate(self, povs: list, system_judgement: str = "") -> GateResult:
        if system_judgement and not self._is_truly_ambiguous(povs, system_judgement):
            return self.fail_result(
                message=f"系统判定'{system_judgement}'为真——这不是罗生门结构，是悬疑结构。罗生门不裁决真相。",
                details={"povs": povs, "judgement": system_judgement},
            )
        return self.pass_result(details={"pov_count": len(povs)})

    def _is_truly_ambiguous(self, povs: list, judgement: str) -> bool:
        """Check if the judgement truly captures ambiguity."""
        if not povs or not judgement:
            return True
        # If any POV contradicts the judgement AND is not marked as "lying",
        # the structure is properly Rashomon
        for pov in povs:
            if isinstance(pov, dict):
                if pov.get("version") != judgement and not pov.get("is_lying", False):
                    return True
        return False


class RSM03_OverlapBoundary(BaseGate):
    """所有版本共同承认的部分构成了故事客观事实的边界。"""

    gate_id = "RSM-03"
    name = "客观事实边界门禁"
    description = "罗生门结构应标记所有视角共同承认的事实（重叠区域）与矛盾区域"
    severity = GateSeverity.WARN

    def evaluate(self, total_events: int, overlapping_events: int, contradictory_events: int) -> GateResult:
        if total_events == 0:
            return self.pass_result(message="无事件数据")
        overlap_ratio = overlapping_events / total_events if total_events else 0
        contradiction_ratio = contradictory_events / total_events if total_events else 0

        if overlap_ratio > 0.8:
            return self.fail_result(
                message=f"视角重叠率{overlap_ratio:.0%}——各版本过于一致，失去罗生门效果",
                details={"overlap_ratio": round(overlap_ratio, 2), "contradiction_ratio": round(contradiction_ratio, 2)},
            )
        if contradiction_ratio < 0.2:
            return self.fail_result(
                message=f"视角矛盾率仅{contradiction_ratio:.0%}——缺乏实质性叙事冲突",
                details={"overlap_ratio": round(overlap_ratio, 2), "contradiction_ratio": round(contradiction_ratio, 2)},
            )
        return self.pass_result(details={"overlap_ratio": round(overlap_ratio, 2), "contradiction_ratio": round(contradiction_ratio, 2)})