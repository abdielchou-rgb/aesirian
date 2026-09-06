from __future__ import annotations

"""Scene Value Turn gates (SVT-01 to SVT-04)."""

from wenjian.models import GateResult, GateSeverity

from .base import BaseGate


class SVT01_SingleSceneFlip(BaseGate):
    gate_id = "SVT-01"
    name = "单场景翻转门禁"
    description = "场景入口和出口的价值观极性必须不同"
    severity = GateSeverity.WARN

    def evaluate(
        self, entry_value: str, exit_value: str, current_total: int = 0, flip_count: int = 0
    ) -> GateResult:
        if entry_value == exit_value:
            return self.fail_result(
                message=f"场景价值观未翻转：入口'{entry_value}' → 出口'{exit_value}'",
                details={"entry": entry_value, "exit": exit_value},
            )
        return self.pass_result(details={"entry": entry_value, "exit": exit_value, "flip": True})


class SVT02_ContinuousFlat(BaseGate):
    gate_id = "SVT-02"
    name = "连续平坦门禁"
    description = "连续4个场景中有3个未翻转，阻断写回"
    severity = GateSeverity.BLOCK

    def evaluate(self, recent_scenes: list) -> GateResult:
        """recent_scenes: list of dicts with {'flip': bool}"""
        if len(recent_scenes) < 4:
            return self.pass_result(message="场景数不足4个，跳过检查")
        no_flip = sum(1 for s in recent_scenes[-4:] if not s.get("flip", True))
        if no_flip >= 3:
            return self.fail_result(
                message=f"连续4个场景中有{no_flip}个未翻转",
                details={"recent_flips": [s.get("flip") for s in recent_scenes[-4:]]},
            )
        return self.pass_result(details={"no_flip_in_last_4": no_flip})


class SVT03_ValueMonotone(BaseGate):
    gate_id = "SVT-03"
    name = "价值观单一门禁"
    description = "全篇超过80%的翻转使用同一对价值观"
    severity = GateSeverity.WARN

    def evaluate(self, value_pair_counts: dict) -> GateResult:
        if not value_pair_counts:
            return self.pass_result(message="无数据")
        total = sum(value_pair_counts.values())
        if total == 0:
            return self.pass_result()
        dominant = max(value_pair_counts.values())
        ratio = dominant / total
        if ratio > 0.8:
            dominant_pair = max(value_pair_counts, key=value_pair_counts.get)
            return self.fail_result(
                message=f"价值观'{dominant_pair}'占{ratio:.0%}，超过80%阈值",
                details={
                    "ratio": round(ratio, 2),
                    "dominant_pair": dominant_pair,
                    "counts": value_pair_counts,
                },
            )
        return self.pass_result(details={"dominant_ratio": round(ratio, 2)})


class SVT04_ActClimax(BaseGate):
    gate_id = "SVT-04"
    name = "幕级翻转门禁"
    description = "每幕结束时必须有不可逆的价值观颠覆"
    severity = GateSeverity.BLOCK

    def evaluate(self, has_irreversible_turn: bool, act_number: int) -> GateResult:
        if not has_irreversible_turn:
            return self.fail_result(
                message=f"第{act_number}幕结束时无不可逆价值观颠覆",
                details={"act": act_number},
            )
        return self.pass_result(details={"act": act_number})
