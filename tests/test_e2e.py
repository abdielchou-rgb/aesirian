"""
E2E 全流程测试（产品化 W4）— 从灵感到写作到审计到导出
覆盖：创建→AI生成→提交→审计(含质量)→推演→发散→大纲→Wiki→导出
Run: python -X utf8 -m pytest tests/test_e2e.py -v
"""

import pytest
from fastapi.testclient import TestClient

from bridge.api_server import app

client = TestClient(app)


def log_ok(m):
    print("[OK] " + m)


class TestE2E:
    def test_full_product_flow(self):
        """一条链走完产品核心流程"""
        # 1. 灵感 → 创建项目
        r = client.post(
            "/import-from-pwa",
            json={
                "premise": "深海空间站的心理医生发现患者共享同一个梦",
                "unit_text": "深海空间站的心理医生发现患者共享同一个梦",
                "characters": [
                    {"name": "沈夜", "role": "心理医生"},
                    {"name": "林晚", "role": "患者"},
                ],
                "tone": "悬疑暗流",
                "conflict": "认知冲突",
            },
        )
        assert r.status_code == 200
        pid = r.json()["project_id"]

        # 2. 上下文组装可观察
        ctx = client.get("/api/context", params={"project_id": pid, "query": "沈夜 梦境 秘密"})
        assert ctx.status_code == 200 and ctx.json()["total_tokens"] > 0

        # 3. AI 续写（LLM 依赖，允许降级）
        cont = client.post(
            "/project/" + pid + "/ai-continue",
            json={
                "project_id": pid,
                "text": "沈夜在诊室坐下。林晚第三次重复同一个梦：深海的走廊，尽头有光。",
                "word_target": 300,
            },
        )
        if cont.status_code == 503:
            log_ok("AI continue degraded (no LLM)")
        else:
            assert cont.status_code == 200 and len(cont.json()["text"]) >= 100

        # 4. 提交章节 → 审计（含质量检测）
        sub = client.post(
            "/project/" + pid + "/submit-chapter",
            json={
                "project_id": pid,
                "text": "第一章：沈夜在诊室坐下。林晚第三次重复同一个梦——深海的走廊，尽头有光。他翻开档案，发现所有患者都画过同一扇门。指尖停在一行小字上：禁止提及。",
            },
        )
        assert sub.status_code == 200
        assert sub.json()["submitted"] is True
        assert "cross_chapter" in sub.json()

        aud = client.post(
            "/project/" + pid + "/audit",
            json={
                "project_id": pid,
                "text": "第二章：沈夜走进档案室，灯光忽明忽暗。他听见门后有呼吸声。",
            },
        )
        assert aud.status_code == 200
        assert "quality" in aud.json()
        # P0-2: /audit 默认 dry_run，不落库、不推进章节号
        assert aud.json().get("dry_run") is True
        assert aud.json().get("submitted") is False

        # 显式提交第 2 章（P0-2 后 /audit 不再隐式落库；提交走 /submit-chapter）
        sub2 = client.post(
            "/project/" + pid + "/submit-chapter",
            json={
                "project_id": pid,
                "text": "第二章：沈夜走进档案室，灯光忽明忽暗。他听见门后有呼吸声。",
            },
        )
        assert sub2.status_code == 200
        assert sub2.json()["submitted"] is True

        # 5. 心智网格
        mg = client.get("/project/" + pid + "/mind-grid")
        assert mg.status_code == 200 and len(mg.json()["characters"]) >= 1

        # 6. 推演（克隆不污染）
        sim = client.post(
            "/project/" + pid + "/simulate",
            json={
                "hypothesis": "如果沈夜发现林晚也在撒谎",
                "belief_changes": [],
            },
        )
        assert sim.status_code == 200 and sim.json()["branches"]

        # 7. 发散
        div = client.post(
            "/diverge",
            json={
                "fragments": ["深海走廊的尽头有光", "档案里画着同一扇门", "禁止提及四个字"],
            },
        )
        assert div.status_code == 200 and len(div.json()["worldlines"]) == 5

        # 8. 大纲
        ol = client.post(
            "/api/generate-outline",
            json={
                "premise": "深海空间站的心理医生发现患者共享同一个梦",
                "template": "three_act",
                "target_chapters": 6,
            },
        )
        assert ol.status_code == 200 and len(ol.json()["acts"]) == 3

        # 9. Wiki 自动收获
        harvest = client.post("/project/" + pid + "/wiki/harvest", json={})
        assert harvest.status_code == 200

        # 10. 导出 Markdown + EPUB
        md = client.get("/project/" + pid + "/export/md")
        assert md.status_code == 200 and len(md.content) > 100
        epub = client.get("/project/" + pid + "/export/epub")
        assert epub.status_code == 200 and epub.content[:4] == b"PK\x03\x04"

        # 11. 风格报告 + 市场发布
        sr = client.get("/project/" + pid + "/style-report")
        assert sr.status_code == 200
        pub = client.post(
            "/style-profiles",
            json={
                "project_id": pid,
                "name": "深海梦境风",
                "genre_tags": ["悬疑"],
            },
        )
        assert pub.status_code == 200

        # 12. 持久化验证（新 orchestrator 重载）
        from core.orchestrator import Orchestrator
        from core.persistence.store import ProjectStore

        # 沙箱/内存回退时，新 ProjectStore 实例共享同一 in-memory 引擎；
        # 文件模式下则走同一 aesirian.db。
        reloaded = Orchestrator(store=ProjectStore()).get_project(pid)
        assert reloaded is not None and reloaded.current_chapter >= 2

        log_ok(f"E2E full flow: project {pid[:10]} 12/12 stages")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
