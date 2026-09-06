from __future__ import annotations
"""女频门禁 — 情感流、人设互动、甜虐比、修罗场。

现有门禁全部男频倾向（爽点、升级、打脸）。
女频的核心驱动力完全不同。
"""

from .base import BaseGate
from wenjian.models import GateSeverity


class ROE01_EmotionalTension(BaseGate):
    """情感张力门禁。"""
    gate_id = "ROE-01"
    name = "情感张力门禁"
    description = "女频核心不是冲突张力而是情感张力——暧昧/误会/推拉"
    severity = GateSeverity.WARN

    def evaluate(self, tension_count: int, word_count: int) -> GateResult:
        density = tension_count / max(word_count / 1000, 1)
        if density < 1.0 and word_count > 500:
            return self.fail_result(message=f"情感张力密度 {density:.1f}/千字——每千字至少1次暧昧/误会/推拉", details={"tension_count": tension_count, "density": round(density, 1)})
        return self.pass_result(details={"density": round(density, 1)})


class ROE02_SweetBitterRatio(BaseGate):
    """甜虐比门禁。"""
    gate_id = "ROE-02"
    name = "甜虐比门禁"
    description = "甜虐比 ≈ 7:3，连续虐不超过 2 章"
    severity = GateSeverity.WARN

    def evaluate(self, sweet_count: int, bitter_count: int, consecutive_bitter: int) -> GateResult:
        total = sweet_count + bitter_count
        issues = []
        if total > 0:
            ratio = sweet_count / total
            if ratio < 0.5:
                issues.append(f"甜:虐 = {sweet_count}:{bitter_count}，建议 7:3")
        if consecutive_bitter > 2:
            issues.append(f"连续虐 {consecutive_bitter} 章，超过 2 章上限")
        if issues:
            return self.fail_result(message="；".join(issues), details={"sweet": sweet_count, "bitter": bitter_count, "consecutive_bitter": consecutive_bitter})
        return self.pass_result(details={"ratio": f"{sweet_count}:{bitter_count}"})


class ROE03_CPChemistry(BaseGate):
    """CP 感门禁。"""
    gate_id = "ROE-03"
    name = "CP感门禁"
    description = "主角与主要感情线对象间的互动化学反应"
    severity = GateSeverity.WARN

    def evaluate(self, meaningful_interactions: int, total_interactions: int, unique_scenarios: int) -> GateResult:
        if total_interactions >= 3 and meaningful_interactions / total_interactions < 0.3:
            return self.fail_result(message=f"有效互动占比 {meaningful_interactions}/{total_interactions}——CP互动的每句话应该有潜台词", details={"meaningful": meaningful_interactions, "total": total_interactions})
        if total_interactions >= 3 and unique_scenarios < 2:
            return self.fail_result(message=f"CP互动场景单一（{unique_scenarios}种）——建议在不同场景下展现关系", details={"scenarios": unique_scenarios})
        return self.pass_result(details={"meaningful_ratio": round(meaningful_interactions / max(total_interactions, 1), 2)})


class ROE04_MisunderstandingCycle(BaseGate):
    """误会循环门禁。"""
    gate_id = "ROE-04"
    name = "误会循环门禁"
    description = "同一个误会循环使用超过 3 次会引发读者厌烦"
    severity = GateSeverity.WARN

    def evaluate(self, same_misunderstanding_count: int, resolved: bool) -> GateResult:
        if same_misunderstanding_count >= 3 and not resolved:
            return self.fail_result(message=f"同一个误会循环使用了 {same_misunderstanding_count} 次仍未解决——读者已经看懂了，角色还在误会", details={"count": same_misunderstanding_count, "resolved": False})
        if same_misunderstanding_count >= 5:
            return self.fail_result(message=f"同一个误会使用了 {same_misunderstanding_count} 次——严重消耗读者耐心", details={"count": same_misunderstanding_count})
        return self.pass_result(details={"count": same_misunderstanding_count})


class ROE05_DetailSugar(BaseGate):
    """细节糖门禁。"""
    gate_id = "ROE-05"
    name = "细节糖门禁"
    description = "女频的情感推进往往靠小动作、微表情、细节——不是大情节"
    severity = GateSeverity.WARN

    def evaluate(self, detail_sugar_count: int, emotional_beat_count: int) -> GateResult:
        if emotional_beat_count > 0 and detail_sugar_count < emotional_beat_count:
            return self.fail_result(message=f"情感推进 {emotional_beat_count} 次，细节糖仅 {detail_sugar_count}——女频的情感靠细节展现，不是靠情节推动", details={"detail_sugar": detail_sugar_count, "emotional_beats": emotional_beat_count})
        return self.pass_result(details={"detail_sugar": detail_sugar_count})


class ROE06_LoveRivalDensity(BaseGate):
    """修罗场密度门禁。"""
    gate_id = "ROE-06"
    name = "修罗场密度门禁"
    description = "多个感情线纠缠、情敌出现的节奏"
    severity = GateSeverity.WARN

    def evaluate(self, love_interest_count: int, rivalry_scenes: int, chapters_covered: int) -> GateResult:
        if love_interest_count >= 3 and rivalry_scenes < 2 and chapters_covered > 10:
            return self.fail_result(message=f"有 {love_interest_count} 条感情线但 {chapters_covered} 章内仅有 {rivalry_scenes} 场修罗场——存在多角关系但没有碰撞", details={"interests": love_interest_count, "rivalry": rivalry_scenes})
        return self.pass_result(details={"interests": love_interest_count, "rivalry_per_10ch": round(rivalry_scenes / max(chapters_covered / 10, 1), 1)})