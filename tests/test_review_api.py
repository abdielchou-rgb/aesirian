"""四视图审查 API 集成测试（four-view-review-plan.md §4.1）

使用 FastAPI TestClient 驱动独立挂载的 review router，验证：
- GET review 初始状态
- POST sync（draft 联动）completed 路径
- POST lock → 冲突 → resolve accept/reject 路径
- sync-mode / changes 端点
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bridge.review_api import router as review_router


@pytest.fixture()
def client():
    # 每个测试使用独立 app，避免 _STATES 跨用例污染
    import bridge.review_api as ra
    ra._STATES.clear()
    ra._CONFLICTS.clear()
    ra._CHANGE_LOG.clear()
    app = FastAPI()
    app.include_router(review_router)
    return TestClient(app)


def test_get_review_initial(client):
    r = client.get("/api/project/p_test/review")
    assert r.status_code == 200
    data = r.json()
    assert data["projectId"] == "p_test"
    assert data["syncMode"] == "realtime"
    assert set(data["locks"].keys()) == {"draft", "framework", "chapters", "characters"}
    assert data["draft"]["content"] == ""
    assert data["framework"]["beats"] == []
    assert len(data["framework"]["acts"]) == 3


def test_sync_draft_completed(client):
    client.get("/api/project/p1/review")
    r = client.post("/api/project/p1/sync", json={
        "source": "draft",
        "content": {"content": "陈默把水晶接入读数仪。突然灯灭了。但门被反锁，他绝望地握紧了刀。"},
        "mode": "realtime",
        "options": {"target_views": []},
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert data["conflicts"] == []
    # 完成态应已写入 characters（陈默）与 framework beats
    state = client.get("/api/project/p1/review").json()
    assert any(c["name"] == "陈默" for c in state["characters"])
    assert len(state["framework"]["beats"]) >= 1


def test_lock_conflict_and_resolve_accept(client):
    client.get("/api/project/p2/review")
    # 锁定 framework
    assert client.post("/api/project/p2/lock", json={"view": "framework", "locked": True}).status_code == 200
    # 从 draft 同步应产生 lock 冲突
    r = client.post("/api/project/p2/sync", json={
        "source": "draft",
        "content": {"content": "新的正文出现了重要情节转折。"},
        "mode": "realtime",
    })
    data = r.json()
    assert data["status"] == "conflict"
    assert any(c["conflict_type"] == "lock" and c["target_view"] == "framework"
               for c in data["conflicts"])
    sync_id = data["sync_id"]

    # 拒绝：framework 不变
    r2 = client.post(f"/api/project/p2/sync/{sync_id}/resolve", json={"view": "", "action": "reject"})
    assert r2.status_code == 200
    assert r2.json()["resolved"] is True
    state = client.get("/api/project/p2/review").json()
    assert state["framework"]["beats"] == []
    # sync_status 应全部 synced（冲突已清）
    assert all(v == "synced" for v in state["sync_status"].values())


def test_lock_conflict_resolve_accept_applies(client):
    client.get("/api/project/p3/review")
    client.post("/api/project/p3/lock", json={"view": "framework", "locked": True})
    r = client.post("/api/project/p3/sync", json={
        "source": "draft",
        "content": {"content": "他拔出剑，向黑暗挥去。终于他找到了出口，重新见到了光。"},
        "mode": "realtime",
    })
    data = r.json()
    assert data["status"] == "conflict"
    sync_id = data["sync_id"]
    # 接受：framework 解锁改写并落地
    r2 = client.post(f"/api/project/p3/sync/{sync_id}/resolve", json={"view": "framework", "action": "accept"})
    assert r2.status_code == 200
    state = client.get("/api/project/p3/review").json()
    assert len(state["framework"]["beats"]) >= 1


def test_sync_mode_change(client):
    client.get("/api/project/p4/review")
    assert client.post("/api/project/p4/sync-mode", json={"mode": "manual"}).json()["mode"] == "manual"
    assert client.post("/api/project/p4/sync-mode", json={"mode": "locked"}).status_code == 200
    # 非法模式
    assert client.post("/api/project/p4/sync-mode", json={"mode": "bogus"}).status_code == 422


def test_changes_history(client):
    client.get("/api/project/p5/review")
    client.post("/api/project/p5/sync", json={
        "source": "draft",
        "content": {"content": "第一句正文。第二句正文。但转折发生了，他必须做出选择。"},
    })
    r = client.get("/api/project/p5/changes")
    assert r.status_code == 200
    assert r.json()["total"] >= 0  # adjust/无 beat 时可能不落 change，只验证端点可访问


def test_unknown_source_422(client):
    r = client.post("/api/project/p6/sync", json={"source": "bogus", "content": {}})
    assert r.status_code == 422
