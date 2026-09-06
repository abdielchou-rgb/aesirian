"""四视图审查 — 数据模型（four-view-review-plan.md §3）

包含：
- ReviewState：四视图审查会话的内存状态（draft / framework / chapters / characters）
- ReviewSnapshot / SyncConflict：SQLModel 持久化模型（供后续接入 SQLite 迁移）

说明：本模块保持零外部运行时依赖（仅 pydantic / sqlmodel），
业务推断逻辑全部在 sync_engine.py。
"""

from __future__ import annotations

import json
import time
from typing import Any

from pydantic import BaseModel, Field

try:  # sqlmodel 可选：api_server 进程可用；纯单元测试环境缺失时不阻塞
    from datetime import datetime

    from sqlmodel import Field as SQLField
    from sqlmodel import SQLModel

    _HAS_SQLMODEL = True
except Exception:  # pragma: no cover
    _HAS_SQLMODEL = False


# ─────────── 纯 Python 状态模型（不依赖 SQLModel）───────────


def now_ms() -> int:
    return int(time.time() * 1000)


class ReviewState(BaseModel):
    """四视图审查页的完整前端状态（与 review.html 的 state 对齐）。"""

    project_id: str = ""
    chapter_number: int = 1
    sync_mode: str = "realtime"  # realtime | manual | locked
    locks: dict[str, bool] = Field(
        default_factory=lambda: {
            "draft": False,
            "framework": False,
            "chapters": False,
            "characters": False,
        }
    )

    # 四视图数据
    draft: dict = Field(default_factory=lambda: {"content": "", "version": 1, "last_modified": 0})
    framework: dict = Field(
        default_factory=lambda: {
            "template": "three_act",
            "acts": [],
            "beats": [],
            "arcs": [],
            "version": 1,
            "last_modified": 0,
        }
    )
    chapters: list[dict] = Field(default_factory=list)
    characters: list[dict] = Field(default_factory=list)

    # 同步状态
    sync_status: dict[str, str] = Field(
        default_factory=lambda: {
            "draft": "synced",
            "framework": "synced",
            "chapters": "synced",
            "characters": "synced",
        }
    )

    # 变更历史
    change_history: list[dict] = Field(default_factory=list)
    pending_changes: list[dict] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return self.model_dump()

    def snapshot_view(self, view: str) -> Any:
        return getattr(self, view)

    def set_sync_status(self, view: str, status: str) -> None:
        s = dict(self.sync_status)
        s[view] = status
        self.sync_status = s

    def record_change(self, record: dict) -> None:
        self.change_history = [*self.change_history, record][-200:]


class SyncRequest(BaseModel):
    """POST /api/project/{id}/sync 的请求体（four-view-review-plan.md §4.1）"""

    source: str  # draft | framework | chapters | characters
    content: dict = Field(default_factory=dict)  # 新内容
    mode: str = "realtime"  # realtime | manual | force
    options: dict = Field(
        default_factory=lambda: {
            "target_views": [],  # 空=全部目标
            "force": False,  # 忽略锁定
        }
    )


class ResolveRequest(BaseModel):
    """POST /api/project/{id}/sync/{sync_id}/resolve 请求体"""

    view: str = ""
    action: str = "accept"  # accept | reject | merge


# ─────────── SQLModel 持久化模型（four-view-review-plan.md §3.2）───────────

if _HAS_SQLMODEL:

    class ReviewSnapshot(SQLModel, table=True):
        """审查页面快照——每次同步后保存"""

        __tablename__ = "review_snapshots"

        id: str = SQLField(primary_key=True)
        project_id: str = SQLField(index=True)
        chapter_number: int = SQLField(index=True)
        draft_json: str = "{}"
        framework_json: str = "{}"
        chapters_json: str = "[]"
        characters_json: str = "[]"
        sync_mode: str = "realtime"
        source_view: str = ""
        change_summary: str = ""
        created_at: datetime = SQLField(default_factory=lambda: datetime.now())

        @classmethod
        def from_state(cls, state: ReviewState, summary: str = "") -> ReviewSnapshot:
            return cls(
                id=f"rs_{state.project_id}_{int(time.time() * 1000)}",
                project_id=state.project_id,
                chapter_number=state.chapter_number,
                draft_json=json.dumps(state.draft, ensure_ascii=False),
                framework_json=json.dumps(state.framework, ensure_ascii=False),
                chapters_json=json.dumps(state.chapters, ensure_ascii=False),
                characters_json=json.dumps(state.characters, ensure_ascii=False),
                sync_mode=state.sync_mode,
                source_view="",
                change_summary=summary,
            )

    class SyncConflict(SQLModel, table=True):
        """同步冲突记录"""

        __tablename__ = "review_sync_conflicts"

        id: str = SQLField(primary_key=True)
        project_id: str = SQLField(index=True)
        source_view: str = ""
        target_view: str = ""
        conflict_type: str = ""  # contradiction | ambiguity | overlap | lock
        source_change: str = "{}"
        target_change: str = "{}"
        resolved: bool = False
        resolution: str = ""  # accept_source | accept_target | merge | manual
        created_at: datetime = SQLField(default_factory=lambda: datetime.now())
        resolved_at: datetime | None = SQLField(default=None)
