from __future__ import annotations
"""角色弧光 + 长篇节奏 + 转折质量 + 断章/付费点门禁。"""

from .base import BaseGate
from wenjian.models import GateSeverity


# ─── 角色弧光深度模型（Truby 22步法 + Egri三位一体） ───

class ARC01_ScarReveal(BaseGate):
    """角色伤疤必须在故事前 1/3 揭示。"""
    gate_id = "ARC-01"
    name = "角色伤疤揭示门禁"
    description = "角色的核心创伤（伤疤）必须在故事前 1/3 内揭示"
    severity = GateSeverity.WARN

    def evaluate(self, position_pct: float, scar_revealed: bool) -> GateResult:
        if position_pct > 33 and not scar_revealed:
            return self.fail_result(message=f"故事已过 {position_pct:.0f}%，角色核心伤疤未揭示", details={"position": position_pct, "scar_revealed": False})
        return self.pass_result(details={"position": position_pct})


class ARC02_DesireConflict(BaseGate):
    """欲望与需求必须冲突。"""
    gate_id = "ARC-02"
    name = "欲望需求冲突门禁"
    description = "自觉欲望与不自觉需求必须存在冲突——两者矛盾越大，角色张力越强"
    severity = GateSeverity.WARN

    def evaluate(self, conscious_desire: str, unconscious_need: str, conflict_score: int = 0) -> GateResult:
        if conflict_score < 3:
            return self.fail_result(
                message=f"欲望('{conscious_desire}')与需求('{unconscious_need}')冲突度 {conflict_score}/5，两者没有真正的矛盾",
                details={"desire": conscious_desire, "need": unconscious_need, "conflict": conflict_score},
            )
        return self.pass_result(details={"conflict": conflict_score})


class ARC03_WeaknessCost(BaseGate):
    """角色的弱点必须在关键场景中造成实际代价。"""
    gate_id = "ARC-03"
    name = "弱点代价门禁"
    description = "角色的性格弱点必须在至少一个关键场景中导致损失——否则它不是弱点"
    severity = GateSeverity.WARN

    def evaluate(self, weakness: str, cost_scenes: int, total_scenes: int) -> GateResult:
        if cost_scenes < 1:
            return self.fail_result(message=f"弱点'{weakness}'没有造成任何实际代价——读者不会觉得它是个弱点", details={"weakness": weakness, "cost_scenes": 0})
        if total_scenes > 20 and cost_scenes < 2:
            return self.fail_result(message=f"整本书只展现了 {cost_scenes} 次弱点的代价，建议至少 2-3 次递进", details={"weakness": weakness, "cost_scenes": cost_scenes, "total": total_scenes})
        return self.pass_result(details={"cost_scenes": cost_scenes})


class ARC04_Transformation(BaseGate):
    """蜕变必须在高潮中体现。"""
    gate_id = "ARC-04"
    name = "角色蜕变门禁"
    description = "角色的内在改变必须在故事高潮中得到最终验证"
    severity = GateSeverity.BLOCK

    def evaluate(self, has_climax_change: bool, initial_flaw: str, final_state: str) -> GateResult:
        if not has_climax_change:
            return self.fail_result(
                message=f"角色从'{initial_flaw}'到'{final_state}'的蜕变没有得到高潮验证——读者不觉得角色真的变了",
                details={"initial_flaw": initial_flaw, "final_state": final_state},
            )
        if initial_flaw == final_state:
            return self.fail_result(message=f"角色从头到尾没有改变——这不是角色弧光，是角色静止", details={"no_change": True})
        return self.pass_result(details={"change": f"{initial_flaw} → {final_state}"})


# ─── 长篇节奏模型 ──────────────────────────────────────

class ARC05_LengthAwarePacing(BaseGate):
    """长篇节奏门禁 — 不同长度使用不同节奏参数。"""
    gate_id = "ARC-05"
    name = "长篇节奏门禁"
    description = "30 章和 3000 章的故事节奏完全不同，根据预估长度调整参数"
    severity = GateSeverity.WARN

    def evaluate(self, projected_chapters: int, current_chapter: int, chapters_since_arc_reset: int) -> GateResult:
        if projected_chapters > 500:
            max_reset = {"short": 10, "medium": 20, "long": 5}.get(
                "short" if projected_chapters < 100 else "medium" if projected_chapters < 500 else "long", 10
            )
            if chapters_since_arc_reset > max_reset * 2:
                return self.fail_result(message=f"长篇 ({projected_chapters} 章) 需要周期性的弧线重置——当前弧持续了 {chapters_since_arc_reset} 章", details={"projected": projected_chapters, "since_reset": chapters_since_arc_reset})
        return self.pass_result(details={"projected": projected_chapters})


