from __future__ import annotations

"""Platform Rhythm gates (PRP-01 to PRP-03)."""

from wenjian.models import GateResult, GateSeverity

from .base import BaseGate


class PRP01_TemplateMismatch(BaseGate):
    gate_id = "PRP-01"
    name = "模板不匹配门禁"
    description = "节奏模板与声明的类型/平台不一致"
    severity = GateSeverity.WARN

    def evaluate(self, declared_platform: str, active_template: str) -> GateResult:
        if declared_platform != active_template:
            return self.fail_result(
                message=f"声明的平台'{declared_platform}'与活跃模板'{active_template}'不一致",
                details={"declared": declared_platform, "active": active_template},
            )
        return self.pass_result(details={"declared": declared_platform, "active": active_template})


class PRP02_HookOverdue(BaseGate):
    gate_id = "PRP-02"
    name = "钩子逾期门禁"
    description = "首个钩子必须在平台指定的字数限制内出现"
    severity = GateSeverity.WARN

    def evaluate(
        self, first_hook_position: int, platform: str = "webnovel", hook_limit: int = None
    ) -> GateResult:
        limits = {
            "webnovel": 150,
            "streaming_first": 300,
            "publication_novel": 99999,
            "literary_fiction": 99999,
        }
        limit = hook_limit if hook_limit is not None else limits.get(platform, 150)
        if first_hook_position > limit:
            return self.fail_result(
                message=f"首个钩子在{first_hook_position}字处，{platform}要求前{limit}字内",
                details={"position": first_hook_position, "limit": limit, "platform": platform},
            )
        return self.pass_result(details={"position": first_hook_position, "limit": limit})


class PRP03_ClimaxGap(BaseGate):
    gate_id = "PRP-03"
    name = "高潮间隔门禁"
    description = "当前距离上一次mini-climax超过模板的间隔要求"
    severity = GateSeverity.WARN

    def evaluate(self, chapters_since_last: int, max_interval: int, platform: str) -> GateResult:
        if chapters_since_last > max_interval:
            return self.fail_result(
                message=f"距上次小高潮已{chapters_since_last}章（{platform}模板上限{max_interval}章）",
                details={
                    "chapters_since_last": chapters_since_last,
                    "max_interval": max_interval,
                    "platform": platform,
                },
            )
        return self.pass_result(
            details={"chapters_since_last": chapters_since_last, "max_interval": max_interval}
        )
