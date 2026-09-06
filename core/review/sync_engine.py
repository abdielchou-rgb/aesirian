"""四视图同步引擎（four-view-review-plan.md §4.2）

SyncEngine：对 ReviewState（draft/framework/chapters/characters 四视图）执行
双向 AI 同步：
- draft → framework/chapters/characters（从正文推断结构/章节/人物增量）
- framework → draft（按结构变化给出试样故事重构/微调提案）
- chapters → draft（按章节变化给出扩写/压缩提案）
- characters → draft（按人物变化给出对话/行为改写提案）

设计原则：
1. 规则路径是主体——不依赖任何外部 LLM 即可产出确定性、可验收的推断结果；
2. LLM 接口（`_llm_oracle`）作为可插拔增强，缺失时静默走规则；
3. 所有推断以"提案（changes + conflicts）"形式浮出，由上层接受/拒绝后落地，
   引擎自身不直接改写持久层。
"""

from __future__ import annotations

import difflib
import re
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.review.models import ReviewState

# 兼容工程内 pydantic 版本
try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    BaseModel = object  # type: ignore

VIEWS = ("draft", "framework", "chapters", "characters")
TARGETS = {
    "draft": ("framework", "chapters", "characters"),
    "framework": ("draft",),
    "chapters": ("draft",),
    "characters": ("draft",),
}

_SENT_SPLIT = re.compile(r"(?<=[。！？!?…\n])")
_SPEAKER = re.compile(r"([\u4e00-\u9fa5A-Za-z]{1,6})[说喊道问答嚷叫]")
_ACTOR = re.compile(
    r"([\u4e00-\u9fa5A-Za-z]{2,4})(?=(?:把|将|被|向|对|与|和|从|在|望|看|听|拿|放下|推开))"
)
_TURN_DOWN = (
    "却",
    "但是",
    "但",
    "突然",
    "然而",
    "反而",
    "拒绝",
    "失败",
    "失去",
    "受伤",
    "逃离",
    "放弃",
    "背叛",
    "死",
    "坠",
)
_TURN_UP = (
    "终于",
    "成功",
    "获",
    "救",
    "觉醒",
    "面对",
    "放下",
    "突破",
    "胜利",
    "归来",
    "重生",
    "原谅",
    "真相",
    "钥匙",
)


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if s and s.strip()]


def _charge_of(sentence: str) -> str:
    """给一个句子打价值转向标签（规则近似）。"""
    if any(k in sentence for k in _TURN_UP):
        return "negative_to_positive"
    if any(k in sentence for k in _TURN_DOWN):
        return "positive_to_negative"
    return "none"


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _name_from_sentence(sentence: str) -> str | None:
    m = _SPEAKER.search(sentence)
    if m and m.group(1) not in ("他说", "她说", "他们说", "这个", "那个"):
        return m.group(1)
    m = _ACTOR.search(sentence)
    return m.group(1) if m else None


def _sentences_text(text: str) -> str:
    """多行文本转单行便于比对。"""
    return re.sub(r"\s+", "", text or "")


