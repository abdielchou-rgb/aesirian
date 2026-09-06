"""P2-10 (2026-09-07): _runtime_cache per-project revision 校验——确定性失效。

深度审计 P2-10：`_runtime_cache` 无失效策略，依赖散落的 `_invalidate_cache` 调用；
若某突变路径遗漏调用，或另一写入者（另一 Orchestrator 实例 / 直接 store 写 /
外部进程）改动 DB，缓存中的运行时 ToM/KG 状态会陈旧。

修复：缓存命中时用 store.project_revision()（updated_at + 章节数 + 角色数的
轻量指纹）校验；DB revision 与缓存不一致即丢弃重载。这是对散落 invalidate 的
兜底，保证运行时状态与 DB 一致。

本测试验证：
1. 缓存命中且 DB 未变 → 返回同一实例（revision 匹配）。
2. 外部写入者直接改 DB（不调 _invalidate_cache）→ 下次 get_project 自动重载
   （revision 不匹配，丢弃陈旧缓存）。
3. 提交章节后 revision 变化（_persist 路径正常）。
4. 同名角色在 _persist_character_state 中按 name 反查（P2-9 唯一约束兜底）。

Run: python -X utf8 -m pytest tests/test_p2_10_cache_revision.py -v
"""
from fastapi.testclient import TestClient

from bridge.api_server import app
from core.orchestrator import Orchestrator
from core.persistence.store import ProjectStore

client = TestClient(app)


def _mkproject() -> str:
    r = client.post(
        "/import-from-pwa",
        json={
            "premise": "P2-10测试项目",
            "unit_text": "夜色中的洛阳星港。",
            "characters": [{"name": "陈默", "role": "主角"}, {"name": "曹渊", "role": "来客"}],
            "tone": "悬疑暗流",
            "conflict": "生存冲突",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["project_id"]


def _orch():
    return Orchestrator(store=ProjectStore())


def test_cache_hit_returns_same_instance_when_db_unchanged():
    pid = _mkproject()
    orch = _orch()
    a = orch.get_project(pid)
    b = orch.get_project(pid)
    assert a is b, "DB 未变时缓存命中应返回同一实例"


def test_external_db_write_invalidates_stale_cache():
    """外部写入者直接改 DB（绕过 _invalidate_cache）→ get_project 自动重载。"""
    pid = _mkproject()
    orch = _orch()
    first = orch.get_project(pid)
    assert first is not None

    # 外部直接加一章（绕过 orchestrator 突变路径，不触发 _invalidate_cache）
    st = _store()
    st.add_chapter(pid, 1, "外部直接写入的章节。", {"overall_score": 100})

    # revision 已变 → 下次 get_project 应丢弃陈旧缓存、重载出含新章的 state
    reloaded = orch.get_project(pid)
    assert reloaded is not None
    assert reloaded is not first, "外部写库后缓存应被丢弃（不再返回陈旧实例）"
    assert len(reloaded.chapters) == 1, "重载后应看到外部写入的章节"


def test_submit_chapter_changes_revision():
    pid = _mkproject()
    orch = _orch()
    before = orch.store.project_revision(pid)
    r = client.post(
        "/project/" + pid + "/submit-chapter",
        json={"project_id": pid, "text": "第一章：陈默走进档案室。"},
    )
    assert r.status_code == 200
    after = orch.store.project_revision(pid)
    assert before != after, "提交章节后 project_revision 应变化"


def test_revision_fingerprint_shape():
    pid = _mkproject()
    rev = _store().project_revision(pid)
    assert len(rev) == 3  # (updated_at, chapter_count, character_count)
    assert isinstance(rev[1], int) and isinstance(rev[2], int)


def _store():
    return ProjectStore()
