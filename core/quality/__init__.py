"""质量保障聚合门面 — 吸收 InkOS/Barthes/Storr/Maass/Show Don't Tell

统一入口：QualityInspector.run_all(text) → 标准化 issue 列表
（含规则名/严重级/消息，可直接并入门禁报告）
"""

from __future__ import annotations

from core.quality.ai_tell_detector import AITellDetector
from core.quality.control_illusion import ControlIllusionDetector
from core.quality.micro_tension import MicroTensionDetector
from core.quality.reality_effect import RealityEffectDetector
from core.quality.show_dont_tell import ShowDontTellDetector


class QualityInspector:
    """五检测器聚合"""

    def __init__(self):
        self.detectors = [
            ("ai_tell", AITellDetector()),
            ("reality_effect", RealityEffectDetector()),
            ("control_illusion", ControlIllusionDetector()),
            ("micro_tension", MicroTensionDetector()),
            ("show_dont_tell", ShowDontTellDetector()),
        ]

    def run_all(self, text: str) -> list[dict]:
        """返回标准化 issue 列表"""
        return [
            {
                "gate_id": f"Q-{family.upper()}",
                "gate_name": issue.get("rule", family),
                "level": issue.get("severity", "warn"),
                "message": issue.get("message", ""),
                "suggestion": "",
                "family": family,
            }
            for family, detector in self.detectors
            for issue in detector.detect(text)
        ]


# 全局单例
_inspector: QualityInspector | None = None


def get_quality_inspector() -> QualityInspector:
    global _inspector
    if _inspector is None:
        _inspector = QualityInspector()
    return _inspector