class ARC06_PayoffDelay(BaseGate):
    """最大铺垫章数门禁。"""
    gate_id = "ARC-06"
    name = "铺垫延迟门禁"
    description = "长篇最长的铺垫弧不应超过总章数的 15%，短篇不应超过总章数的 25%"
    severity = GateSeverity.WARN

    def evaluate(self, longest_setup_chapters: int, projected_chapters: int) -> GateResult:
        ratio = longest_setup_chapters / max(projected_chapters, 1)
        limit = 0.25 if projected_chapters < 100 else 0.15
        if ratio > limit:
            return self.fail_result(message=f"最长铺垫弧 {longest_setup_chapters} 章占总长 {ratio:.0%}，{self._length_label(projected_chapters)}不应超过 {limit:.0%}", details={"setup": longest_setup_chapters, "total": projected_chapters, "ratio": round(ratio, 2), "limit": limit})
        return self.pass_result(details={"ratio": round(ratio, 2), "limit": limit})

    def _length_label(self, chapters: int) -> str:
        return "短篇" if chapters < 100 else "中篇" if chapters < 500 else "长篇"


# ─── 转折质量门禁（surprising yet inevitable） ────────

class ARC07_TurnQuality(BaseGate):
    """转折质量评分门禁。"""
    gate_id = "ARC-07"
    name = "转折质量门禁"
    description = "好的转折应该'意料之外，情理之中'——意外度 + 必然度 + 影响度 + 连锁反应"
    severity = GateSeverity.WARN

    def evaluate(self, surprise: int, inevitability: int, impact: int, has_chain_reaction: bool) -> GateResult:
        total = surprise + inevitability + impact
        issues = []
        if surprise < 3:
            issues.append(f"意外度 {surprise}/5 — 转折太容易猜到")
        if inevitability < 3:
            issues.append(f"必然度 {inevitability}/5 — 转折缺乏伏笔支撑，显得机械降神")
        if impact < 3:
            issues.append(f"影响度 {impact}/5 — 转折没有改变任何价值观")
        if not has_chain_reaction:
            issues.append("缺少连锁反应 — 转折后没有后续影响")
        if issues:
            return self.fail_result(message="；".join(issues), details={"surprise": surprise, "inevitability": inevitability, "impact": impact, "chain": has_chain_reaction})
        return self.pass_result(details={"total": total, "quality": "high" if total >= 12 else "medium"})


# ─── 断章/付费点设计 ───────────────────────────────────

class ARC08_ChapterBreak(BaseGate):
    """断章质量门禁。"""
    gate_id = "ARC-08"
    name = "断章质量门禁"
    description = "章末必须有未解决的问题或新信息——驱动读者点下一章"
    severity = GateSeverity.WARN

    def evaluate(self, has_unresolved: bool, has_new_info: bool, is_vip_chapter: bool = False, has_pleasure_near_end: bool = False) -> GateResult:
        issues = []
        if not has_unresolved and not has_new_info:
            issues.append("章末既无未解决问题也无新信息——读者没有理由点下一章")
        if is_vip_chapter and not has_pleasure_near_end:
            issues.append("付费章节前应有爽点——VIP 章前没有爽点，付费意愿可能低")
        if issues:
            return self.fail_result(message="；".join(issues), details={"unresolved": has_unresolved, "new_info": has_new_info})
        return self.pass_result(details={"unresolved": has_unresolved, "new_info": has_new_info})


class ARC09_DepthCheck(BaseGate):
    """每 10 章深度钩子门禁。"""
    gate_id = "ARC-09"
    name = "深度钩子门禁"
    description = "每 10 章至少应有一个'必追'级别的大钩子"
    severity = GateSeverity.WARN

    def evaluate(self, last_deep_hook_ago: int) -> GateResult:
        if last_deep_hook_ago >= 10:
            return self.fail_result(message=f"距上次深度钩子已 {last_deep_hook_ago} 章——建议在最近一章设一个强钩子", details={"since_last_hook": last_deep_hook_ago})
        return self.pass_result(details={"since_last_hook": last_deep_hook_ago})