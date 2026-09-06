from __future__ import annotations
"""微型张力门禁 — 基于 Donald Maass《Writing the Breakout Novel》。

张力不是章节级的，是句子级的。
每一页都要有让读者翻页的理由。
"""

from .base import BaseGate
from wenjian.models import GateSeverity, GateResult


class MT01_MicroTensionDensity(BaseGate):
    """每 500 字至少 1 个微型张力点。"""
    gate_id = "MTS-01"
    name = "微型张力密度门禁"
    description = "每 500 字至少出现1个微型张力点"
    severity = GateSeverity.WARN

    def evaluate(self, micro_tension_count: int, char_count: int) -> GateResult:
        if char_count < 300:
            return self.pass_result(message="文本太短，跳过")
        expected = max(1, char_count // 500)
        if micro_tension_count < expected:
            return self.fail_result(
                message=f"微型张力 {micro_tension_count} 个/{char_count} 字，期待至少 {expected} 个。需要更多微型悬念/对话冲突/句末逆转",
                details={"count": micro_tension_count, "char_count": char_count, "expected": expected,
                         "density": round(micro_tension_count / max(char_count / 500, 1), 2)},
            )
        return self.pass_result(details={"count": micro_tension_count, "density": round(micro_tension_count / max(char_count / 500, 1), 2)})


class MT02_ReversalDensity(BaseGate):
    """句末逆转——每 1000 字至少 1 个微观逆转。"""
    gate_id = "MTS-02"
    name = "微观逆转密度门禁"
    description = "每 1000 字至少1个句末逆转"
    severity = GateSeverity.WARN

    def evaluate(self, reversal_count: int, char_count: int) -> GateResult:
        if char_count < 300:
            return self.pass_result(message="文本太短")
        expected = max(1, char_count // 1000)
        if reversal_count < expected:
            return self.fail_result(
                message=f"句末逆转 {reversal_count} 个/{char_count} 字，期待至少 {expected} 个",
                details={"count": reversal_count, "char_count": char_count, "expected": expected},
            )
        return self.pass_result()