from __future__ import annotations
"""Netflix Redundancy gates — 第二屏信息冗余门禁.

核心原则：关键信息必须在信道中重复，因为接收方可能没在看（第二屏读者）。
在小说中对应：核心设定、角色目标、伏笔等需要周期性复述。
"""

from .base import BaseGate
from wenjian.models import GateResult, GateSeverity


class NFR01_CoreSettingRecap(BaseGate):
    """核心设定是否每 3-4 章被复述一次。"""

    gate_id = "NFR-01"
    name = "核心设定复述门禁"
    description = "核心世界观设定必须在每 3-4 章内被自然复述一次，防止跳读读者丢失上下文"
    severity = GateSeverity.WARN

    def evaluate(self, chapters_since_last_recap: int, max_interval: int = 4) -> GateResult:
        if chapters_since_last_recap > max_interval:
            return self.fail_result(
                message=f"核心设定已{chapters_since_last_recap}章未被复述（建议每{max_interval}章复述一次）",
                details={"chapters_since": chapters_since_last_recap, "max_interval": max_interval},
            )
        return self.pass_result(details={"chapters_since": chapters_since_last_recap})


class NFR02_CharacterGoalRestatement(BaseGate):
    """角色核心目标是否在关键时刻被再次声明。"""

    gate_id = "NFR-02"
    name = "角色目标重申门禁"
    description = "主角的核心目标必须在每 3 章内被自然重申一次（可通过对话、内心独白等）"
    severity = GateSeverity.WARN

    def evaluate(self, chapters_since_restated: int, max_interval: int = 3) -> GateResult:
        if chapters_since_restated > max_interval:
            return self.fail_result(
                message=f"主角目标已{chapters_since_restated}章未被重申（建议每{max_interval}章重申一次）",
                details={"chapters_since": chapters_since_restated, "max_interval": max_interval},
            )
        return self.pass_result(details={"chapters_since": chapters_since_restated})


class NFR03_ForeshadowRepeat(BaseGate):
    """伏笔在回收前至少被提及 2 次。"""

    gate_id = "NFR-03"
    name = "伏笔重复门禁"
    description = "关键伏笔在回收前必须在不同位置被至少提及 2 次（不是 1 次），保证跳读读者也能注意到"
    severity = GateSeverity.BLOCK

    def evaluate(self, gap_id: str, mention_count: int, min_mentions: int = 2) -> GateResult:
        if mention_count < min_mentions:
            return self.fail_result(
                message=f"伏笔'{gap_id}'仅被提及{mention_count}次（需要{min_mentions}次，含回收时的揭示）",
                details={"gap_id": gap_id, "mentions": mention_count, "min_required": min_mentions},
            )
        return self.pass_result(details={"gap_id": gap_id, "mentions": mention_count})


class NFR04_JumpReaderAnchor(BaseGate):
    """每章前 200 字存在跳读锚点（可独立理解的叙事锚句）。"""

    gate_id = "NFR-04"
    name = "跳读锚点门禁"
    description = "每章前 200 字应包含一句即使跳过前文也能独立理解的锚句，为跳读读者恢复上下文"
    severity = GateSeverity.WARN

    def evaluate(self, opening_text: str, chapter_number: int) -> GateResult:
        """Check if the chapter opening contains context-anchoring elements."""
        if chapter_number == 1:
            return self.pass_result(message="首章无需跳读锚点")

        # Heuristic: check for references to previous events
        recap_markers = ["前面", "之前", "上回", "上次", "刚才", "那时",
                         "经过", "自从", "从那以后", "还记得"]
        character_refs = ["他", "她", "他们", "这个", "那个"]

        opening = opening_text[:200]
        has_recap = any(m in opening for m in recap_markers)
        has_char_ref = any(m in opening for m in character_refs)

        if not has_recap and not has_char_ref:
            return self.fail_result(
                message=f"第{chapter_number}章前200字无上下文锚点，跳读读者可能无法恢复理解",
                details={"chapter": chapter_number, "has_recap_marker": has_recap, "has_character_ref": has_char_ref,
                         "suggestion": "加入回顾性短语，如'经过前几日的调查'" },
            )
        return self.pass_result(details={"chapter": chapter_number, "has_recap_marker": has_recap})


class NFR05_SubtextLayer(BaseGate):
    """每章至少 1 个深层叙事层内容（给专注读者的奖励）。

    show AND tell 的双层编码：主叙事层所有人能跟上，深层叙事层仅专注读者能获得。
    """

    gate_id = "NFR-05"
    name = "双层编码门禁"
    description = "每章应包含至少 1 个深层叙事层内容（微表情/环境细节/器物象征），奖励专注读者"
    severity = GateSeverity.WARN

    def evaluate(self, has_deep_layer: bool, chapter_number: int) -> GateResult:
        if not has_deep_layer:
            return self.fail_result(
                message=f"第{chapter_number}章缺少深层叙事层内容",
                details={"chapter": chapter_number, "suggestion": "加入一个环境细节或器物象征作为深层回报"},
            )
        return self.pass_result(details={"chapter": chapter_number})