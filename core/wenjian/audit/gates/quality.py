from __future__ import annotations

"""质量检测门禁 — 灌水检测 + 读者情绪曲线。"""

from wenjian.models import GateSeverity

from .base import BaseGate


class QLT01_FillerDetection(BaseGate):
    gate_id = "QLT-01"
    name = "灌水检测门禁"
    description = "识别并标记无意义填充段落"
    severity = GateSeverity.WARN

    def evaluate(
        self, filler_ratio: float = 0.0, total_paragraphs: int = 1, filler_paragraphs: int = 0
    ) -> GateResult:
        if filler_ratio > 0.3 and filler_paragraphs >= 2:
            return self.fail_result(
                message=f"灌水段落 {filler_paragraphs}/{total_paragraphs}（{filler_ratio:.0%}）"
            )
        return self.pass_result()


class QLT02_RepeatedInfo(BaseGate):
    gate_id = "QLT-02"
    name = "信息重复门禁"
    description = "同一信息在短时间内被重复多次"
    severity = GateSeverity.WARN

    def evaluate(self, repeat_count: int = 0, chapters_span: int = 0) -> GateResult:
        if repeat_count >= 3 and chapters_span <= 2:
            return self.fail_result(
                message=f"同一信息在 {chapters_span} 章内重复 {repeat_count} 次"
            )
        return self.pass_result()


class QLT03_EmotionCurve(BaseGate):
    gate_id = "QLT-03"
    name = "情绪曲线门禁"
    description = "检测压抑→释放的周期性"
    severity = GateSeverity.WARN

    def evaluate(
        self,
        tension_level: float = 0.0,
        consecutive_tension_chapters: int = 0,
        genre: str = "xianxia_modern",
    ) -> GateResult:
        max_t = {
            "xianxia_modern": 4,
            "xianxia_traditional": 5,
            "historical_rebirth": 4,
            "xuanhuan": 4,
        }.get(genre, 5)
        if tension_level > 0.7 and consecutive_tension_chapters >= max_t:
            return self.fail_result(message=f"连续 {consecutive_tension_chapters} 章高压，需释放段")
        return self.pass_result()


class QLT04_PacingVariety(BaseGate):
    gate_id = "QLT-04"
    name = "节奏多样性门禁"
    description = "检查节奏是否过于单一"
    severity = GateSeverity.WARN

    def evaluate(
        self, dominant_beat_ratio: float = 0.0, dominant_beat_type: str = ""
    ) -> GateResult:
        if dominant_beat_ratio > 0.7:
            return self.fail_result(
                message=f"'{dominant_beat_type}'占{dominant_beat_ratio:.0%}，节奏单一"
            )
        return self.pass_result()


class QLT05_OpenLoopCount(BaseGate):
    gate_id = "QLT-05"
    name = "未闭环事件门禁"
    description = "同时悬而未决的事件数量管理"
    severity = GateSeverity.WARN

    def evaluate(self, open_loops: int = 0) -> GateResult:
        if open_loops > 5:
            return self.fail_result(message=f"同时有{open_loops}个未闭环事件线")
        return self.pass_result()
