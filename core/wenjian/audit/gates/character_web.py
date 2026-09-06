from __future__ import annotations
"""角色关系网门禁 — 基于 John Truby《The Anatomy of Story》。

Truby 核心：角色不由他们"是谁"定义，由"和谁有什么关系"定义。
一个角色 = 他与所有其他角色的关系之和。
角色弧光 = 这个关系网络的整体变化。
"""

from .base import BaseGate
from wenjian.models import GateSeverity


class CR01_RelationshipChange(BaseGate):
    """两个角色之间的关系必须在故事中发生至少一次变化。"""
    gate_id = "CR-01"
    name = "关系变化门禁"
    description = "故事中每对主要角色之间的关系必须发生至少一次有意义的变化"
    severity = GateSeverity.WARN

    def evaluate(self, character_a: str, character_b: str, relationship: str, has_changed: bool, change_at_chapter: int = 0) -> GateResult:
        if not has_changed:
            return self.fail_result(
                message=f"角色 {character_a} 和 {character_b} 的 {relationship} 关系从开头到结尾没有变化",
                details={"pair": f"{character_a}-{character_b}", "relationship": relationship},
            )
        if change_at_chapter and change_at_chapter > 20:
            return self.fail_result(
                message=f"角色 {character_a} 和 {character_b} 的关系在第 {change_at_chapter} 章才变化，偏晚",
                details={"change_at": change_at_chapter},
            )
        return self.pass_result()


class CR02_WebDensity(BaseGate):
    """关系网络密度——有意义的活跃关系至少占角色数的 50%。"""
    gate_id = "CR-02"
    name = "关系网密度门禁"
    description = "有意义的活跃关系至少占角色数的50%"
    severity = GateSeverity.WARN

    def evaluate(self, character_count: int, active_relationships: int) -> GateResult:
        expected_min = max(2, character_count // 2)
        if active_relationships < expected_min:
            return self.fail_result(
                message=f"有 {character_count} 个角色但只有 {active_relationships} 条活跃关系线（期望至少 {expected_min} 条）",
                details={"characters": character_count, "active": active_relationships, "expected_min": expected_min},
            )
        return self.pass_result(details={"active_relations": active_relationships})


class CR03_RoleDiversity(BaseGate):
    """关系类型多样性——每个角色至少扮演 2 种关系角色。"""
    gate_id = "CR-03"
    name = "角色类型多样性门禁"
    description = "每个主要角色至少扮演2种关系角色"
    severity = GateSeverity.WARN

    def evaluate(self, roles: dict) -> GateResult:
        missing = [char for char, role_count in roles.items() if role_count < 2]
        if missing:
            return self.fail_result(
                message=f"缺少角色类型：{'、'.join(missing)}",
                details={"missing": missing, "roles": roles},
            )
        return self.pass_result()