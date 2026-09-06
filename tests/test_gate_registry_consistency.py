"""P0-1 门禁单一真源一致性测试（2026-09-07 审计修复）。

背景：README「145+」/ user-guide「166」/ api docstring「166」/ attribution「167」/
mcp docstring「167」各自手写数字，无一处可从 registry 推导 → 数字漂移不可核验。

修复后的铁律：
1. `wenjian.audit.gates.GATE_CATALOG` 是唯一真源（total=167, blocking=23）。
2. 设计稿基线 145（V2）+ STC 风格一致性 22 = registry 167，关系由常量显式表达。
3. 本文档与 README/user-guide/attribution 中出现的"门禁总数"必须 == registry。
   若 registry 演进（加/删门禁），此处断言会红，提醒同步文档——禁止手写漂移。

Run: python -X utf8 -m pytest tests/test_gate_registry_consistency.py -v
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root (bridge/core 等)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))  # wenjian 包在 core/ 下

from wenjian.audit.gates import (  # noqa: E402
    BLOCKING_TOTAL,
    DESIGN_BASELINE_V2,
    GATE_CATALOG,
    GATE_FAMILIES,
    GATE_TOTAL,
    STYLE_CONSISTENCY_INCREMENT,
    gate_registry_stats,
)

ROOT = Path(__file__).resolve().parents[1]


# ─────────────────────────────────────────────
# 1. registry 自身一致性
# ─────────────────────────────────────────────

def test_registry_total_and_baseline_relation():
    """145（V2 基线）+ 22（STC 风格一致性）= registry 167。"""
    assert GATE_TOTAL == len(GATE_CATALOG) == 167
    assert DESIGN_BASELINE_V2 + STYLE_CONSISTENCY_INCREMENT == GATE_TOTAL
    # STC 族确有 22 道
    assert GATE_FAMILIES.get("STC") == 22


def test_registry_stats_shape():
    stats = gate_registry_stats()
    assert stats["total"] == GATE_TOTAL
    assert stats["blocking"] == BLOCKING_TOTAL
    assert stats["blocking"] == 23
    assert stats["by_severity"]["block"] == BLOCKING_TOTAL
    # 每门禁都有 params schema（供 dispatcher/文档派生，禁止空 catalog 项）
    assert all("params" in m and isinstance(m["params"], list) for m in GATE_CATALOG.values())
    assert all("severity" in m for m in GATE_CATALOG.values())


def test_registry_has_no_duplicate_gate_ids():
    ids = [m["gate_id"] for m in GATE_CATALOG.values()]
    assert len(ids) == len(set(ids))
    assert all(gid in GATE_CATALOG for gid in ids)


# ─────────────────────────────────────────────
# 2. 文档数字 == registry（防手写漂移）
# ─────────────────────────────────────────────

DOC_NUMBER_PATTERN = re.compile(r"(\d{3})\s*道?门禁|\b(\d{3})-gate\b")


def _doc_gate_numbers(path: Path) -> set[int]:
    """提取文档/源码注释中形如 '167 道门禁' / '167-gate' 的数字。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    nums: set[int] = set()
    for m in DOC_NUMBER_PATTERN.finditer(text):
        num = int(m.group(1) or m.group(2))
        nums.add(num)
    return nums


@pytest.mark.parametrize(
    "rel_path",
    [
        "README.md",
        "docs/user-guide.md",
        "docs/attribution.md",
    ],
)
def test_docs_gate_count_equals_registry(rel_path):
    """公开文档中凡是写『NNN 道门禁』/『NNN-gate』，NNN 必须 == registry total。"""
    p = ROOT / rel_path
    if not p.exists():
        pytest.skip(f"{rel_path} not present")
    nums = _doc_gate_numbers(p)
    # 允许完全不提数字（空集合）；一旦提了就必须是 167。
    assert all(n == GATE_TOTAL for n in nums), (
        f"{rel_path} 门禁数字 {sorted(nums)} 与 registry({GATE_TOTAL}) 不一致——"
        f"请改为引用单一真源，禁止手写漂移数字。"
    )


def test_api_docstring_no_hardcoded_gate_count():
    """api_server /audit docstring 不得再硬编码门禁总数（实际只跑 G1-G5+G6-G10 链路）。"""
    text = (ROOT / "bridge" / "api_server.py").read_text(encoding="utf-8")
    # 允许 145 仅作为 registry 常量名（不出现裸 '145门禁' 文案）
    assert "166门禁" not in text and "166 门禁" not in text
    assert "167门禁" not in text and "167 门禁" not in text


def test_mcp_docstring_no_hardcoded_gate_count():
    """mcp analyze_chapter docstring 不得再写死 '167-gate'（registry 驱动）。"""
    text = (ROOT / "mcp_server_fast.py").read_text(encoding="utf-8")
    assert "167-gate" not in text
    assert "registry-driven" in text or "GATE_CATALOG" in text


def test_frontend_no_hardcoded_gate_count():
    """dashboard.html 不再向用户传播无法核验的 '166 道门禁' 文案。"""
    for rel in ["electron_ide/public/dashboard.html", "electron_ide/public/review.html"]:
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        assert "166 道门禁" not in text and "含166道门禁" not in text


def test_methodology_marks_design_baseline():
    """文鉴方法论文稿须标注 145 为 V2 设计基线（避免被误读为当前数量）。"""
    p = ROOT / "core" / "craft" / "wenjian-methodology-v2.md"
    text = p.read_text(encoding="utf-8", errors="replace")
    assert "V2 设计基线" in text or "设计基线" in text
    assert "GATE_CATALOG" in text or "单一真源" in text
