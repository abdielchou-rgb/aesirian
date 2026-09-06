"""四视图同步引擎单测（four-view-review-plan.md §4.2 规则路径）

重点验证：离线（无 LLM）环境下 SyncEngine 的确定性推断：
- draft → framework/chapters/characters 的联动增量
- framework/chapters/characters → draft 的重构/调整提案
- 锁定视图的冲突拦截与裁决落地
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.review.models import ReviewState
from core.review.sync_engine import SyncEngine, build_initial_framework

STORY_OLD = """陈默把水晶接入读数仪。房间安静得可怕。"""

STORY_NEW = """陈默把水晶接入读数仪。房间安静得可怕。突然，灯灭了。陈默听见了身后的脚步声，他握紧了刀。但是门却被从外面反锁了，他感到一阵绝望。"""


def make_state() -> ReviewState:
    st = ReviewState(project_id="p1")
    st.draft = {"content": STORY_OLD, "version": 1, "last_modified": 0}
    st.framework = build_initial_framework()
    st.chapters = [{"number": 1, "title": "第一章", "summary": "", "status": "writing",
                    "wordCount": len(STORY_OLD), "wordTarget": 2000, "sceneIds": []}]
    return st


class TestSyncEngineOffline:
    def test_sync_no_change_returns_empty(self):
        st = make_state()
        eng = SyncEngine()
        res = eng.sync("p1", "draft", {"content": STORY_OLD}, state=st)
        assert res["status"] == "completed"
        assert res["changes"] == {}

    def test_draft_to_framework_adds_beats(self):
        st = make_state()
        eng = SyncEngine()
        res = eng.sync("p1", "draft", {"content": STORY_NEW}, state=st)
        assert res["status"] == "completed"
        fw = res["changes"].get("framework")
        assert fw is not None and fw["action"] in ("update", "rewrite")
        assert len(fw["diff"]["added"]) >= 1
        # 新增节拍应含张力分类
        assert all(b.get("charge") for b in fw["diff"]["added"])

    def test_draft_to_characters_detects_new_person(self):
        st = make_state()
        eng = SyncEngine()
        res = eng.sync("p1", "draft", {"content": STORY_NEW}, state=st)
        chars = res["changes"].get("characters")
        assert chars is not None
        assert any(d["name"] == "陈默" for d in chars["diff"]["added"])

    def test_draft_to_chapters_updates_wordcount(self):
        st = make_state()
        eng = SyncEngine()
        res = eng.sync("p1", "draft", {"content": STORY_NEW}, state=st)
        ch = res["changes"].get("chapters")
        assert ch is not None
        # 新正文更长，字数应大于旧字数
        assert ch["data"][0]["wordCount"] > len(STORY_OLD)

    def test_lock_conflict_blocks_target(self):
        st = make_state()
        st.locks = {"draft": False, "framework": True, "chapters": False, "characters": False}
        eng = SyncEngine()
        res = eng.sync("p1", "draft", {"content": STORY_NEW}, state=st)
        assert res["status"] == "conflict"
        assert any(c["target_view"] == "framework" and c["conflict_type"] == "lock"
                   for c in res["conflicts"])

    def test_force_bypasses_lock(self):
        st = make_state()
        st.locks = {"draft": False, "framework": True, "chapters": False, "characters": False}
        eng = SyncEngine()
        res = eng.sync("p1", "draft", {"content": STORY_NEW}, state=st, mode="force")
        assert res["status"] == "completed"

    def test_framework_restructure_rewrites_draft(self):
        st = make_state()
        st.draft = {"content": "旧稿内容。", "version": 1, "last_modified": 0}
        new_fw = {
            "template": "three_act",
            "acts": build_initial_framework()["acts"],
            "beats": [{"id": "b1", "actId": "act_1", "name": "引出水晶", "chapter": 1,
                       "description": "陈默获得水晶", "storyValue": "positive", "charge": "none"},
                      {"id": "b2", "actId": "act_2", "name": "绝境", "chapter": 2,
                       "description": "被反锁", "storyValue": "negative", "charge": "positive_to_negative"}],
            "version": 2,
        }
        eng = SyncEngine()
        res = eng.sync("p1", "framework", new_fw, state=st)
        assert res["status"] == "completed"
        draft = res["changes"].get("draft")
        assert draft is not None and draft["action"] == "rewrite"
        assert "结构重写草案" in draft["data"]["content"]

    def test_chapters_add_suggests_expand(self):
        st = make_state()
        new_ch = [dict(c) for c in st.chapters] + [
            {"number": 2, "title": "第二章", "summary": "", "status": "planned",
             "wordCount": 0, "wordTarget": 2000, "sceneIds": []}]
        eng = SyncEngine()
        res = eng.sync("p1", "chapters", new_ch, state=st)
        draft = res["changes"].get("draft")
        assert draft is not None and draft["action"] == "adjust"
        assert draft["adjustments"][0]["type"] == "expand"

    def test_characters_belief_change_suggests_rewrite(self):
        st = make_state()
        st.characters = [{"id": "c1", "name": "陈默", "role": "protagonist",
                          "beliefs": ["世界是安全的"], "goals": [], "secrets": [],
                          "arc": {"startChapter": 1, "endChapter": 0, "transformation": ""},
                          "firstAppearance": 1}]
        new_chars = [{"id": "c1", "name": "陈默", "role": "protagonist",
                      "beliefs": ["世界是安全的", "必须相信直觉"], "goals": ["逃出去"], "secrets": [],
                      "arc": {"startChapter": 1, "endChapter": 0, "transformation": ""},
                      "firstAppearance": 1}]
        eng = SyncEngine()
        res = eng.sync("p1", "characters", new_chars, state=st)
        draft = res["changes"].get("draft")
        assert draft is not None and draft["action"] == "adjust"
        assert any(a["type"] == "rewrite_dialogue" for a in draft["adjustments"])

    def test_target_views_filter(self):
        st = make_state()
        eng = SyncEngine()
        res = eng.sync("p1", "draft", {"content": STORY_NEW},
                       options={"target_views": ["chapters"]}, state=st)
        assert set(res["changes"].keys()) <= {"chapters"}


class TestReviewState:
    def test_record_change_capped(self):
        st = make_state()
        for i in range(250):
            st.record_change({"id": f"c{i}"})
        assert len(st.change_history) <= 200
        assert st.change_history[-1]["id"] == "c249"

    def test_snapshot_view(self):
        st = make_state()
        assert st.snapshot_view("draft") is st.draft
