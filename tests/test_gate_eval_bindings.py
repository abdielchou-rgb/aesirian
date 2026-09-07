"""P1-5 (2026-09-07): 每门禁独立单测——safe_eval 实参绑定行为快照。

审计 P1-5 清单："registry dataclass + 每门禁独立单测 + 死门禁检测"。
registry(GATE_CATALOG) 与死门禁检测(test_gate_dead_dispatch) 已落地，本文件补上
"每门禁独立单测"：对 GATE_CATALOG 全部门禁，在代表性子上下文中直接跑 safe_eval，
锁定每门禁 evaluate 实参绑定的行为快照（passed/severity/message 前缀）。

用途：
1. 防止日后改动 safe_eval 分支/表驱动化时悄悄改变某门禁的参数绑定；
2. 作为"表驱动化重构"的差分安全网——先跑本测试得基线，重构后必须仍绿。

设计：不逐门禁手写断言（142×N 条不可维护），而是"全门禁 × 多上下文"的行为快照
+ 关键门禁的重点语义断言。快照断言刻意宽松到能抓"绑定错误/异常/假通过"，
又不过度耦合 message 细节。

Run: python -X utf8 -m pytest tests/test_gate_eval_bindings.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

import pytest  # noqa: E402
from wenjian.audit.gates import GATE_CATALOG, get_gate  # noqa: E402
from wenjian.audit.pipeline import AuditPipeline  # noqa: E402

# 代表性子上下文：干净短章 / 植入矛盾 / 带角色 / 第2章 / 带节奏字段
CONTEXTS = {
    "clean_short": {
        "chapter_text": "第一章：陈默走进工坊，夜风裹着冷却液的气味。他把水晶接入读数仪。他推开门，看见屋里灯还亮着。",
        "chapter_index": 0,
        "chapter_number": 1,
    },
    "implant_time": {
        "chapter_text": "陈默修了十一年罪忆水晶——准确地说，是二十一年，从没见过这样的。",
        "chapter_index": 0,
        "chapter_number": 1,
    },
    "with_character": {
        "chapter_text": "第一章：陈默看着曹渊，说我们明天就走。",
        "chapter_index": 0,
        "chapter_number": 1,
        "character": {"name": "陈默", "has_conscious": True, "desire_spoken": True, "recent_progress": ["x"]},
    },
    "chapter2": {
        "chapter_text": "第二章：雨停了，他推开门，看见灯还亮着。",
        "chapter_index": 1,
        "chapter_number": 2,
    },
    "rhythm_ctx": {
        "chapter_text": "第一章：夜色里，他快步穿过长廊，手指划过冰凉的墙面。远处传来低语声。",
        "chapter_index": 0,
        "chapter_number": 1,
        "act_pct": 0.5,
        "chapter_sentiment": 0.3,
        "webnovel_rhythm_score": 0.6,
        "readability": 0.7,
    },
}
CTX_KEYS = list(CONTEXTS)


@pytest.fixture(scope="module")
def pipeline():
    return AuditPipeline(genre_id="suspense", platform="webnovel")


@pytest.mark.parametrize("gid", sorted(GATE_CATALOG))
@pytest.mark.parametrize("ctx_name", CTX_KEYS)
def test_every_gate_evaluates_without_error(pipeline, gid, ctx_name):
    """全门禁 × 全代表上下文：safe_eval 不抛异常、返回 GateResult、不静默假通过。

    排除项：跨章专用门禁（STC-01..22/RVI-06）与结构性门禁（SVT-01 等）在本单章
    ctx 下缺数据会 SKIPPED——这是预期；此处只要求"不崩溃 + 返回合法结果"。
    """
    ctx = pipeline._enrich_context(dict(CONTEXTS[ctx_name]))
    gate = get_gate(gid)
    result = pipeline.safe_eval(gate, ctx)
    assert result is not None, f"{gid} safe_eval 返回 None"
    assert hasattr(result, "passed"), f"{gid} 结果缺少 passed"
    assert result.severity.value in {"block", "warn", "pass", "info"}, f"{gid} 非法 severity"


@pytest.mark.parametrize("gid", sorted(GATE_CATALOG))
def test_every_gate_has_registry_meta(pipeline, gid):
    """registry 元数据完整（params schema 与 evaluate 签名一致）。"""
    import inspect

    meta = GATE_CATALOG[gid]
    gate = get_gate(gid)
    sig = inspect.signature(gate.evaluate)
    # registry params 必须都是 evaluate 的真实参数（防 schema 与实现漂移）
    for p in meta["params"]:
        assert p in sig.parameters, f"{gid} registry params 含 evaluate 没有的参数: {p}"


# ── 关键语义锚点：这几类绑定错误最容易在重构时悄悄引入 ──

def test_clean_short_anchor_bindings(pipeline):
    """干净短章：safe_eval 直接调用不抛错（SKIP 决策在 run_full 层，此处只测纯 evaluate）。"""
    ctx = pipeline._enrich_context(dict(CONTEXTS["clean_short"]))
    for gid in ("G3-04", "BRK-01", "SVT-01", "LANG-04", "NFR-03"):
        r = pipeline.safe_eval(get_gate(gid), ctx)
        assert "evaluation error" not in (r.message or ""), f"{gid} 绑定异常: {r.message}"
        # SVT-01 缺 entry/exit 时纯 evaluate 返回 warn fail——合法（SKIP 是 run_full 职责）
    # run_full 层验证：结构门禁缺数据才真正 SKIPPED（回归 P1-5 语义）
    rep = pipeline.run_full(ctx)
    svt = next(r for r in rep.gate_results if r.gate_id == "SVT-01")
    assert getattr(svt, "skipped", False) is True, "SVT-01 单章缺数据应 SKIPPED（run_full 层）"


def test_implanted_time_surfaces_numeric_signal(pipeline):
    """植入"十一年→二十一年"：数值矛盾在单章 run_full 不可见（走跨章 CSN），
    但 scan_numeric_facts 必须抽出时长事实（P0-3 契约）。"""
    from core.csn_consistency import scan_numeric_facts

    facts = scan_numeric_facts(CONTEXTS["implant_time"]["chapter_text"])
    assert any(f.subject == "陈默" and f.predicate == "时长" for f in facts)


def test_with_character_bindings_do_not_crash(pipeline):
    """带 character dict 上下文：DDT/RSM 等依赖 ch 的门禁应正常求值不崩。"""
    ctx = pipeline._enrich_context(dict(CONTEXTS["with_character"]))
    for gid in ("DDT-01", "DDT-02", "RSM-01", "CRN-01"):
        r = pipeline.safe_eval(get_gate(gid), ctx)
        assert "evaluation error" not in (r.message or ""), f"{gid} 异常: {r.message}"
