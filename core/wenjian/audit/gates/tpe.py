from __future__ import annotations

"""Touchpoint Engineering gates (TPE-01 to TPE-03)."""

from wenjian.models import GateResult, GateSeverity

from .base import BaseGate


class TPE01_OverexplainedEmotion(BaseGate):
    gate_id = "TPE-01"
    name = "情绪过度解释门禁"
    description = "直接情绪声明的次数必须少于触点次数"
    severity = GateSeverity.WARN

    def evaluate(self, direct_emotions: int, touchpoints: int) -> GateResult:
        if direct_emotions > touchpoints:
            return self.fail_result(
                message=f"情绪声明{direct_emotions}次 > 触点{touchpoints}次",
                details={
                    "direct_emotions": direct_emotions,
                    "touchpoints": touchpoints,
                    "ratio": f"{direct_emotions}:{touchpoints}",
                },
            )
        return self.pass_result(
            details={"direct_emotions": direct_emotions, "touchpoints": touchpoints}
        )


class TPE02_TurnNoTouchpoint(BaseGate):
    gate_id = "TPE-02"
    name = "转折无触点门禁"
    description = "关键转折场景中必须有至少指定数量的触点"
    severity = GateSeverity.WARN

    def evaluate(
        self,
        scene_id: str,
        touchpoint_count: int,
        is_critical: bool = True,
        min_touchpoints: int = 2,
    ) -> GateResult:
        if is_critical and touchpoint_count < min_touchpoints:
            return self.fail_result(
                message=f"关键场景'{scene_id}'仅有{touchpoint_count}个触点（需要{min_touchpoints}个）",
                details={
                    "scene_id": scene_id,
                    "touchpoint_count": touchpoint_count,
                    "min_required": min_touchpoints,
                },
            )
        return self.pass_result(
            details={"scene_id": scene_id, "touchpoint_count": touchpoint_count}
        )


class TPE03_TouchpointMismatch(BaseGate):
    gate_id = "TPE-03"
    name = "触点不匹配门禁"
    description = "触点的情感负载与上下文情感不一致"
    severity = GateSeverity.WARN

    def evaluate(self, scene_id: str, touchpoint_emotion: str, context_emotion: str) -> GateResult:
        if touchpoint_emotion != context_emotion:
            return self.fail_result(
                message=f"场景'{scene_id}'触点负载'{touchpoint_emotion}'与上下文情感'{context_emotion}'不一致",
                details={
                    "scene_id": scene_id,
                    "touchpoint_emotion": touchpoint_emotion,
                    "context_emotion": context_emotion,
                },
            )
        return self.pass_result(
            details={
                "scene_id": scene_id,
                "touchpoint_emotion": touchpoint_emotion,
                "context_emotion": context_emotion,
            }
        )
