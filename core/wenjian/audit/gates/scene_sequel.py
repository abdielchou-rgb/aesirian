from __future__ import annotations

from wenjian.models import GateResult

"""Scene-Sequel 结构门禁 -- 基于 Dwight Swain / Jack Bickham 的场景理论。"""

from wenjian.models import GateSeverity

from .base import BaseGate


class SST01_SceneTypeLabel(BaseGate):
    gate_id = "SST-01"
    name = "场景类型标注门禁"
    description = "每个场景必须标注是行动场景（Scene）还是反应场景（Sequel）"
    severity = GateSeverity.WARN

    def evaluate(self, scene_type: str, has_clear_type: bool) -> GateResult:
        if not has_clear_type or scene_type not in ("scene", "sequel"):
            return self.fail_result(message="场景类型未标注", details={"scene_type": scene_type})
        return self.pass_result()


class SST02_CausalChain(BaseGate):
    gate_id = "SST-02"
    name = "因果链门禁"
    description = "每个场景的起始状态必须由上一个场景的结束状态直接导致"
    severity = GateSeverity.WARN

    def evaluate(self, previous_exit: str, current_entry: str, chain_strength: int) -> GateResult:
        if chain_strength < 2:
            return self.fail_result(
                message=f"场景因果链偏弱（强度 {chain_strength}/5）",
                details={"chain": chain_strength},
            )
        return self.pass_result()


class SST03_SceneSequelRhythm(BaseGate):
    gate_id = "SST-03"
    name = "场景交替节奏门禁"
    description = "不能连续3个Scene无Sequel缓冲"
    severity = GateSeverity.WARN

    def evaluate(self, recent_types: list) -> GateResult:
        if len(recent_types) < 3:
            return self.pass_result(message="数据不足")
        last_3 = recent_types[-3:]
        if all(t == "scene" for t in last_3):
            return self.fail_result(
                message="连续3个行动场景无反应续场", details={"pattern": last_3}
            )
        if all(t == "sequel" for t in last_3):
            return self.fail_result(
                message="连续3个反应场景无行动推进", details={"pattern": last_3}
            )
        return self.pass_result()


class SCQ01_SceneStructure(SST01_SceneTypeLabel):
    gate_id = "SCQ-01"
    name = "场景结构完整性"
    description = "场景必须有清晰的目标-冲突-结果结构"


class SCQ02_SequelStructure(SST02_CausalChain):
    gate_id = "SCQ-02"
    name = "续篇结构完整性"
    description = "续篇必须有反应-困境-决定结构"


class SCQ03_SceneSequelAlternation(SST03_SceneSequelRhythm):
    gate_id = "SCQ-03"
    name = "场景续篇交替"
    description = "Scene与Sequel必须交替出现"


class SCQ04_MotivationReaction(BaseGate):
    gate_id = "SCQ-04"
    name = "动机反应链"
    description = "角色的行为必须有内在动机"
    severity = GateSeverity.WARN

    def evaluate(self, has_clear_motivation: bool, has_visible_reaction: bool) -> GateResult:
        if not has_clear_motivation:
            return self.fail_result(message="角色行动缺乏清晰的内在动机")
        if not has_visible_reaction:
            return self.fail_result(message="角色应对事件缺乏可见的外部反应")
        return self.pass_result()


class SCQ05_ProactiveProtagonist(BaseGate):
    gate_id = "SCQ-05"
    name = "主角主动性"
    description = "主角应该是行动的发起者而非被动反应的接收者"
    severity = GateSeverity.WARN

    def evaluate(self, proactive_actions: int, reactive_actions: int) -> GateResult:
        total = proactive_actions + reactive_actions
        if total < 3:
            return self.pass_result(message="数据不足")
        ratio = proactive_actions / total
        if ratio < 0.3:
            return self.fail_result(
                message=f"主角主动性偏低（{proactive_actions}/{total}）",
                details={"ratio": round(ratio, 2)},
            )
        return self.pass_result()