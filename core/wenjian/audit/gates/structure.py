from __future__ import annotations
"""结构门禁 — 断章钩子、场景目标、节奏冰火七重天。

断章钩子（网文核心）：
  每章结尾必须给读者一个"翻页理由"。
  来源：起点中文网二十年实战。

场景目标（Egri《戏剧写作艺术》）：
  每个场景必须有不可替代的目的——去掉它故事不受影响就是废场景。

节奏冰火七重天（网文圈）：
  常见的 7 章节奏周期：起→承→转→合→抑→扬→爆
"""

from .base import BaseGate
from wenjian.models import GateSeverity


class STR01_ChapterHook(BaseGate):
    """每章章末钩子检测。"""
    gate_id = "STR-01"
    name = "断章钩子门禁"
    description = "每章结尾必须有让读者想继续读的钩子"
    severity = GateSeverity.WARN

    def evaluate(self, hook_intensity: int, chapter_number: int, hook_type: str = "") -> GateResult:
        if hook_intensity < 2:
            return self.fail_result(
                message=f"第 {chapter_number} 章结尾钩子强度 {hook_intensity}/5，建议至少 2/5",
                details={"chapter": chapter_number, "intensity": hook_intensity, "type": hook_type},
            )
        return self.pass_result(details={"chapter": chapter_number, "intensity": hook_intensity})


class STR02_SceneObjective(BaseGate):
    """每个场景必须有不可替代的目的。"""
    gate_id = "STR-02"
    name = "场景目标门禁"
    description = "每个场景必须有不可替代的目的——去掉它故事是否受影响"
    severity = GateSeverity.BLOCK

    def evaluate(self, scene_id: str, has_irreplaceable_purpose: bool, purpose_category: str = "") -> GateResult:
        if not has_irreplaceable_purpose:
            return self.fail_result(
                message=f"场景 '{scene_id}' 没有不可替代的目的——删掉它故事不受影响",
                details={"scene": scene_id, "suggestion": "问问：这个场景要么推进剧情、要么塑造角色、要么提供关键信息。如果都不满足，删掉它。"},
            )
        return self.pass_result(details={"scene": scene_id, "purpose": purpose_category})


class STR03_SceneStructure(BaseGate):
    """场景结构完整性：目标→障碍→结果→转折。"""
    gate_id = "STR-03"
    name = "场景结构门禁"
    description = "完整场景应有：目标→障碍→结果→转折"
    severity = GateSeverity.WARN

    def evaluate(self, has_goal: bool, has_obstacle: bool, has_result: bool, has_turn: bool) -> GateResult:
        missing = []
        if not has_goal: missing.append("角色目标")
        if not has_obstacle: missing.append("遭遇障碍")
        if not has_result: missing.append("场景结果")
        if not has_turn: missing.append("价值翻转")
        if missing:
            return self.fail_result(message=f"场景结构不完整，缺少：{'、'.join(missing)}", details={"elements": {"goal": has_goal, "obstacle": has_obstacle, "result": has_result, "turn": has_turn}})
        return self.pass_result()


class STR04_SevenLayerRhythm(BaseGate):
    """节奏冰火七重天：起→承→转→合→抑→扬→爆。"""
    gate_id = "STR-04"
    name = "七重节奏门禁"
    description = "检测 7 章节奏周期：起承转合抑扬爆"
    severity = GateSeverity.WARN

    def evaluate(self, recent_chapter_types: list, current_position: int) -> GateResult:
        """recent_chapter_types: 最近章节的节奏类型列表。"""
        ideal_cycle = ["起", "承", "转", "合", "抑", "扬", "爆"]
        if len(recent_chapter_types) < 3:
            return self.pass_result(message="章节不足 3 章，跳过节奏检查")

        # 检查连续同一类型
        recent = recent_chapter_types[-3:]
        if len(set(recent)) == 1:
            return self.fail_result(
                message=f"连续 3 章都是 '{recent[0]}' 型节奏，读者会感到单调。建议按照 起→承→转→合→抑→扬→爆 的节奏安排。",
                details={"recent_types": recent_chapter_types[-5:], "cycle": ideal_cycle},
            )

        # 检查高潮间隔
        climax_positions = [i for i, t in enumerate(recent_chapter_types) if t in ("扬", "爆")]
        if climax_positions and current_position - climax_positions[-1] > 7:
            return self.fail_result(
                message=f"距上次'扬/爆'章已超过 7 章，读者可能进入阅读疲劳期",
                details={"since_last_climax": current_position - climax_positions[-1]},
            )

        return self.pass_result(details={"recent_types": recent_chapter_types[-5:]})


class STR05_SceneRemovability(BaseGate):
    """全场景删除测试——如果删掉不影响主线就是废场景。"""
    gate_id = "STR-05"
    name = "废场景检测门禁"
    description = "如果删除这个场景后故事主线不受影响，它就是废场景"
    severity = GateSeverity.WARN

    def evaluate(self, removable: bool, scene_id: str) -> GateResult:
        if removable:
            return self.fail_result(
                message=f"场景 '{scene_id}' 删除后主线不受影响",
                details={"scene": scene_id, "verdict": "废场景——要么赋予它不可替代的功能，要么删掉"},
            )
        return self.pass_result(details={"scene": scene_id})


class STR06_ChapterLengthConsistency(BaseGate):
    """章节长度一致性检测。"""
    gate_id = "STR-06"
    name = "章节长度一致性门禁"
    description = "章节长度不宜剧烈波动"
    severity = GateSeverity.WARN

    def evaluate(self, current_length: int, avg_length: float, max_deviation_pct: float = 0.5) -> GateResult:
        if avg_length == 0:
            return self.pass_result()
        deviation = abs(current_length - avg_length) / avg_length
        if deviation > max_deviation_pct:
            return self.fail_result(
                message=f"本章 {current_length} 字，偏离均值 {avg_length:.0f} 的 {deviation:.0%}（上限 {max_deviation_pct:.0%}）",
                details={"current": current_length, "avg": round(avg_length), "deviation_pct": round(deviation, 2)},
            )
        return self.pass_result(details={"deviation_pct": round(deviation, 2)})