"""大纲规划系统 — WriteHERE 递归分解 + GOAT/MICE/Dramatica 标注

OutlineNode: 递归嵌套大纲节点（act/chapter/scene/beat 四级）
StoryOutline: 项目大纲根 + 模板 + 持久化
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

TEMPLATE_IDS = ("three_act", "hero_journey", "save_the_cat", "story_circle")

TEMPLATE_STRUCTURES = {
    "three_act": ["第一幕：建立", "第二幕：对抗", "第三幕：解决"],
    "hero_journey": ["启程", "启蒙", "归来"],
    "save_the_cat": [
        "布局",
        "争论",
        "乐趣与游戏",
        "中点",
        "坏人逼近",
        "一无所有",
        "灵魂黑夜",
        "第三幕",
        "终场",
    ],
    "story_circle": [
        "舒适区",
        "需求",
        "进入陌生",
        "适应搜索",
        "得到想要的",
        "付出代价",
        "回归",
        "改变",
    ],
}


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class OutlineNode:
    """大纲节点——支持递归嵌套"""

    id: str
    level: str  # act / chapter / scene / beat
    title: str
    description: str = ""
    children: list[OutlineNode] = field(default_factory=list)
    status: str = "planned"  # planned / writing / draft / revised / complete
    word_target: int = 0
    word_actual: int = 0
    methodology_source: str = ""

    # GOAT 故事值电荷
    story_value: str = "neutral"  # positive / negative / neutral
    story_charge: str = "none"  # positive_to_negative / negative_to_positive / none

    # Dramatica 四视角
    primary_pov: str = "objective"  # objective / main / impact / relationship

    # MICE 嵌套
    mice_type: str = ""  # milieu / idea / character / event
    mice_open_chapter: int = 0
    mice_close_chapter: int = 0

    # Freytag/Yorke 高潮位置
    climax_position: float = 0.0  # 0.625=Freytag 0.85=Yorke

    # ── 序列化 ──

    def to_dict(self) -> dict:
        d = asdict(self)
        d["children"] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> OutlineNode:
        children = [cls.from_dict(c) for c in data.pop("children", [])]
        return cls(
            **{k: v for k, v in data.items() if k in cls.__dataclass_fields__}, children=children
        )

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def chapters_flat(self) -> list[OutlineNode]:
        return [n for n in self.walk() if n.level == "chapter"]


@dataclass
class StoryOutline:
    """完整故事大纲"""

    project_id: str = ""
    template: str = "three_act"
    root: OutlineNode | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def to_json(self) -> str:
        return json.dumps(
            {
                "project_id": self.project_id,
                "template": self.template,
                "root": self.root.to_dict() if self.root else None,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )

    @classmethod
    def from_json(cls, raw: str) -> StoryOutline:
        data = json.loads(raw)
        root = OutlineNode.from_dict(data["root"]) if data.get("root") else None
        return cls(
            project_id=data.get("project_id", ""),
            template=data.get("template", "three_act"),
            root=root,
        )

    # ── MICE LIFO 合法性（G15） ──

    def validate_mice_lifo(self) -> list[dict]:
        """MICE 线程必须 LIFO 闭合（嵌套线索后开先闭）"""
        stack: list[OutlineNode] = []
        violations = []
        order = 0
        for node in self.root.walk() if self.root else []:
            if not node.mice_type:
                continue
            order += 1
            if node.mice_open_chapter and not node.mice_close_chapter:
                stack.append(node)  # 开启
            elif node.mice_close_chapter:
                # 找栈顶匹配同类型
                if stack and stack[-1].mice_type == node.mice_type:
                    stack.pop()  # LIFO 合规闭合
                else:
                    # 检查栈内是否存在同类型（跨层闭合 = 违规）
                    in_stack = any(n.mice_type == node.mice_type for n in stack)
                    if in_stack:
                        violations.append(
                            {
                                "rule": "mice_lifo",
                                "node": node.title,
                                "detail": f"「{node.mice_type}」线程跨越外层线程闭合（应后开先闭）",
                            }
                        )
                        stack = [n for n in stack if n.mice_type != node.mice_type]
        # 未闭合线程
        violations.extend(
            {
                "rule": "mice_unclosed",
                "node": unclosed.title,
                "detail": f"「{unclosed.mice_type}」线程从未闭合",
            }
            for unclosed in stack
        )
        return violations
