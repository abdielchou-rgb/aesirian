"""P0-2 (2026-09-07): /audit 默认 analysis-only（dry_run）——不落库、不推进章节。

背景（深度审计 S1.2）：`/audit` 端点此前在无 BLOCK 时静默调用 `orch.submit_chapter(...)`，
会落库、推进章节号、触发 ToM/KG 更新——用户"试算建议文本"时可能不知不觉写入章节，
无法区分"试算"与"提交"。

修复后铁律：
1. POST /project/{id}/audit 默认 dry_run：只审计不落库，current_chapter 不变，
   DB chapters 数不变，project.gates 审计历史/章节计数不被污染。
2. 显式 commit=true 保留旧提交语义（标 deprecated；建议改用 /submit-chapter）。
3. 前端"提交"走 /submit-chapter（本就如此）；/audit 定位为只读试算。

Run: python -X utf8 -m pytest tests/test_audit_dry_run.py -v
"""
from fastapi.testclient import TestClient

from bridge.api_server import app

client = TestClient(app)


def _mkproject() -> str:
    r = client.post(
        "/import-from-pwa",
        json={
            "premise": "P0-2审计测试项目",
            "unit_text": "夜色中的洛阳星港，一位匠人正在修复罪忆水晶。",
            "characters": [{"name": "陈默", "role": "主角"}, {"name": "曹渊", "role": "来客"}],
            "tone": "悬疑暗流",
            "conflict": "生存冲突",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["project_id"]


def _chapter_count(pid: str) -> int:
    """经 store 读 DB 中的章节数（不经过运行时缓存）。"""
    from core.orchestrator import Orchestrator
    from core.persistence.store import ProjectStore

    return len(Orchestrator(store=ProjectStore()).store.get_chapters(pid))


def test_audit_default_is_dry_run_no_persist():
    """默认 /audit：dry_run=true, submitted=false；不落库、不推进章节。"""
    pid = _mkproject()
    before = _chapter_count(pid)

    r = client.post(
        "/project/" + pid + "/audit",
        json={"project_id": pid, "text": "第一章：陈默推开工坊的门，看见曹渊站在阴影里。"},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["dry_run"] is True
    assert d["submitted"] is False
    assert "overall_score" in d
    assert "gate_results" in d
    assert "quality" in d and isinstance(d["quality"], list)

    # 不落库、不推进章节
    assert _chapter_count(pid) == before


def test_audit_dry_run_does_not_advance_chapter_number():
    """dry_run 后 orchestrator 的 current_chapter 不变（无隐式 +1）。"""
    pid = _mkproject()
    r = client.post(
        "/project/" + pid + "/audit",
        json={"project_id": pid, "text": "第一章：星港的夜风裹着冷却液的气味。"},
    )
    assert r.status_code == 200

    from core.orchestrator import Orchestrator
    from core.persistence.store import ProjectStore

    orch = Orchestrator(store=ProjectStore())
    proj = orch.get_project(pid)
    assert proj is not None
    assert proj.current_chapter == 0  # 未提交任何章


def test_audit_commit_true_persists_with_deprecation():
    """commit=true 保留旧提交语义：submitted=true、落库，并给出 deprecated 提示。"""
    pid = _mkproject()
    r = client.post(
        "/project/" + pid + "/audit",
        json={
            "project_id": pid,
            "text": "第一章：陈默指尖滑过水晶，七层加密泛着冷光。",
            "commit": True,
        },
    )
    assert r.status_code == 200
    d = r.json()
    # 该文本应无 G1-G5 BLOCK（普通叙述），故提交成功
    assert d["submitted"] is True
    assert d["dry_run"] is False
    assert "deprecated" in d and "submit-chapter" in d["deprecated"]
    assert _chapter_count(pid) == 1


def test_submit_chapter_remains_primary_commit_path():
    """/submit-chapter 仍是主提交路径，返回 submitted/cross_chapter。"""
    pid = _mkproject()
    r = client.post(
        "/project/" + pid + "/submit-chapter",
        json={"project_id": pid, "text": "第一章：他推开门，灯下坐着一个人。"},
    )
    assert r.status_code == 200
    assert r.json()["submitted"] is True
    assert "cross_chapter" in r.json()
    assert _chapter_count(pid) == 1


def test_dry_run_gates_not_polluted():
    """多次 dry_run 不污染 project.gates 审计历史（临时实例隔离）。"""
    pid = _mkproject()
    for i in range(3):
        r = client.post(
            "/project/" + pid + "/audit",
            json={"project_id": pid, "text": f"试算文本{i}：夜色中的脚步声由远及近。"},
        )
        assert r.status_code == 200

    from core.orchestrator import Orchestrator
    from core.persistence.store import ProjectStore

    orch = Orchestrator(store=ProjectStore())
    proj = orch.get_project(pid)
    # 临时实例隔离：真实 gates 的审计历史应为空（尚未提交任何章）
    assert len(proj.gates.get_audit_history()) == 0
