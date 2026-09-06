"""递归大纲生成器 — WriteHERE（前提→幕→章→场景）+ LLM 逐层细化 + 方法论标注"""

from __future__ import annotations

import json
import re

from core.planning.outline import (
    TEMPLATE_STRUCTURES,
    OutlineNode,
    StoryOutline,
)
from core.pydantic_ai_engine import get_llm_engine

_POSITIVE_KWS = ("胜利", "发现", "成长", "获得", "成功", "和解", "突破")
_NEGATIVE_KWS = ("失败", "损失", "打击", "失去", "背叛", "死亡", "崩溃", "误会")


class OutlineGenerator:
    """递归大纲生成器"""

    def __init__(self):
        self.llm = get_llm_engine()

    # ─── 主入口 ───

    def generate(
        self, premise: str, template: str = "three_act", target_chapters: int = 12
    ) -> StoryOutline:
        template = template if template in TEMPLATE_STRUCTURES else "three_act"
        target_chapters = max(4, min(target_chapters, 60))

        # 第一层：宏观结构（幕）
        acts = self._generate_acts(premise, template)

        # 第二层：递归细化幕 → 章
        per_act = max(2, target_chapters // len(acts))
        counter = [0]
        for act in acts:
            chapters = self._generate_chapters(act, premise, per_act, counter)
            act.children = chapters

        root = OutlineNode(
            id="root",
            level="act",
            title=premise[:30] or "未命名",
            description=premise,
            children=acts,
        )
        # 第三层：方法论标注（GOAT 电荷 / Dramatica 视角 / MICE / 高潮位）
        self._annotate_story_values(root)
        self._annotate_povs(root)
        self._annotate_mice(root)
        self._annotate_climax(root, template)

        return StoryOutline(template=template, root=root)

    # ─── 生成层 ───

    def _generate_acts(self, premise: str, template: str) -> list[OutlineNode]:
        structure = TEMPLATE_STRUCTURES[template]
        if self.llm.available():
            prompt = (
                f"故事前提：{premise}\n叙事模板：{template}\n"
                f"请为每个结构段生成一段 30 字以内剧情概要。输出 JSON 数组，"
                f'每项 {{"title": "段名", "description": "概要"}}，数量必须为 {len(structure)}，'
                f"顺序对应：{structure}。只输出 JSON。"
            )
            raw = self.llm.generate_chapter(prompt, {"characters": []}, word_target=500)
            if raw:
                m = re.search(r"\[.*\]", raw, re.DOTALL)
                if m:
                    try:
                        items = json.loads(m.group(0))
                        acts = []
                        for i, s in enumerate(structure):
                            it = items[i] if i < len(items) else {}
                            title = str(it.get("title") or s)[:24]
                            acts.append(
                                OutlineNode(
                                    id=f"act_{i + 1}",
                                    level="act",
                                    title=title,
                                    description=str(it.get("description", ""))[:120],
                                )
                            )
                    except (json.JSONDecodeError, KeyError):
                        pass
                    else:
                        return acts
        return [
            OutlineNode(id=f"act_{i + 1}", level="act", title=s, description="")
            for i, s in enumerate(structure)
        ]

    def _generate_chapters(
        self, act: OutlineNode, premise: str, n: int, counter: list
    ) -> list[OutlineNode]:
        chapters: list[OutlineNode] = []
        if self.llm.available():
            prompt = (
                f"故事前提：{premise}\n当前结构段：{act.title}——{act.description}\n"
                f"请把这一段分解为 {n} 章。输出 JSON 数组，每项 "
                f'{{"title": "章节名(≤8字)", "description": "本章剧情(≤40字)"}}。只输出 JSON。'
            )
            raw = self.llm.generate_chapter(prompt, {"characters": []}, word_target=600)
            if raw:
                m = re.search(r"\[.*\]", raw, re.DOTALL)
                if m:
                    try:
                        for it in json.loads(m.group(0))[:n]:
                            if not it.get("title"):
                                continue
                            counter[0] += 1
                            chapters.append(
                                OutlineNode(
                                    id=f"ch_{counter[0]:03d}",
                                    level="chapter",
                                    title=str(it["title"])[:16],
                                    description=str(it.get("description", ""))[:80],
                                    word_target=2500,
                                )
                            )
                    except (json.JSONDecodeError, KeyError):
                        pass
        # 降级：均匀切分
        while len(chapters) < n:
            counter[0] += 1
            chapters.append(
                OutlineNode(
                    id=f"ch_{counter[0]:03d}",
                    level="chapter",
                    title=f"{act.title}·{len(chapters) + 1}",
                    description=f"{act.title}推进：冲突升级与信息揭示",
                    word_target=2500,
                )
            )
        return chapters

    # ─── 方法论标注层 ───

    def _annotate_story_values(self, node: OutlineNode):
        """GOAT: 场景正/负电荷"""
        for child in node.children:
            desc = child.description or child.title
            if any(kw in desc for kw in _POSITIVE_KWS):
                child.story_value = "positive"
            elif any(kw in desc for kw in _NEGATIVE_KWS):
                child.story_value = "negative"
            # 电荷变化：相邻章节正负翻转
            self._annotate_story_values(child)
        for a, b in zip(node.children, node.children[1:], strict=False):
            if (
                a.story_value != "neutral"
                and b.story_value != "neutral"
                and a.story_value != b.story_value
            ):
                b.story_charge = f"{a.story_value}_to_{b.story_value}"

    def _annotate_povs(self, node: OutlineNode, counter: list | None = None):
        """Dramatica: 客观/主角/影响/关系 四视角全局轮转（跨幕连续）"""
        if counter is None:
            counter = [0]
        povs = ("objective", "main", "impact", "relationship")
        for child in node.children:
            if child.children:
                self._annotate_povs(child, counter)
            else:
                child.primary_pov = povs[counter[0] % 4]
                counter[0] += 1

    def _annotate_mice(self, node: OutlineNode):
        """MICE: 按描述关键词分型 + 嵌套开闭章节"""
        for child in node.children:
            desc = child.description or child.title
            if any(kw in desc for kw in ("世界", "地点", "旅程", "抵达", "归来")):
                child.mice_type = "milieu"
            elif any(kw in desc for kw in ("问题", "谜", "真相", "调查", "秘密")):
                child.mice_type = "idea"
            elif any(kw in desc for kw in ("成长", "转变", "蜕变", "和解")):
                child.mice_type = "character"
            elif any(kw in desc for kw in ("冲突", "事件", "战斗", "危机", "背叛")):
                child.mice_type = "event"
            self._annotate_mice(child)
        # 开闭章节：本节点类型开启于首子，闭合于尾子（LIFO 友好）
        if node.mice_type and node.children:
            first, last = node.children[0], node.children[-1]
            if first is not node:
                first.mice_open_chapter = first.id.isdigit() and int(first.id.split("_")[-1]) or 0
                last.mice_close_chapter = last.id.isdigit() and int(last.id.split("_")[-1]) or 0

    def _annotate_climax(self, root: OutlineNode, template: str):
        """Freytag/Yorke: 高潮位置标注到临近结尾章节"""
        chapters = root.chapters_flat()
        if not chapters:
            return
        pos = 0.85 if template == "story_circle" else 0.625
        idx = max(0, int(len(chapters) * pos) - 1)
        chapters[idx].climax_position = pos
        chapters[idx].methodology_source = "Yorke 5幕辩证" if pos == 0.85 else "Freytag 金字塔"
