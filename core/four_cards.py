"""四卡双向联动 — 核心数据模型（FOUR_CARD_PLAN.md §1）

设计结论：不是四个 JSON，是同一个叙事引擎的四个视图。
- 人物小传卡（CharacterBiography）—— 锚（最高优先级真源）
- 框架卡（FrameworkBeat）       —— 张力轨迹
- 章节卡（ChapterBeat）         —— 价值翻转快照
- 试样故事卡（SampleStory）     —— 验证 want/wound/lie 能否点燃的 pilot

四卡同屏审查页状态由 FourCardProject 持有；任何 AI 联动修改都以
diff_engine.Diff 提案浮出，作者批准才落地（铁律：永不静默改写）。

实现说明：计划书中以 @dataclass 示意，工程实现采用 pydantic BaseModel，
字段与默认值完全对齐，以获得模型序列化（MCP 传输 / LLM 结构化输出）能力。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# 运行时导入 diff_engine 是安全的：diff_engine 只在函数内延迟导入本模块，
# 不存在模块级循环。这里必须拿到真实 Diff 类型，pydantic 才能在
# model_validate(json) 时把 pending_diffs 反序列化为 Diff 而非 dict。
from core.diff_engine import Diff


class CharacterBiography(BaseModel):
    """人物小传卡 —— 锚。want/wound/lie/change 构成角色因果链。"""

    name: str = Field(description="角色名", default="未命名主角")
    want: str = Field(description="具体到「失败可见」的欲望，如'夺回家族当铺'", default="")
    wound: str = Field(description="塑造他的创伤，如'七岁被至亲当众遗弃'", default="")
    lie: str = Field(description="错误信念/生存法则，如'对人交心等于死于背叛'", default="")
    change: str = Field(description="高潮时放弃或死守这个谎，如'最后把刀递给仇人'", default="")
    voice_traits: list[str] = Field(default_factory=list, description="口吻标记（persona）")


class FrameworkBeat(BaseModel):
    """框架卡 —— 张力轨迹。每个 beat 标注价值翻转方向与张力来源。"""

    index: int = Field(description="beats 序号", default=0)
    goal: str = Field(description="本 beat 要碾过谁的哪个 wound/lie", default="")
    value_turn: str = Field(description="价值翻转方向：正→负 / 负→正", default="负→正")
    tension_source: str = Field(
        description="张力来源，对应 tom_engine TensionType：信念冲突/戏剧反讽/递归错位/秘密暴露风险/目标冲突",
        default="目标冲突",
    )


class ChapterBeat(BaseModel):
    """章节卡 —— 翻转快照。"""

    summary: str = Field(description="本章剧情摘要", default="")
    value_turn: str = Field(description="价值翻转方向：正→负 / 负→正", default="正→负")
    causally_linked: bool = Field(
        description="与该章前因后果是否'因为…所以'，而非'然后'", default=False
    )


class SampleStory(BaseModel):
    """试样故事卡 —— pilot。验证 want/wound/lie 能否点燃场景。"""

    text: str = Field(description="试样故事原文", default="")
    transportation_score: float = Field(
        description="reader_model 沉浸度评分 0-100，非空表示已完成评估", default=0.0
    )


class FourCardProject(BaseModel):
    """四卡同屏的审查页状态。"""

    biographies: list[CharacterBiography] = Field(default_factory=list)  # 锚
    framework: list[FrameworkBeat] = Field(default_factory=list)
    chapters: list[ChapterBeat] = Field(default_factory=list)
    sample: SampleStory = Field(default_factory=SampleStory)
    pending_diffs: list[Diff] = Field(default_factory=list)

    # ─── 便捷构造 ───

    @classmethod
    def empty(cls) -> FourCardProject:
        return cls(biographies=[], framework=[], chapters=[], sample=SampleStory())

    def add_diff(self, diff) -> None:
        """登记一条待批准提案（status=pending 时进入 pending_diffs）。"""
        if getattr(diff, "status", "pending") == "pending":
            self.pending_diffs.append(diff)

    def card_summary(self) -> dict:
        """供 UI / MCP 输出的轻量摘要。"""
        return {
            "biography_count": len(self.biographies),
            "framework_beats": len(self.framework),
            "chapter_beats": len(self.chapters),
            "transportation_score": self.sample.transportation_score,
            "pending_diff_count": len(self.pending_diffs),
            "anchored": all(b.want and b.wound and b.lie for b in self.biographies),
        }
