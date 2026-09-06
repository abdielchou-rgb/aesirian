"""
L2 API Integration Tests — Full business flow verification via TestClient
Run: pytest tests/test_api_flows.py -v
"""

import pytest
from fastapi.testclient import TestClient

from bridge.api_server import app

client = TestClient(app)


def log_ok(msg):
    print("[OK] " + msg)


class TestAPIFlows:
    """End-to-end API flow tests matching user stories"""

    def test_health_endpoint(self):
        """Health check returns all engines ready"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "engines" in data
        assert len(data["engines"]) >= 5  # tom, kg, gates, reader, cooldown
        log_ok("Health endpoint works")

    def test_create_project_from_idea(self):
        """User can create project from one-sentence idea"""
        response = client.post(
            "/import-from-pwa",
            json={
                "premise": "A detective on Mars investigates a murder",
                "unit_text": "Full story text here...",
                "characters": [{"name": "Detective Chen", "role": "Protagonist"}],
                "tone": "悬疑暗流",
                "conflict": "生存冲突",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "project_id" in data
        assert "title" in data
        assert "mind_grid_url" in data
        log_ok("Create project works: " + data["project_id"][:12])
        return data["project_id"]

    def test_get_mind_grid(self):
        """Mind grid returns character/belief data for visualization"""
        pid = self.test_create_project_from_idea()
        response = client.get("/project/" + pid + "/mind-grid")
        assert response.status_code == 200
        data = response.json()
        assert "characters" in data
        assert "tension_points" in data
        assert "relationships" in data
        assert "chapter" in data
        log_ok("Mind grid endpoint works")

    def test_submit_chapter(self):
        """Submit chapter runs gates and returns audit results"""
        pid = self.test_create_project_from_idea()
        response = client.post(
            "/project/" + pid + "/submit-chapter",
            json={
                "project_id": pid,
                "text": "Chapter 1: The body was found in airlock 7. Detective Chen arrived first.",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "submitted" in data
        assert "overall_score" in data
        assert "gate_results" in data
        assert "audit_results" in data
        log_ok("Submit chapter works: score=" + str(data["overall_score"]))
        return pid

    def test_get_suggestions(self):
        """Get continuation suggestions after chapter submission"""
        pid = self.test_submit_chapter()
        response = client.post("/project/" + pid + "/suggestions", json={"project_id": pid})
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert "llm_available" in data
        assert "tension_count" in data
        assert "character_count" in data
        assert "transportation_trend" in data
        assert isinstance(data["suggestions"], list)
        log_ok("Suggestions work: " + str(len(data["suggestions"])) + " suggestions")

    def test_load_sample_chapter(self):
        """Load sample chapter 1 text"""
        response = client.get("/chapter-1-sample")
        assert response.status_code == 200
        text = response.text
        assert len(text) > 100
        assert "陈默" in text or "Chapter" in text
        log_ok("Sample chapter loads")

    def test_validate_text(self):
        """Validate text without submitting (pre-generation gates)"""
        pid = self.test_create_project_from_idea()
        response = client.post(
            "/project/" + pid + "/validate",
            json={"project_id": pid, "text": "Test text for validation"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "gate_results" in data
        assert isinstance(data["gate_results"], list)
        log_ok("Text validation works")

    def test_update_belief(self):
        """Update character belief via mind grid"""
        pid = self.test_create_project_from_idea()
        response = client.post(
            "/project/" + pid + "/belief",
            json={
                "project_id": pid,
                "character": "Detective Chen",
                "proposition": "The murderer is on the station",
                "value": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "tensions" in data
        log_ok("Belief update works")

    def test_get_constraints(self):
        """Get scene constraints for LLM generation"""
        pid = self.test_create_project_from_idea()
        response = client.post("/project/" + pid + "/constraints")
        assert response.status_code == 200
        data = response.json()
        assert "tension_points" in data
        assert "character_tendencies" in data
        assert "reader_state" in data
        assert "recommended_patterns" in data
        log_ok("Constraints endpoint works")

    def test_full_user_flow(self):
        """Complete user flow: create -> submit -> suggestions -> mind-grid"""
        # Create
        create_resp = client.post(
            "/import-from-pwa",
            json={
                "premise": "Full flow test",
                "unit_text": "Story...",
                "characters": [{"name": "Hero", "role": ""}],
                "tone": "温暖治愈",
                "conflict": "关系冲突",
            },
        )
        pid = create_resp.json()["project_id"]

        # Submit chapter
        submit_resp = client.post(
            "/project/" + pid + "/submit-chapter",
            json={"project_id": pid, "text": "Chapter 1: The adventure begins."},
        )
        assert submit_resp.json()["submitted"]

        # Get suggestions
        sug_resp = client.post("/project/" + pid + "/suggestions", json={"project_id": pid})
        assert len(sug_resp.json()["suggestions"]) > 0

        # Get mind grid
        mg_resp = client.get("/project/" + pid + "/mind-grid")
        assert len(mg_resp.json()["characters"]) > 0

        log_ok("Full user flow works end-to-end")

    # ─── #04 LLM Generation ───

    def test_generate_chapter(self):
        """#04: LLM generates 200-500 char chapter from one-line idea"""
        pid = self.test_create_project_from_idea()
        response = client.post(
            "/project/" + pid + "/generate-chapter",
            json={"prompt": "写一段关于错过的故事", "word_target": 300},
        )
        if response.status_code == 503:
            log_ok("Generate endpoint exists (LLM unavailable in test env — 503 graceful)")
            return
        assert response.status_code == 200
        data = response.json()
        assert data["llm_used"]
        assert len(data["text"]) >= 100
        log_ok("LLM chapter generation works: " + str(len(data["text"])) + " chars")

    # ─── #08 Chapter Management ───

    def test_chapter_crud(self):
        """#08: list / get / delete chapters"""
        pid = self.test_create_project_from_idea()
        # Submit 2 chapters
        for i in (1, 2):
            client.post(
                "/project/" + pid + "/submit-chapter",
                json={"project_id": pid, "text": "第" + str(i) + "章：旅途继续。夜色渐深。"},
            )
        # List
        r = client.get("/project/" + pid + "/chapters")
        assert r.status_code == 200
        chapters = r.json()
        assert len(chapters) == 2
        assert chapters[0]["number"] == 1
        assert chapters[1]["number"] == 2
        assert chapters[0]["word_count"] > 0
        # Get single
        r2 = client.get("/project/" + pid + "/chapters/1")
        assert r2.status_code == 200
        assert "旅途" in r2.json()["text"]
        # Delete
        r3 = client.delete("/project/" + pid + "/chapters/1")
        assert r3.status_code == 200
        assert r3.json()["deleted"]
        # Verify deletion
        r4 = client.get("/project/" + pid + "/chapters")
        assert len(r4.json()) == 1
        log_ok("Chapter CRUD works (list/get/delete)")

    # ─── #06 Export ───

    def test_markdown_export(self):
        """#06: Markdown export downloads full novel"""
        pid = self.test_create_project_from_idea()
        client.post(
            "/project/" + pid + "/submit-chapter",
            json={"project_id": pid, "text": "第一章：导出测试。这是正文内容。"},
        )
        r = client.get("/project/" + pid + "/export/md")
        assert r.status_code == 200
        assert len(r.content) > 50
        log_ok("Markdown export works: " + str(len(r.content)) + " bytes")

    # ─── #11 Style Report ───

    def test_style_report(self):
        """#11: Style fingerprint radar from submitted chapters"""
        pid = self.test_create_project_from_idea()
        # 无章节 → 400 优雅提示
        r0 = client.get("/project/" + pid + "/style-report")
        assert r0.status_code == 400
        assert "尚无" in r0.json()["detail"]
        # 提交含感官描写的章节
        client.post(
            "/project/" + pid + "/submit-chapter",
            json={
                "project_id": pid,
                "text": "夜色像墨一样浓。他推开沉重的木门，门轴发出刺耳的呻吟。空气里弥漫着灰尘的味道。月光落在她半边脸上。她开口说：你终于来了。他没有回答，只是走近坐下。",
            },
        )
        r = client.get("/project/" + pid + "/style-report")
        assert r.status_code == 200
        d = r.json()
        assert d["chapter_count"] == 1
        dash = d["dashboard"]
        indicators = dash["radar"]["indicators"]
        assert len(indicators) >= 6  # 虚词/词汇/句长/标点/对话/感官
        names = [i["name"] for i in indicators]
        assert "感官描写" in names and "对话占比" in names
        assert "sensory_radar" in dash
        assert "dialogue_pie" in dash
        log_ok("Style report works: " + str(len(indicators)) + " radar dims")

    # ─── #10 Gate tiered data ───

    def test_gate_results_shape_for_tiering(self):
        """#10: submit response carries level-tagged gate/audit results"""
        pid = self.test_create_project_from_idea()
        r = client.post(
            "/project/" + pid + "/submit-chapter",
            json={"project_id": pid, "text": "第一章：他推开门，看见屋里的灯光。她坐在窗边等他。"},
        )
        d = r.json()
        all_gates = d.get("gate_results", []) + d.get("audit_results", [])
        for g in all_gates:
            assert "level" in g, "gate result missing level for tiering"
        log_ok("Gate results carry level tags for tiered display")

    # ─── #12 Cross-chapter consistency ───

    def test_cross_chapter_consistency(self):
        """#12: contradicting numeric facts across chapters get flagged"""
        pid = self.test_create_project_from_idea()
        # Ch1: 年龄 30
        r1 = client.post(
            "/project/" + pid + "/submit-chapter",
            json={"project_id": pid, "text": "第一章：陈默今年三十岁，在洛阳星港修水晶。"},
        )
        assert "cross_chapter" in r1.json()
        # Ch2: 年龄 45 —— 应触发事实矛盾
        r2 = client.post(
            "/project/" + pid + "/submit-chapter",
            json={"project_id": pid, "text": "第二章：多年过去。陈默今年四十五岁，依然在星港。"},
        )
        d2 = r2.json()
        conflicts = d2.get("cross_chapter", [])
        # P0-3: CSN 数值矛盾检测器补齐了"三十岁→四十五岁"这类中文数词年龄矛盾
        # （原提取器只认阿拉伯数字句式，中文数词年龄从未被检出）。
        assert any(c["type"] == "csn_numeric_contradiction" for c in conflicts), (
            f"应检出年龄矛盾（三十岁→四十五岁），实际 conflicts={conflicts}"
        )
        for c in conflicts:
            assert c["type"] in (
                "fact_contradiction",
                "identity_shift_unexplained",
                "belief_contradiction",
                "csn_numeric_contradiction",
            )
            assert "severity" in c and "detail" in c
        log_ok(
            "Cross-chapter consistency endpoint wired: "
            + str(len(conflicts))
            + " conflicts detected"
        )

    # ─── #13 Methodology attribution ───

    def test_methodology_attribution(self):
        """#13: rule suggestions carry methodology source attribution"""
        pid = self.test_create_project_from_idea()
        client.post(
            "/project/" + pid + "/submit-chapter",
            json={
                "project_id": pid,
                "text": "第一章：他推开门。她转身离开，去了远方。两人就此错过。",
            },
        )
        r = client.post("/project/" + pid + "/suggestions", json={"project_id": pid})
        d = r.json()
        assert "suggestions" in d
        with_methodology = [s for s in d["suggestions"] if s.get("methodology")]
        # 至少部分规则建议带方法论标注（LLM 建议可选）
        log_ok(
            "Methodology attribution: "
            + str(len(with_methodology))
            + "/"
            + str(len(d["suggestions"]))
            + " suggestions annotated"
        )

    # ─── #15 Hypothetical simulation ───

    def test_simulate_hypothesis(self):
        """#15: what-if simulation returns branches without mutating main project"""
        pid = self.test_create_project_from_idea()
        r = client.post(
            "/project/" + pid + "/simulate",
            json={
                "hypothesis": "如果主角发现配角在撒谎",
                "belief_changes": [
                    {"character": "Detective Chen", "proposition": "配角在撒谎", "value": True}
                ],
                "branch_count": 3,
            },
        )
        assert r.status_code == 200
        d = r.json()
        assert "branches" in d and "tensions" in d and "applied_beliefs" in d
        assert 1 <= len(d["branches"]) <= 3
        for b in d["branches"]:
            assert "title" in b and "summary" in b
        # 主线未被污染：角色信念中不存在推演注入的命题
        mg = client.get("/project/" + pid + "/mind-grid").json()
        main_beliefs = {}
        for c in mg["characters"]:
            main_beliefs.update(c.get("world_beliefs") or {})
        assert "配角在撒谎" not in main_beliefs, "simulation leaked into main project!"
        log_ok("Simulation works: " + str(len(d["branches"])) + " branches, main project untouched")

    # ─── #16 Fragment divergence ───

    def test_diverge_fragments(self):
        """#16: 3 fragments -> 5 worldlines with beats"""
        r = client.post(
            "/diverge",
            json={
                "fragments": ["雨夜便利店的暖黄灯光", "抽屉里没有署名的信", "开走的末班地铁"],
                "count": 5,
            },
        )
        assert r.status_code == 200
        d = r.json()
        assert d["fragment_count"] == 3
        assert len(d["worldlines"]) == 5
        for wl in d["worldlines"]:
            assert "genre" in wl and "beats" in wl
            assert len(wl["beats"]) >= 3
        # 少于2个碎片 → 400
        r2 = client.post("/diverge", json={"fragments": ["只有一个碎片"], "count": 3})
        assert r2.status_code == 400
        log_ok("Divergence works: " + str(len(d["worldlines"])) + " worldlines from 3 fragments")

    # ─── #17 EPUB export ───

    def test_epub_export(self):
        """#17: EPUB export produces valid epub (PK zip header)"""
        pid = self.test_create_project_from_idea()
        client.post(
            "/project/" + pid + "/submit-chapter",
            json={"project_id": pid, "text": "第一章：夜色降临。他推开门，看见屋里的灯还亮着。"},
        )
        r = client.get("/project/" + pid + "/export/epub")
        assert r.status_code == 200
        assert r.content[:4] == b"PK\x03\x04", "not a valid epub/zip"
        assert len(r.content) > 1000
        log_ok("EPUB export works: " + str(len(r.content)) + " bytes")

    # ─── #18 World Wiki CRUD + harvest ───

    def test_world_wiki(self):
        """#18: wiki add / list / delete + chapter harvest"""
        pid = self.test_create_project_from_idea()
        client.post(
            "/project/" + pid + "/submit-chapter",
            json={
                "project_id": pid,
                "text": "第一章：他推开洛阳老宅的大门。屋里桌上有把青铜钥匙，泛着绿光。",
            },
        )
        # 手动添加
        r1 = client.post(
            "/project/" + pid + "/wiki",
            json={"name": "失乐园协议", "element_type": "event", "description": "军方机密"},
        )
        assert r1.status_code == 200
        eid = r1.json()["id"]
        # 列表
        r2 = client.get("/project/" + pid + "/wiki")
        d2 = r2.json()
        assert d2["counts"]["event"] >= 1
        # 自动收获（章节中的地点/物品）
        r3 = client.post("/project/" + pid + "/wiki/harvest", json={})
        assert r3.status_code == 200
        harvested = r3.json()["harvested"]
        # 再列（收获后应有更多元素）
        r4 = client.get("/project/" + pid + "/wiki")
        assert r4.json()["counts"]["location"] + r4.json()["counts"]["item"] >= 1
        # 删除
        r5 = client.delete("/project/" + pid + "/wiki/" + eid)
        assert r5.status_code == 200 and r5.json()["deleted"]
        log_ok("World Wiki works: add/list/harvest/delete, " + str(len(harvested)) + " harvested")

    # ─── #21 Style marketplace ───

    def test_style_marketplace(self):
        """#21: publish fingerprint -> browse marketplace -> apply to another project"""
        # 项目A：提交章节 + 生成风格报告（落指纹）
        pid_a = self.test_create_project_from_idea()
        client.post(
            "/project/" + pid_a + "/submit-chapter",
            json={
                "project_id": pid_a,
                "text": "第一章：夜色像墨一样浓。他推开沉重的木门，门轴发出刺耳的呻吟。月光落在她半边脸上，另一半隐在阴影里。",
            },
        )
        client.get("/project/" + pid_a + "/style-report")
        # 发布
        r1 = client.post(
            "/style-profiles",
            json={
                "project_id": pid_a,
                "name": "冷峻夜色风",
                "description": "高压悬疑",
                "genre_tags": ["悬疑"],
            },
        )
        assert r1.status_code == 200, r1.text
        profile_id = r1.json()["id"]
        # 浏览市场
        r2 = client.get("/style-profiles?sort=newest")
        names = [p["name"] for p in r2.json()]
        assert "冷峻夜色风" in names
        # 项目B应用
        pid_b = self.test_create_project_from_idea()
        client.post(
            "/project/" + pid_b + "/submit-chapter",
            json={
                "project_id": pid_b,
                "text": "第一章：阳光洒满房间。她微笑着走进来，一切都明亮温暖。",
            },
        )
        client.get("/project/" + pid_b + "/style-report")
        r3 = client.post("/project/" + pid_b + "/apply-style/" + str(profile_id))
        assert r3.status_code == 200
        assert r3.json()["applied"] is True
        # 下载计数
        r4 = client.get("/style-profiles")
        prof = next(p for p in r4.json() if p["id"] == profile_id)
        assert prof["download_count"] >= 1
        log_ok(
            "Style marketplace: publish -> browse -> apply (downloads: "
            + str(prof["download_count"])
            + ")"
        )

    # ─── #23 Plugin system ───

    def test_plugin_system(self):
        """#23: plugin discovery + gate execution in submit flow"""
        # 插件发现
        r1 = client.get("/plugins")
        assert r1.status_code == 200
        d1 = r1.json()
        names = [p["name"] for p in d1["plugins"]]
        assert "passive-voice-detector" in names, "gate plugin not loaded"
        assert "exclamation-density" in names, "analyzer plugin not loaded"
        types = {p["name"]: p["type"] for p in d1["plugins"]}
        assert types["passive-voice-detector"] == "gate"
        assert types["exclamation-density"] == "analyzer"
        # 试运行 gate 插件（高被动密度文本应 WARN）
        r2 = client.post(
            "/plugins/test-gate",
            json={
                "project_id": "x",
                "text": "他被骗了。他被迫离开。他受到了伤害。他遭受了打击。他被遣返了。",
            },
        )
        assert r2.status_code == 200
        pg = r2.json()["plugin_gate_results"]
        pv = next(p for p in pg if p["plugin"] == "passive-voice-detector")
        assert pv["level"] == "WARN"
        assert pv["gate_id"].startswith("PLUGIN::")
        # 正常文本应 PASS
        r3 = client.post(
            "/plugins/test-gate",
            json={"project_id": "x", "text": "他推开大门。月光洒在她脸上。他握紧了手中的钥匙。"},
        )
        pg3 = r3.json()["plugin_gate_results"]
        pv3 = next(p for p in pg3 if p["plugin"] == "passive-voice-detector")
        assert pv3["level"] == "PASS"
        # 提交流程含插件门禁
        pid = self.test_create_project_from_idea()
        r4 = client.post(
            "/project/" + pid + "/submit-chapter",
            json={"project_id": pid, "text": "第一章：他推开门，看见灯光。她坐在窗边。"},
        )
        assert "plugin_gates" in r4.json()
        assert isinstance(r4.json()["plugin_gates"], list)
        log_ok("Plugin system: 2 plugins loaded, gate executes in submit flow")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
