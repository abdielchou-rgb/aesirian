"""P2-8 (2026-09-07): chapters 复合唯一约束 + 幂等 upsert + 跨章增量摘要。

深度审计 S2.2.2/P2 建议：
1. chapters 表缺 (project_id, number) 唯一约束——重复提交/并发可产生同项目同章号
   的多条记录（幽灵章节）。
2. check_cross_chapter_consistency 每次提交对每个历史章全量 `_extract_entities`，
   全书累计 O(n²) 全文本正则提取。

修复：
- models.Chapter 增加 UniqueConstraint(project_id, number)
- store.add_chapter 改为 (project_id, number) 幂等 upsert（重复提交同章号覆盖）
- submit_chapter 落盘 `audit_report_json["_entity_summary"]`；跨章检查读历史章
  摘要（_history_entity_view），无摘要的老数据才回退全量提取

Run: python -X utf8 -m pytest tests/test_p2_8_uniqueness.py -v
"""
import json

from fastapi.testclient import TestClient

from bridge.api_server import app
from core.orchestrator import Orchestrator
from core.persistence.store import ProjectStore

client = TestClient(app)


def _mkproject() -> str:
    r = client.post(
        "/import-from-pwa",
        json={
            "premise": "P2-8测试项目",
            "unit_text": "夜色中的洛阳星港。",
            "characters": [{"name": "陈默", "role": "主角"}],
            "tone": "悬疑暗流",
            "conflict": "生存冲突",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["project_id"]


def _store():
    return ProjectStore()


def test_add_chapter_same_number_is_idempotent():
    """同 (project_id, number) 重复 add_chapter → 覆盖不新增（无幽灵章节）。"""
    pid = _mkproject()
    st = _store()
    st.add_chapter(pid, 1, "第一章：陈默走进工坊。", {"overall_score": 100})
    st.add_chapter(pid, 1, "第一章：陈默走进工坊（修订）。", {"overall_score": 90})

    chapters = st.get_chapters(pid)
    assert len(chapters) == 1, f"应只有 1 条章节记录，实际 {len(chapters)}"
    assert chapters[0].text == "第一章：陈默走进工坊（修订）。"
    assert chapters[0].audit_report_json


def test_unique_constraint_blocks_duplicate_insert():
    """唯一约束存在：绕过 add_chapter 直接插入同 (project, number) 应失败。"""
    from sqlalchemy.exc import IntegrityError

    from core.persistence.models import Chapter

    pid = _mkproject()
    st = _store()
    st.add_chapter(pid, 2, "第二章：雨声渐大。")

    from sqlmodel import Session

    with Session(st.engine) as session:
        dup = Chapter(
            id="dup_dup_dup_001",
            project_id=pid,
            number=2,
            title="重复章",
            text="应该冲突",
        )
        session.add(dup)
        try:
            session.commit()
            raise AssertionError("唯一约束未生效——同 (project_id, number) 竟插入成功")
        except IntegrityError:
            session.rollback()  # 预期：复合唯一约束拦截


def test_submit_persists_entity_summary():
    """submit_chapter 落盘 audit_report_json 含 _entity_summary。"""
    pid = _mkproject()
    r = client.post(
        "/project/" + pid + "/submit-chapter",
        json={"project_id": pid, "text": "第一章：陈默走进档案室，林晚跟在他身后。"},
    )
    assert r.status_code == 200
    st = _store()
    chapters = st.get_chapters(pid)
    assert len(chapters) == 1
    payload = json.loads(chapters[0].audit_report_json)
    assert "_entity_summary" in payload, "提交应落盘实体摘要"
    summary = payload["_entity_summary"]
    assert "characters" in summary and "facts" in summary
    assert "identity_changes" in summary


def test_cross_chapter_reads_persisted_summary_not_full_reextract():
    """跨章检查读历史章落盘摘要（view 命中），不再全量重提取。

    间接断言：check 输出与 P0-3 一致（CSN 年龄矛盾仍被检出），说明摘要路径
    保留了行为；同时 _history_entity_view 对已有摘要章返回 summary。
    """
    pid = _mkproject()
    client.post(
        "/project/" + pid + "/submit-chapter",
        json={"project_id": pid, "text": "第一章：陈默修了十一年罪忆水晶。"},
    )

    orch = Orchestrator(store=_store())
    chapter = _store().get_chapters(pid)[0]
    view = orch._history_entity_view(chapter)
    assert view.get("characters") is not None  # 摘要视图结构完整

    # 新章含年龄矛盾 → 跨章应检出（读历史章摘要路径）
    conflicts = orch.check_cross_chapter_consistency(
        pid, "第二章：陈默修了二十一年罪忆水晶。"
    )
    assert any(c["type"] == "csn_numeric_contradiction" for c in conflicts), conflicts
