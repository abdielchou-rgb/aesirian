"""多层上下文组装器 — NovelAI 分层注入 + Morpheus 三层记忆

复用 ProjectStore（角色信念/章节/伏笔均已持久化），
按 ContextLayer 优先级组装，带 token 预算控制与分层可观测。
"""
from __future__ import annotations

import json
from core.context.engine import ContextLayer, ContextConfig, AssembledContext


class ContextAssembler:
    """多层上下文组装器"""

    def __init__(self, store, config: ContextConfig | None = None):
        self.store = store
        self.config = config or ContextConfig()

    # ─── 主入口 ───

    def assemble(self, project_id: str, user_input: str = "",
                 current_chapter: int = 0) -> AssembledContext:
        result = AssembledContext()
        budget = self.config.max_tokens

        builders = [
            (ContextLayer.PROJECT, self._build_project),
            (ContextLayer.CHARACTERS, self._build_characters),
            (ContextLayer.RECENT, self._build_recent),
            (ContextLayer.EPISODIC, self._build_episodic),
            (ContextLayer.DERIVED, self._build_derived),
        ]
        for layer, builder in builders:
            if not self.config.layers.get(layer):
                continue
            section = builder(project_id, user_input, current_chapter)
            if not section:
                continue
            cost = self._count_tokens(section)
            if result.total_tokens + cost > budget:
                continue  # 预算内优先级让位
            result.sections[layer.name] = section
            result.token_estimates[layer.name] = cost
            result.total_tokens += cost

        # L5 用户输入永远注入
        if user_input:
            section = f"## 用户当前输入\n{user_input}"
            result.sections[ContextLayer.USER.name] = section
            result.token_estimates[ContextLayer.USER.name] = self._count_tokens(section)

        result.text = "\n\n".join(result.sections.values())
        return result

    # ─── 分层构建 ───

    def _build_project(self, project_id, user_input, chapter) -> str:
        p = self.store.get_project(project_id)
        if not p:
            return ""
        lines = ["## 故事设定",
                 f"标题：{p.title}",
                 f"类型：{p.genre}"]
        if p.premise:
            lines.append(f"前提：{p.premise[:200]}")
        return "\n".join(lines)

    def _build_characters(self, project_id, user_input, chapter) -> str:
        chars = self.store.get_characters(project_id)
        if not chars:
            return ""
        level = self.config.character_detail_level
        if level == "names_only":
            return "## 角色名单\n" + "、".join(c.name for c in chars[:12])
        lines = ["## 角色档案"]
        for c in chars[:10]:
            lines.append(f"\n### {c.name}（{c.role or '未定'}）")
            if level == "summary":
                continue
            beliefs = self._load_json(c.beliefs_json, {})
            goals = self._load_json(c.goals_json, [])
            for prop, b in list(beliefs.items())[:5]:
                if isinstance(b, dict):
                    lines.append(f"- 相信「{prop}」= {b.get('value')}"
                                 f"（置信 {float(b.get('confidence', 1.0)):.0%}）")
            for g in goals[:3]:
                d = g.get("description", g) if isinstance(g, dict) else g
                if d:
                    lines.append(f"- 目标：{d}")
        return "\n".join(lines)

    def _build_recent(self, project_id, user_input, chapter) -> str:
        chapters = self.store.get_chapters(project_id)
        if not chapters:
            return ""
        picked = chapters
        if self.config.enable_retrieval and user_input:
            picked = self._retrieve_relevant(chapters, user_input)
        picked = picked[-self.config.recent_chapters:]
        if not picked:
            return ""
        lines = ["## 最近章节"]
        for ch in picked:
            summary = ch.text[:200] + "…" if len(ch.text) > 200 else ch.text
            lines.append(f"\n### 第{ch.number}章 {ch.title}\n{summary}")
        return "\n".join(lines)

    def _build_episodic(self, project_id, user_input, chapter) -> str:
        """Morpheus L2：情景记忆——各章审计轨迹（分数+跨章冲突+线索变化）"""
        chapters = self.store.get_chapters(project_id)
        if not chapters:
            return ""
        events = []
        for ch in chapters[-6:]:
            report = self._load_json(ch.audit_report_json, {})
            score = report.get("overall_score", "?")
            cross = report.get("cross_chapter", [])
            bits = [f"第{ch.number}章 综合分 {score}"]
            if cross:
                bits.append(f"{len(cross)} 项跨章冲突")
            events.append("- " + "；".join(bits))
        if not events:
            return ""
        return "## 情景记忆（审计轨迹）\n" + "\n".join(events)

    def _build_derived(self, project_id, user_input, chapter) -> str:
        """Morpheus L3：派生记忆——未闭合线索账本"""
        threads = self.store.get_open_foreshadowings(project_id)
        if not threads:
            return ""
        lines = ["## 派生记忆", "### 未闭合线索（须回收）"]
        for t in threads[:10]:
            lines.append(f"- {t.description[:80]}")
        return "\n".join(lines)

    # ─── 工具 ───

    @staticmethod
    def _load_json(raw, default):
        try:
            return json.loads(raw) if raw else default
        except (json.JSONDecodeError, TypeError):
            return default

    def _retrieve_relevant(self, chapters, query: str):
        """Morpheus L2 关键词检索（生产可换向量）"""
        kws = {q for q in query if not q.isspace()} | set(query[:40].split())
        scored = []
        for ch in chapters:
            head = ch.text[:500]
            score = sum(1 for kw in kws if len(kw) >= 2 and kw in head)
            if score > 0:
                scored.append((ch, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [ch for ch, _ in scored] or chapters

    @staticmethod
    def _count_tokens(text: str) -> int:
        return len(text) // 2  # 中文约 1.5 字/token 的保守估计