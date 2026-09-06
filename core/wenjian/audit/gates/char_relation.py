from __future__ import annotations
"""人物关系网门禁 — John Truby《The Anatomy of Story》。

核心：孤立角色不是故事，角色之间的关系网才是。
每个角色必须在关系网中有明确位置。
"""

from .base import BaseGate
from wenjian.models import GateSeverity


class CRN01_RelationshipCount(BaseGate):
    """每个主要角色至少与 2 个其他角色有实质性关系。"""
    gate_id = "CRN-01"
    name = "角色关系数量门禁"
    description = "每个主要角色至少与 2 个其他角色有实质性关系"
    severity = GateSeverity.WARN

    def evaluate(self, character_name: str, relationship_count: int) -> GateResult:
        if relationship_count < 2:
            return self.fail_result(message=f"角色'{character_name}'仅有 {relationship_count} 段实质性关系（需要至少 2 段）——孤立角色难以驱动故事", details={"character": character_name, "relationships": relationship_count})
        return self.pass_result(details={"character": character_name, "relationships": relationship_count})


class CRN02_RelationDiversity(BaseGate):
    """关系中至少 1 条冲突性、1 条支持性的。"""
    gate_id = "CRN-02"
    name = "关系多样性门禁"
    description = "一个角色的关系网中至少同时存在冲突与支持关系"
    severity = GateSeverity.WARN

    def evaluate(self, character_name: str, conflict_relationships: int, support_relationships: int) -> GateResult:
        if conflict_relationships == 0:
            return self.fail_result(message=f"角色'{character_name}'完全没有冲突关系——没有冲突的关系不会推动故事", details={"conflict": 0, "support": support_relationships})
        if support_relationships == 0:
            return self.fail_result(message=f"角色'{character_name}'完全没有支持关系——角色在故事中缺乏情感锚点", details={"conflict": conflict_relationships, "support": 0})
        return self.pass_result(details={"conflict": conflict_relationships, "support": support_relationships})


class CRN03_RelationshipEvolution(BaseGate):
    """关系必须在故事中演变。"""
    gate_id = "CRN-03"
    name = "关系演变门禁"
    description = "角色关系不能静止——每一段关系都应该在故事中发生变化"
    severity = GateSeverity.WARN

    def evaluate(self, characters_with_arcs: int, total_characters: int) -> GateResult:
        if total_characters >= 3 and characters_with_arcs < total_characters:
            static = total_characters - characters_with_arcs
            return self.fail_result(message=f"{static}/{total_characters} 个角色没有关系弧——每段关系应该在故事中发生变化", details={"with_arc": characters_with_arcs, "total": total_characters, "static": static})
        return self.pass_result(details={"with_arc": characters_with_arcs, "total": total_characters})


class CRN04_CharacterTriangle(BaseGate):
    """铁三角结构检测：主角 + 对手 + 盟友。"""
    gate_id = "CRN-04"
    name = "角色铁三角门禁"
    description = "主角、对手、盟友三者构成叙事铁三角——缺任何一个都会让故事失衡"
    severity = GateSeverity.WARN

    def evaluate(self, has_protagonist: bool, has_antagonist: bool, has_ally: bool) -> GateResult:
        missing = []
        if not has_protagonist: missing.append("主角")
        if not has_antagonist: missing.append("对手(对抗力量)")
        if not has_ally: missing.append("盟友(情感锚点)")
        if missing:
            return self.fail_result(message=f"铁三角不完整，缺少：{'、'.join(missing)}", details={"protagonist": has_protagonist, "antagonist": has_antagonist, "ally": has_ally})
        return self.pass_result()


class CRN05_OpponentDepth(BaseGate):
    """对手深度门禁。"""
    gate_id = "CRN-05"
    name = "对手深度门禁"
    description = "对手必须有自己合理的动机——不能为了坏而坏"
    severity = GateSeverity.WARN

    def evaluate(self, has_motivation: bool, motivation_clarity: int, shares_goal_with_protagonist: bool) -> GateResult:
        if not has_motivation:
            return self.fail_result(message="对手没有自己的动机——好的对手相信自己才是对的", details={"has_motivation": False})
        if motivation_clarity < 3:
            return self.fail_result(message=f"对手动机明确度 {motivation_clarity}/5——读者需要理解他为什么这么做", details={"clarity": motivation_clarity})
        if shares_goal_with_protagonist:
            return self.pass_result(details={"motivation": motivation_clarity, "note": "对手与主角追求同一目标——这是高质量的对手设计"})
        return self.pass_result(details={"motivation": motivation_clarity})