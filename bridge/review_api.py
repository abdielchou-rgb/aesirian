"""四视图审查 API 路由（four-view-review-plan.md §4.1）

挂在 bridge/api_server.py 的 app 上：
- GET  /api/project/{id}/review                   四视图完整状态
- POST /api/project/{id}/sync                     同步请求
- POST /api/project/{id}/sync/{sync_id}/resolve   接受/拒绝变更
- POST /api/project/{id}/lock                     锁定/解锁视图
- POST /api/project/{id}/sync-mode                同步模式
- GET  /api/project/{id}/changes                  变更历史

会话态以内存 ReviewStore 保存（单机单进程够用）；快照落 SQLModel 模型由
上层调用方按需接入（见 models.ReviewSnapshot）。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.review.models import ResolveRequest, ReviewState, SyncRequest
from core.review.sync_engine import SyncEngine, build_initial_framework

router = APIRouter(prefix="/api", tags=["review"])

# 全局会话态（进程内）
_STATES: dict[str, ReviewState] = {}
_CHANGE_LOG: dict[str, list[dict]] = {}
_CONFLICTS: dict[str, list[dict]] = {}


def _get_state(project_id: str) -> ReviewState:
    if project_id not in _STATES:
        raise HTTPException(status_code=404, detail="项目不存在或无审查会话")
    return _STATES[project_id]


def _ensure_state(project_id: str) -> ReviewState:
    if project_id not in _STATES:
        st = ReviewState(project_id=project_id, framework=build_initial_framework())
        _STATES[project_id] = st
        _CHANGE_LOG[project_id] = []
        _CONFLICTS[project_id] = []
    return _STATES[project_id]


@router.get("/project/{project_id}/review")
async def get_review(project_id: str, chapter: int = 1):
    state = _ensure_state(project_id)
    return {
        "projectId": project_id,
        "currentChapter": chapter,
        "syncMode": state.sync_mode,
        "locks": state.locks,
        "draft": state.draft,
        "framework": state.framework,
        "chapters": state.chapters,
        "characters": state.characters,
        "sync_status": state.sync_status,
        "pending_changes": state.pending_changes,
    }


@router.post("/project/{project_id}/sync")
async def post_sync(project_id: str, req: SyncRequest):
    state = _ensure_state(project_id)
    if req.source not in ("draft", "framework", "chapters", "characters"):
        raise HTTPException(status_code=422, detail=f"未知视图: {req.source}")

    engine = SyncEngine()
    result = engine.sync(
        project_id=project_id,
        source=req.source,
        content=req.content,
        mode=req.mode,
        options=req.options,
        state=state,
    )

    if result["status"] == "conflict":
        _CONFLICTS[project_id] = result["conflicts"]
        state.pending_changes = result["changes"]
        for c in result["conflicts"]:
            state.set_sync_status(c["target_view"], "conflict")
        return {
            "sync_id": result["sync_id"],
            "status": "conflict",
            "conflicts": result["conflicts"],
            "changes": result["changes"],
            "summary": result["summary"],
        }

    # completed：变更已应用到 state（sync_engine._apply_changes）
    state.pending_changes = []
    _CHANGE_LOG[project_id] = list(state.change_history or [])
    return {
        "sync_id": result["sync_id"],
        "status": "completed",
        "changes": result["changes"],
        "conflicts": [],
        "summary": result["summary"],
    }


@router.post("/project/{project_id}/sync/{sync_id}/resolve")
async def resolve_sync(project_id: str, sync_id: str, req: ResolveRequest):
    state = _get_state(project_id)
    conflicts = _CONFLICTS.get(project_id, [])
    pending = state.pending_changes or {}
    if not conflicts:
        raise HTTPException(status_code=404, detail="无待解决冲突")

    for c in conflicts:
        # 仅处理用户指定的目标视图（空=全部）
        if req.view and c.get("target_view") != req.view:
            continue
        target = c.get("target_view")
        if req.action == "reject":
            state.set_sync_status(target, "synced")
            continue
        # accept / merge → 落地 pending 中该视图的变更
        change = pending.get(target)
        if change:
            self_apply(state, target, change)
        state.set_sync_status(target, "synced")

    _CONFLICTS[project_id] = []
    state.pending_changes = {}
    _CHANGE_LOG[project_id] = list(state.change_history or [])
    return {"resolved": True, "sync_id": sync_id}


def self_apply(state: ReviewState, view: str, change: dict) -> None:
    """把一条变更直接落地到 state（accept 用）。与 SyncEngine._apply_changes 同构。"""
    action = change.get("action")
    if action not in ("update", "rewrite"):
        return
    data = change.get("data", {})
    if view == "draft":
        state.draft = {**state.draft, **data}
    elif view == "framework":
        state.framework = {**state.framework, **data}
    elif view == "chapters" and isinstance(data, list):
        state.chapters = data
    elif view == "characters" and isinstance(data, list):
        state.characters = data
    state.record_change(
        {
            "id": f"chg_{len(state.change_history) + 1}",
            "timestamp": int(__import__("time").time() * 1000),
            "source_view": "resolve",
            "summary": change.get("reason", f"接受 {view} 变更"),
            "accepted": True,
        }
    )


@router.post("/project/{project_id}/lock")
async def set_lock(project_id: str, body: dict):
    view = body.get("view", "")
    locked = bool(body.get("locked"))
    if view not in ("draft", "framework", "chapters", "characters"):
        raise HTTPException(status_code=422, detail=f"未知视图: {view}")
    state = _ensure_state(project_id)
    locks = dict(state.locks)
    locks[view] = locked
    state.locks = locks
    return {"view": view, "locked": locked}


@router.post("/project/{project_id}/sync-mode")
async def set_sync_mode(project_id: str, body: dict):
    mode = body.get("mode", "realtime")
    if mode not in ("realtime", "manual", "locked"):
        raise HTTPException(status_code=422, detail=f"未知模式: {mode}")
    state = _ensure_state(project_id)
    state.sync_mode = mode
    return {"mode": mode}


@router.get("/project/{project_id}/changes")
async def get_changes(project_id: str, limit: int = 20, offset: int = 0):
    _ensure_state(project_id)
    log = _CHANGE_LOG.get(project_id, [])
    return {"changes": log[offset : offset + limit], "total": len(log)}
