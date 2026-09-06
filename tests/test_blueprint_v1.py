"""
蓝图 v1.0 L2 测试 — 上下文工程 / 生成质量 / 大纲规划 / VoiceProfile
Run: python -X utf8 -m pytest tests/test_blueprint_v1.py -v
"""

import pytest
from fastapi.testclient import TestClient

from bridge.api_server import app

client = TestClient(app)


def _mkproject(premise="蓝图测试项目") -> str:
    r = client.post(
        "/import-from-pwa",
        json={
            "premise": premise,
            "unit_text": premise,
            "characters": [{"name": "陈默", "role": "主角"}, {"name": "曹渊", "role": "来客"}],
            "tone": "悬疑暗流",
            "conflict": "生存冲突",
        },
    )
    return r.json()["project_id"]


def _mkproject_with_chapter() -> str:
    pid = _mkproject()
    client.post(
        "/project/" + pid + "/submit-chapter",
        json={
            "project_id": pid,
            "text": "第一章：夜色像墨一样浓。陈默推开沉重的木门，门轴发出刺耳的呻吟。空气里弥漫着灰尘的味道。曹渊坐在窗边说：「你来了。」陈默没有回答，只是走近。窗外雨声渐大。",
        },
    )
    return pid


def log_ok(m):
    print("[OK] " + m)