class SyncEngine:
    """四视图双向同步引擎。"""

    def __init__(
        self,
        llm: Any | None = None,
        tom: Any | None = None,
        kg: Any | None = None,
        style: Any | None = None,
        oracle: Callable[[str], str | None] | None = None,
    ):
        self.llm = llm
        self.tom = tom
        self.kg = kg
        self.style = style
        self._oracle = oracle  # 可选：外部 LLM 单发接口，输入 prompt 返回文本或 None

    # ─────────── 主流程 ───────────

    def sync(
        self,
        project_id: str,
        source: str,
        content: dict,
        mode: str = "realtime",
        options: dict | None = None,
        state: ReviewState | None = None,
    ) -> dict:
        """执行同步，返回 {status, changes, conflicts, summary, sync_id}。

        state: 四视图当前状态（ReviewState）。引擎内部使用 dict 形态，
        顶层（api_server）负责与持久层互换。
        """
        from core.review.models import ReviewState  # 延迟导入避免模块级循环

        options = options or {}
        force = bool(options.get("force")) or mode == "force"
        target_views = list(options.get("target_views") or TARGETS.get(source, []))

        if source not in VIEWS:
            raise ValueError(f"Unknown source: {source}")
        current = state if state is not None else ReviewState(project_id=project_id)

        # 1. 分源推断
        changes = self._dispatch(source, current, content, target_views)

        # 2. 冲突检测（目标锁定视图 / 目标视图重复更新）
        conflicts = self._detect_conflicts(current, changes, source, force=force)

        # 3. 冲突且未强制 → 挂起等待用户裁决
        sync_id = _short_id("sync")
        if conflicts and not force:
            for c in conflicts:
                c["sync_id"] = sync_id
            return {
                "sync_id": sync_id,
                "status": "conflict",
                "changes": changes,
                "conflicts": conflicts,
                "summary": self._generate_summary(changes),
            }

        # 4. 无冲突（或强制）→ 应用变更到内存态
        applied = self._apply_changes(current, changes, source)
        summary = self._generate_summary(applied)
        return {
            "sync_id": sync_id,
            "status": "completed",
            "changes": applied,
            "conflicts": [],
            "summary": summary,
        }

    # ─────────── 路由 ───────────

    def _dispatch(self, source: str, current: Any, content: dict, target_views: list[str]) -> dict:
        if source == "draft":
            return self._sync_from_draft(current, content, target_views)
        if source == "framework":
            return self._sync_from_framework(current, content)
        if source == "chapters":
            return self._sync_from_chapters(current, content)
        if source == "characters":
            return self._sync_from_characters(current, content)
        return {}

    # ─────────── draft → 其它三视图 ───────────

    def _sync_from_draft(self, current: Any, new_draft: dict, target_views: list[str]) -> dict:
        old_text = _sentences_text(current.draft.get("content", ""))
        new_text = _sentences_text(new_draft.get("content", ""))
        if new_text == old_text:
            return {}
        changes: dict[str, dict] = {}

        # 新增/移除的句子
        added, removed = self._diff_text(old_text, new_text)

        if "framework" in target_views:
            fw_changes = self._infer_framework_changes(current, added, removed)
            if fw_changes:
                changes["framework"] = fw_changes
        if "chapters" in target_views:
            ch_changes = self._infer_chapter_changes(current, added, removed)
            if ch_changes:
                changes["chapters"] = ch_changes
        if "characters" in target_views:
            ch_c = self._infer_character_changes(current, added, removed)
            if ch_c:
                changes["characters"] = ch_c
        return changes

    def _diff_text(self, old: str, new: str) -> tuple[list[str], list[str]]:
        """按句子比对，返回 (added, removed)。"""
        added: list[str] = []
        removed: list[str] = []
        # 字符级 LCS 近似：
        matcher = difflib.SequenceMatcher(None, old, new)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                added.append(new[j1:j2])
            elif tag == "delete":
                removed.append(old[i1:i2])
            elif tag == "replace":
                removed.append(old[i1:i2])
                added.append(new[j1:j2])
        # 仅保留有实质内容的块
        added = [a for a in added if _sentences_text(a)]
        removed = [r for r in removed if _sentences_text(r)]
        return added, removed

    def _infer_framework_changes(
        self, current: Any, added: list[str], removed: list[str]
    ) -> dict | None:
        """新增文本 → 框架 beats 增量（规则推断）。"""
        if not added:
            return None
        old_beats = current.framework.get("beats", [])
        new_beats = [dict(b) for b in old_beats]
        diffs = {"added": [], "modified": [], "deleted": []}

        act_map = {1: "act_1", 2: "act_2", 3: "act_3"}
        for chunk in added:
            for sent in _split_sentences(chunk):
                if len(_sentences_text(sent)) < 6:
                    continue
                charge = _charge_of(sent)
                # 找位置：按是否张力转折分配幕
                if charge == "negative_to_positive":
                    act = 3
                elif charge == "positive_to_negative":
                    act = 2
                else:
                    act = 1
                name = _sentences_text(sent)[:14] + ("…" if len(_sentences_text(sent)) > 14 else "")
                beat = {
                    "id": _short_id("beat"),
                    "actId": act_map.get(act, "act_1"),
                    "name": name,
                    "chapter": current.chapter_number,
                    "description": _sentences_text(sent)[:60],
                    "storyValue": "positive"
                    if charge == "negative_to_positive"
                    else ("negative" if charge == "positive_to_negative" else "neutral"),
                    "charge": charge,
                }
                new_beats.append(beat)
                diffs["added"].append(beat)
        if not diffs["added"] and not diffs["deleted"]:
            return None
        acts = current.framework.get("acts") or self._default_acts()
        return {
            "action": "update",
            "data": {
                **current.framework,
                "beats": new_beats,
                "acts": acts,
                "version": current.framework.get("version", 1) + 1,
            },
            "diff": diffs,
            "reason": "检测到正文新增情节，推导出新的框架节拍",
        }

    def _default_acts(self) -> list[dict]:
        return [
            {
                "id": "act_1",
                "name": "第一幕：建立",
                "startChapter": 1,
                "endChapter": 3,
                "description": "介绍主角、世界观与初始冲突",
            },
            {
                "id": "act_2",
                "name": "第二幕：对抗",
                "startChapter": 4,
                "endChapter": 7,
                "description": "张力升级，主角反复尝试后陷入困境",
            },
            {
                "id": "act_3",
                "name": "第三幕：解决",
                "startChapter": 8,
                "endChapter": 10,
                "description": "真相揭晓，主角完成转变",
            },
        ]

    def _infer_chapter_changes(
        self, current: Any, added: list[str], removed: list[str]
    ) -> dict | None:
        if not added and not removed:
            return None
        old_list = [dict(c) for c in current.chapters]
        if not old_list:
            old_list = [
                {
                    "number": 1,
                    "title": "第1章",
                    "summary": "",
                    "status": "writing",
                    "wordCount": 0,
                    "wordTarget": 2000,
                    "sceneIds": [],
                }
            ]
        ch = old_list[0]
        full_new = current.draft.get("content", "") + "".join(added)
        ch["wordCount"] = len(_sentences_text(full_new))
        ch["status"] = "revised" if len(_sentences_text(full_new)) >= 500 else "writing"
        ch["summary"] = _sentences_text(full_new)[:80]
        return {
            "action": "update",
            "data": old_list,
            "diff": {
                "added": [],
                "modified": [{"number": ch["number"], "wordCount": ch["wordCount"]}],
                "deleted": [],
            },
            "reason": "正文有增改，更新章节字数与状态",
        }

    def _infer_character_changes(
        self, current: Any, added: list[str], removed: list[str]
    ) -> dict | None:
        if not added:
            return None
        known = {c.get("name") for c in current.characters}
        new_chars: list[dict] = []
        diffs_added = []
        for chunk in added:
            for sent in _split_sentences(chunk):
                name = _name_from_sentence(sent)
                if name and name not in known and name not in {c["name"] for c in new_chars}:
                    new_chars.append(
                        {
                            "id": _short_id("char"),
                            "name": name,
                            "role": "unknown",
                            "beliefs": [],
                            "goals": [],
                            "secrets": [],
                            "arc": {
                                "startChapter": current.chapter_number,
                                "endChapter": 0,
                                "transformation": "",
                            },
                            "firstAppearance": current.chapter_number,
                        }
                    )
                    known.add(name)
                    diffs_added.append({"name": name, "firstAppearance": current.chapter_number})
        if not new_chars:
            return None
        return {
            "action": "update",
            "data": [dict(c) for c in current.characters] + new_chars,
            "diff": {"added": diffs_added, "modified": [], "deleted": []},
            "reason": f"正文中识别到新出现人物：{', '.join(d['name'] for d in diffs_added)}",
        }

    # ─────────── framework → draft ───────────

    def _sync_from_framework(self, current: Any, new_framework: dict) -> dict:
        old = current.framework or {}
        diff = self._diff_framework(old, new_framework)
        changes: dict[str, dict] = {}
        if not diff["structure_changed"]:
            return changes
        # 结构重大变化 → 试样故事重构提案
        new_draft = self._restructure_draft(current.draft.get("content", ""), old, new_framework)
        changes["draft"] = {
            "action": "rewrite",
            "data": {
                "content": new_draft,
                "version": current.draft.get("version", 1) + 1,
                "last_modified": int(__import__("time").time() * 1000),
            },
            "diff": {"added": [], "modified": [], "deleted": []},
            "reason": f"框架结构变化：{diff['summary']}",
        }
        return changes

    def _diff_framework(self, old: dict, new: dict) -> dict:
        old_names = {b.get("name") for b in old.get("beats", [])}
        new_names = {b.get("name") for b in new.get("beats", []) if b.get("name")}
        added = list(new_names - old_names)
        removed = list(old_names - new_names)
        structure_changed = bool(added or removed)
        return {
            "structure_changed": structure_changed,
            "added": added,
            "removed": removed,
            "summary": f"新增节拍 {len(added)} 个，移除 {len(removed)} 个",
        }

    def _restructure_draft(self, draft: str, old_fw: dict, new_fw: dict) -> str:
        """规则重构：保留原文骨架，在开头附上按新框架划分的结构提示。

        说明：真实的小说级重构需要 LLM；规则路径产出结构标注版草稿，
        保证可读、可审、不会凭空生成与事实冲突的剧情。
        """
        beats = new_fw.get("beats", [])
        acts = new_fw.get("acts", []) or self._default_acts()
        acts_lookup = {a.get("id"): a.get("name", "") for a in acts}
        lines = [f"（结构重写草案 · {new_fw.get('template', 'three_act')}）"]
        for i, b in enumerate(beats, 1):
            act_name = acts_lookup.get(b.get("actId"), "")
            lines.append(f"[{act_name or '节拍'} {i}] {b.get('name', '')} —— {b.get('charge', '')}")
        lines.append("")
        lines.append(draft)
        return "\n".join(lines)

    # ─────────── chapters → draft ───────────

    def _sync_from_chapters(self, current: Any, new_chapters: list) -> dict:
        old = current.chapters or []
        added = [c for c in new_chapters if c.get("number") not in {o.get("number") for o in old}]
        modified = [
            c
            for c in new_chapters
            if c.get("number") in {o.get("number") for o in old}
            and c != old[next(i for i, o in enumerate(old) if o.get("number") == c.get("number"))]
        ]
        changes: dict[str, dict] = {}
        if added:
            ch = added[0]
            changes.setdefault("draft", {"action": "adjust", "adjustments": [], "reason": ""})
            changes["draft"]["adjustments"].append(
                {
                    "type": "expand",
                    "chapter": ch.get("number"),
                    "suggestion": f"为新增章节「{ch.get('title', '')}」扩写正文",
                }
            )
            changes["draft"]["reason"] = f"新增章节：{ch.get('title', '')}"
        if modified:
            ch = modified[0]
            changes.setdefault("draft", {"action": "adjust", "adjustments": [], "reason": ""})
            changes["draft"]["adjustments"].append(
                {
                    "type": "revision",
                    "chapter": ch.get("number"),
                    "suggestion": f"章节「{ch.get('title', '')}」状态变为 {ch.get('status')}，建议按大纲调整正文",
                }
            )
            changes["draft"]["reason"] = f"章节状态变化：{ch.get('title', '')}"
        return changes

    # ─────────── characters → draft ───────────

    def _sync_from_characters(self, current: Any, new_characters: list) -> dict:
        old = current.characters or []
        old_by_name = {c.get("name"): c for c in old}
        new_by_name = {c.get("name"): c for c in new_characters}
        belief_changes = []
        new_names = []
        for name, nc in new_by_name.items():
            oc = old_by_name.get(name)
            if not oc:
                new_names.append(name)
                continue
            # 信念数量变化视为信念更新
            if len(nc.get("beliefs") or []) != len(oc.get("beliefs") or []) or (
                nc.get("goals") or []
            ) != (oc.get("goals") or []):
                belief_changes.append({"name": name})
        changes: dict[str, dict] = {}
        if belief_changes or new_names:
            adjustments = []
            if belief_changes:
                adjustments.append(
                    {
                        "type": "rewrite_dialogue",
                        "names": [b["name"] for b in belief_changes],
                        "suggestion": f"角色信念/目标变化：{', '.join(b['name'] for b in belief_changes)}，建议改写相关对话与行动",
                    }
                )
            if new_names:
                adjustments.append(
                    {
                        "type": "insert_appearance",
                        "names": new_names,
                        "suggestion": f"新增角色：{', '.join(new_names)}，建议在正文中安排登场",
                    }
                )
            changes["draft"] = {
                "action": "adjust",
                "adjustments": adjustments,
                "reason": "人物卡片变化，建议联动改写正文",
            }
        return changes

    # ─────────── 冲突检测与落地 ───────────

    def _detect_conflicts(
        self, current: Any, changes: dict, source: str, force: bool = False
    ) -> list[dict]:
        conflicts: list[dict] = []
        if not changes:
            return conflicts
        locks = current.locks or {}
        # 锁定目标视图不允许被改写
        conflicts.extend(
            {
                "id": _short_id("conf"),
                "source_view": source,
                "target_view": view,
                "conflict_type": "lock",
                "message": f"「{view}」视图已锁定，本次改动被拦截",
            }
            for view in changes
            if view != source and locks.get(view)
        )
        # 两个不同源同时改写同一目标（当前单源场景不会出现，但保留守卫）
        if not conflicts and len(changes) > 1 and "draft" in changes:
            conflicts.append(
                {
                    "id": _short_id("conf"),
                    "source_view": source,
                    "target_view": "draft",
                    "conflict_type": "overlap",
                    "message": "多个目标同时改写试样故事，需要确认",
                }
            )
        return conflicts

    def _apply_changes(self, current: Any, changes: dict, source: str) -> dict:
        applied: dict[str, dict] = {}
        for view, change in changes.items():
            action = change.get("action")
            if action in ("update", "rewrite"):
                data = change.get("data", {})
                if view == "draft":
                    current.draft = {**current.draft, **data}
                elif view == "framework":
                    current.framework = {**current.framework, **data}
                elif view == "chapters":
                    current.chapters = data if isinstance(data, list) else current.chapters
                elif view == "characters":
                    current.characters = data if isinstance(data, list) else current.characters
                current.set_sync_status(view, "synced")
                applied[view] = change
            elif action == "adjust":
                # adjust 提案不做结构性落地，只记录为待处理建议
                current.set_sync_status(view, "synced")
                applied[view] = change
        if applied:
            current.record_change(
                {
                    "id": _short_id("chg"),
                    "timestamp": int(__import__("time").time() * 1000),
                    "source_view": source,
                    "summary": self._generate_summary(applied),
                    "accepted": True,
                }
            )
        return applied

    def _generate_summary(self, changes: dict) -> str:
        if not changes:
            return "无实质变化"
        parts = []
        for view, change in changes.items():
            act = change.get("action")
            reason = change.get("reason")
            parts.append(f"{view}({act})")
            if reason:
                parts[-1] = f"{view}({act}：{reason})"
        return "；".join(parts)


def build_initial_framework(template: str = "three_act") -> dict:
    """构建空项目的默认框架（acts + 空 beats）。"""
    engine = SyncEngine()
    acts = engine._default_acts()
    return {
        "template": template,
        "acts": acts,
        "beats": [],
        "arcs": [],
        "version": 1,
        "last_modified": int(__import__("time").time() * 1000),
    }
