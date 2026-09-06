"""
产品化计划 v1 L2 测试 — 质量检测 / AI续写 / 审计端点
Run: python -X utf8 -m pytest tests/test_product_v1.py -v
"""

import pytest
from fastapi.testclient import TestClient

from bridge.api_server import app

client = TestClient(app)


def log_ok(m):
    print("[OK] " + m)


def _mkproject() -> str:
    r = client.post(
        "/import-from-pwa",
        json={
            "premise": "产品化测试项目",
            "unit_text": "产品化测试项目",
            "characters": [{"name": "陈默", "role": "主角"}],
            "tone": "悬疑暗流",
            "conflict": "生存冲突",
        },
    )
    return r.json()["project_id"]


class TestProductV1:
    # ── W2: 四大质量检测模块 ──

    def test_reality_effect(self):
        from core.quality.reality_effect import RealityEffectDetector

        d = RealityEffectDetector()
        abstract = "人生的意义在于爱情。命运的安排让一切都充满某种深刻的情感，他的内心充满孤独与绝望，对自由与世界有说不出的复杂感受。"
        issues = d.detect(abstract)
        rules = {i["rule"] for i in issues}
        assert rules  # 抽象密度应命中至少一条
        # 具体文本零误报
        concrete = (
            "他推开沉重的木门，门轴发出刺耳的呻吟。空气里弥漫着灰尘与旧书页的味道。"
            "月光落在她半边脸上，她攥紧了袖口。"
        )
        assert d.detect(concrete) == []
        log_ok("reality_effect: " + str(sorted(rules)))

    def test_control_illusion(self):
        from core.quality.control_illusion import ControlIllusionDetector

        d = ControlIllusionDetector()
        pov_jump = (
            "我推开门，看见他坐在窗边。他说：你来了。我走过去。他的目光一直落在我的手上。"
            "她觉得这很不寻常，但他没有说破。"
        )
        rules = {i["rule"] for i in d.detect(pov_jump)}
        assert "pov_jump" in rules or "missing_concrete" in rules
        log_ok("control_illusion: " + str(sorted(rules)))

    def test_micro_tension(self):
        from core.quality.micro_tension import MicroTensionDetector

        d = MicroTensionDetector()
        # 3 段、无张力词、反复强调平淡
        flat = (
            "他走在街上，街上很平静，一切如常。\n"
            "人们过着平淡的日子，一如既往，没什么特别。\n"
            "生活平静如水，每个人都安详地走着，如常地回家。"
        )
        rules = {i["rule"] for i in d.detect(flat)}
        assert "tension_flat" in rules or "paragraph_tension_deficit" in rules
        log_ok("micro_tension: " + str(sorted(rules)))

    def test_show_dont_tell(self):
        from core.quality.show_dont_tell import ShowDontTellDetector

        d = ShowDontTellDetector()
        telling = "他很生气。她很难过。他很害怕。她非常开心。"
        rules = {i["rule"] for i in d.detect(telling)}
        assert any(r.startswith("telling_") for r in rules)
        log_ok("show_dont_tell: " + str(sorted(rules)))

    def test_quality_aggregator_endpoint(self):
        pid = _mkproject()
        r = client.post(
            "/api/quality",
            json={
                "project_id": pid,
                "text": "他很生气。她很难过。他很害怕。她非常开心。他走在街上，一切如常，没有异常，没有什么不对劲。",
            },
        )
        assert r.status_code == 200
        d = r.json()
        assert d["total"] > 0
        assert "show_dont_tell" in d["families"]
        log_ok(f"quality endpoint: {d['total']} issues, families={d['families']}")

    # ── W1: 审计端点 ──

    def test_audit_endpoint(self):
        pid = _mkproject()
        r = client.post(
            "/project/" + pid + "/audit",
            json={
                "project_id": pid,
                "text": "第一章：他推开门，看见灯光。她坐在窗边。窗外雨声渐大。",
            },
        )
        assert r.status_code == 200
        d = r.json()
        assert "overall_score" in d
        assert "gate_results" in d
        assert "quality" in d and isinstance(d["quality"], list)
        log_ok(f"audit endpoint: score={d['overall_score']}, quality={d['quality_total']}")

    # ── W1: AI 续写（LLM 依赖，允许 503 降级） ──

    def test_ai_continue(self):
        pid = _mkproject()
        client.post(
            "/project/" + pid + "/submit-chapter",
            json={
                "project_id": pid,
                "text": "第一章：陈默把水晶接入读数仪。七层加密逐层解开。第五层时，他听到了声音——直接在颅骨里震动。",
            },
        )
        r = client.post(
            "/project/" + pid + "/ai-continue",
            json={
                "project_id": pid,
                "text": "陈默把水晶接入读数仪。七层加密逐层解开。第五层时，他听到了声音——直接在颅骨里震动。",
                "word_target": 300,
            },
        )
        if r.status_code == 503:
            log_ok("ai-continue: LLM unavailable, graceful 503")
            return
        assert r.status_code == 200
        d = r.json()
        assert len(d["text"]) >= 100
        assert "score" in d
        log_ok(
            f"ai-continue: {len(d['text'])} chars, score={d['score']}, ctx={d['context_tokens']}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
