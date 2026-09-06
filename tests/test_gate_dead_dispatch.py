"""P1-5 (2026-09-07): safe_eval 表驱动化 / 死门禁检测。

深度审计发现：167 门禁中 23 道（STC-01..22 风格一致性 + RVI-06 邪恶力量揭示）
注册在 GATE_CATALOG 且被 run_full 遍历，但 safe_eval 无显式分支 → 静默落到
`return gate.pass_result()`（"registry 有而 dispatcher 无"的死门禁）。

修复（见 core/wenjian/audit/pipeline.py）：
1. 23 道跨章专用门禁声明进 STRUCTURAL_GATE_REQUIREMENTS——单章缺数据即显式
   SKIPPED（不再假通过）；
2. safe_eval 尾部静默 pass_result 改为 `_auto_bind_evaluate`：跨章/全稿路径通过
   style_baseline / context 提供 evaluate 参数时按 GATE_CATALOG params schema
   自动绑定真跑；必要参数缺失则显式 SKIPPED。

本测试固化三条铁律：
- 每条 registry 门禁在单章 run_full 的结果必须是"真跑过"或"显式 SKIPPED"，
  不允许"passed=True 且 skipped=False 但 dispatcher 无分支"（静默假通过）。
- 跨章路径提供 style_baseline 时 STC 门禁能真跑（死门禁可被激活）。
- 单章不提供 style_baseline 时 STC/RVI-06 显式 SKIPPED，不污染统计。

Run: python -X utf8 -m pytest tests/test_gate_dead_dispatch.py -v
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from wenjian.audit.gates import GATE_CATALOG, registry_gate_ids  # noqa: E402
from wenjian.audit.pipeline import (  # noqa: E402
    STRUCTURAL_GATE_REQUIREMENTS,
    AuditPipeline,
    _auto_bind_evaluate,
)

ROOT = Path(__file__).resolve().parents[1]


def _dispatcher_branches() -> set[str]:
    """静态提取 safe_eval 方法中的显式 gid 分支（含 startswith 前缀）。"""
    src = (ROOT / "core" / "wenjian" / "audit" / "pipeline.py").read_text(encoding="utf-8")
    m = re.search(r"def safe_eval\(self, gate, context\):.*?(?=\n    def )", src, re.S)
    assert m, "safe_eval 方法体未找到"
    body = m.group(0)
    exact = set(re.findall(r'if gid == "([A-Za-z0-9-]+)"', body))
    in_tuples: set[str] = set()
    for mt in re.finditer(r"if gid in \(([^)]*)\)", body):
        in_tuples.update(re.findall(r'"([A-Za-z0-9-]+)"', mt.group(1)))
    prefixes = set(re.findall(r'if gid\.startswith\("([A-Za-z0-9-]+)', body))
    covered = set(exact) | set(in_tuples)
    for p in prefixes:
        covered |= {g for g in GATE_CATALOG if g.startswith(p)}
    return covered


def _no_silent_pass(cfg=None):
    """跑一次单章 run_full，返回违反"静默假通过"的门禁清单。"""
    p = AuditPipeline(cfg)
    ctx = p._enrich_context({"text": "第一章：陈默走进工坊，夜风裹着冷却液的气味。他把水晶接入读数仪。", "chapter_index": 0})
    rep = p.run_full(ctx)
    bad = []
    for r in rep.gate_results:
        # 真跑过 = 有显式 dispatcher 分支或非 pass_result 语义（passed=False 或 skipped）
        # 静默假通过 = passed=True 且 skipped=False 且 evaluate 只是 pass_result 兜底
        if r.gate_id in _dispatcher_branches():
            continue
        if r.skipped:
            continue
        if not r.passed:
            continue
        # 到达这里：不在 dispatcher、未 skipped、却 passed=True → 检查是否 auto-bind 真跑
        # （auto-bind 成功会返回真结果；无法静态区分，交由单测 4 验证具体门禁）
        bad.append(r.gate_id)
    return bad


# ─────────────────────────────────────────────
# 1. registry 覆盖：每门禁必须有 dispatcher 分支或跨章声明
# ─────────────────────────────────────────────

def test_every_registry_gate_is_dispatched_or_cross_chapter():
    dispatched = _dispatcher_branches()
    declared = set(STRUCTURAL_GATE_REQUIREMENTS.keys())
    unaccounted = [g for g in registry_gate_ids() if g not in dispatched and g not in declared]
    assert unaccounted == [], f"registry 有而 dispatcher 无、且未声明跨章的门禁: {unaccounted}"


def test_all_structural_declarations_exist_in_registry():
    unknown = [g for g in STRUCTURAL_GATE_REQUIREMENTS if g not in GATE_CATALOG]
    assert unknown == [], f"STRUCTURAL_GATE_REQUIREMENTS 声明了不存在的门禁: {unknown}"


# ─────────────────────────────────────────────
# 2. 跨章专用门禁单章显式 SKIPPED（不假通过）
# ─────────────────────────────────────────────

def test_cross_chapter_gates_skipped_in_single_chapter():
    p = AuditPipeline()
    ctx = p._enrich_context({"text": "第一章：陈默走进工坊，夜风裹着冷却液的气味。他把水晶接入读数仪。", "chapter_index": 0})
    rep = p.run_full(ctx)
    results = {r.gate_id: r for r in rep.gate_results}
    for gid in ["STC-01", "STC-22", "RVI-06"]:
        r = results.get(gid)
        assert r is not None, f"{gid} 未出现在 run_full 结果中"
        assert r.skipped is True, f"{gid} 在单章应显式 SKIPPED，实际 skipped={r.skipped} passed={r.passed}"


# ─────────────────────────────────────────────
# 3. 跨章路径提供 style_baseline → STC 死门禁可被激活真跑
# ─────────────────────────────────────────────

def test_stc_activated_when_style_baseline_provided():
    p = AuditPipeline()
    ctx = p._enrich_context({"text": "第一章：陈默非常快地走进工坊。", "chapter_index": 0})
    ctx["style_baseline"] = {
        "adverb_density": 0.05,
        "baseline_adverb_mean": 0.01,
        "baseline_adverb_std": 0.005,
    }
    rep = p.run_full(ctx)
    r = next(x for x in rep.gate_results if x.gate_id == "STC-01")
    assert r.skipped is False, "提供 style_baseline 后 STC-01 不应 SKIPPED"
    assert r.passed is False, "副词密度 Z=4.0 应检出漂移（failed）"


# ─────────────────────────────────────────────
# 4. 单章 run_full 无静默假通过
# ─────────────────────────────────────────────

def test_no_silent_pass_in_single_chapter():
    bad = _no_silent_pass()
    assert bad == [], f"静默假通过的门禁（registry有/dispatcher无/未SKIP/passed=True）: {bad}"


# ─────────────────────────────────────────────
# 5. auto_bind 对缺必要参数返回 SKIPPED、对全参真跑
# ─────────────────────────────────────────────

def test_auto_bind_missing_required_returns_skipped():
    from wenjian.audit.gates import get_gate

    gate = get_gate("SVT-01")  # 必填 entry_value/exit_value
    res = _auto_bind_evaluate(gate, {"chapter_text": "测试"})
    assert res.skipped is True
    assert res.passed is True


def test_auto_bind_full_params_evaluates():
    from wenjian.audit.gates import get_gate

    gate = get_gate("SVT-01")
    res = _auto_bind_evaluate(gate, {"entry_value": "生", "exit_value": "死"})
    assert res.skipped is False
    assert res.passed is True  # 生→死 是合法价值翻转