class TestBlueprintV1:
    # ── W1: 上下文工程 ──

    def test_context_assembly_layers(self):
        """蓝图3.1: 分层组装含 PROJECT/CHARACTERS/RECENT/EPISODIC/DERIVED/USER"""
        pid = _mkproject_with_chapter()
        r = client.get("/api/context", params={"project_id": pid, "query": "陈默 水晶 秘密"})
        assert r.status_code == 200
        d = r.json()
        assert d["total_tokens"] > 0
        layers = d["layers"]
        assert layers["PROJECT"]["chars"] > 0
        assert layers["CHARACTERS"]["chars"] > 0
        assert layers["RECENT"]["chars"] > 0
        assert layers["USER"]["chars"] > 0
        assert "角色档案" in d["text"] and "故事设定" in d["text"]
        log_ok("context layers: " + str([k for k, v in layers.items() if v["chars"] > 0]))

    def test_context_project_not_found(self):
        r = client.get("/api/context", params={"project_id": "nonexistent"})
        assert r.status_code == 404

    # ── W1: InkOS 4 规则（经质量管线端点间接验证 + 直接单测） ──

    def test_ai_tell_detector_rules(self):
        """蓝图3.4: 四条 AI 痕迹规则"""
        from core.quality.ai_tell_detector import AITellDetector

        d = AITellDetector()
        # 段落均匀
        uniform = "\n".join(
            "他走了三步然后停下。然而他似乎想到了什么。所以她大概明白了。" for _ in range(3)
        )
        # 公式化过渡
        formulaic = "然而他走了。然后她来了。然而他停了。然后她坐了。接着灯灭了。"
        issues = d.detect(uniform + "\n" + formulaic)
        rules = {i["rule"] for i in issues}
        assert "formulaic_transition" in rules
        assert "paragraph_uniformity" in rules or "hedge_density" in rules
        # 干净文本零误报
        clean = (
            "夜色像墨一样浓。他推开那扇沉重的木门，门轴发出刺耳的呻吟，仿佛多年未曾有人来过。\n"
            "空气里弥漫着灰尘与旧书页混合的味道。他抬头，看见她坐在窗边。\n"
            "月光落在她半边脸上，另一半隐在阴影里。她开口说：「你来了。」他握紧了口袋里的钥匙，没有回答。"
        )
        assert d.detect(clean) == []
        log_ok("AITellDetector: " + str(sorted(rules)))

    # ── W1: VoiceProfile ──

    def test_voice_profile(self):
        """蓝图3.3.2: 从已写文本推导作者声音"""
        pid = _mkproject_with_chapter()
        r = client.get("/api/voice-profile/" + pid)
        assert r.status_code == 200
        d = r.json()
        assert "profile" in d
        assert d["profile"]["pov_preference"] in ("第一人称", "第三人称")
        log_ok("voice profile: " + d["profile"]["pov_preference"] + " | " + d["prompt"][:40])

    def test_voice_profile_heuristic_fallback(self):
        """LLM 不可用也有启发式档案"""
        from core.style.voice_profile import VoiceProfileInterview

        # 足够长的第三人称样本（>60 字）
        vp = VoiceProfileInterview().extract_from_text(
            "夜很深，走廊尽头的灯忽明忽暗。他推开门，门轴发出刺耳的呻吟。"
            "她说：「你终于来了。」他没有回答，只是把外套挂在了门边。"
            "两人对坐着，谁都没有先开口。窗外的雨声渐渐大了。"
        )
        assert vp.source == "heuristic"
        assert vp.pov_preference == "第三人称"
        assert vp.dialogue_ratio_target > 0
        # 过短文本：不猜 POV，返回空档案默认值
        vp_short = VoiceProfileInterview().extract_from_text("太短")
        assert vp_short.source == "heuristic"

    # ── W2: 大纲规划 ──

    def test_generate_outline(self):
        """蓝图3.2: 递归大纲 + GOAT/Dramatica/MICE 标注 + LIFO 验证"""
        r = client.post(
            "/api/generate-outline",
            json={
                "premise": "火星殖民地侦探调查密室谋杀案",
                "template": "three_act",
                "target_chapters": 6,
            },
        )
        assert r.status_code == 200
        d = r.json()
        acts = d["acts"]
        assert len(acts) == 3
        all_ch = [c for a in acts for c in a["chapters"]]
        assert len(all_ch) >= 6
        # Dramatica 视角轮转
        povs = [c["primary_pov"] for c in all_ch[:4]]
        assert len(set(povs)) == 4
        # 至少一章标注高潮位置（Freytag 0.625）
        assert any(c["climax_position"] > 0 for c in all_ch)
        # 序列化完整
        assert "outline_json" in d
        log_ok(
            f"outline: {len(acts)} acts, {len(all_ch)} chapters, "
            f"violations={len(d['mice_violations'])}"
        )

    def test_mice_lifo_validation(self):
        """蓝图 G15: MICE LIFO 违规检测真实抓错"""
        from core.planning.outline import OutlineNode, StoryOutline

        root = OutlineNode(
            id="root",
            level="act",
            title="t",
            children=[
                # 外层 idea 线程开启不闭合
                OutlineNode(
                    id="a1", level="chapter", title="外层", mice_type="idea", mice_open_chapter=1
                ),
                # 内层 event 先闭合（合规 LIFO）
                OutlineNode(
                    id="a2", level="chapter", title="内层", mice_type="event", mice_open_chapter=2
                ),
                OutlineNode(
                    id="a3",
                    level="chapter",
                    title="内层闭",
                    mice_type="event",
                    mice_close_chapter=3,
                ),
            ],
        )
        ol = StoryOutline(root=root)
        v = ol.validate_mice_lifo()
        assert any(x["rule"] == "mice_unclosed" for x in v)
        log_ok("MICE LIFO catches unclosed thread")

    # ── W1: 生成质量管线（LLM 依赖，允许 503 降级） ──

    def test_generate_with_quality(self):
        pid = _mkproject_with_chapter()
        r = client.post(
            "/api/generate-with-quality",
            json={
                "project_id": pid,
                "instruction": "陈默发现水晶里的记忆指向一个更大的阴谋",
                "word_target": 400,
            },
        )
        if r.status_code == 503:
            log_ok("quality generation: LLM unavailable, graceful 503")
            return
        assert r.status_code == 200
        d = r.json()
        assert len(d["text"]) >= 100
        assert 0 <= d["score"] <= 100
        assert d["rounds"] >= 1
        log_ok(
            f"quality generation: score={d['score']} rounds={d['rounds']} "
            f"ctx_tokens={d['context_tokens']}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
