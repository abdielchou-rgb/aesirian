"""P0-3 (2026-09-07): 一致性桥 — CSN 数值矛盾检测。

背景（深度审计 S1.2.1.3 + docs/internal/gate-verification-report.md §5）：
时间/空间/身份/事实类矛盾 0/12 检出。根因之一：正则 EntityExtractor 对中文
数词数值事实（"修了十一年"）提取为空 → 跨章一致性 facts 为空 → 矛盾无法比对。

修复：core/csn_consistency.py 提供中文数词归一化 + 保守数值事实扫描 +
跨章数值矛盾比对；orchestrator.check_cross_chapter_consistency 新增第 4 类
检测 csn_numeric_contradiction；submit_chapter/audit_draft 的 G6-G10 用真实
reader_context（不再硬编码 0 值，G8 认知负荷恢复可测）。

Run: python -X utf8 -m pytest tests/test_csn_consistency.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from csn_consistency import (  # noqa: E402
    chinese_numeral_to_int,
    find_cross_chapter_numeric_conflicts,
    scan_numeric_facts,
)

# ─────────────────────────────────────────────
# 1. 中文数词归一化
# ─────────────────────────────────────────────

def test_chinese_numeral_basics():
    assert chinese_numeral_to_int("十一") == 11
    assert chinese_numeral_to_int("二十一") == 21
    assert chinese_numeral_to_int("三十") == 30
    assert chinese_numeral_to_int("四十五") == 45
    assert chinese_numeral_to_int("一百") == 100
    assert chinese_numeral_to_int("9") == 9
    assert chinese_numeral_to_int("零") == 0
    assert chinese_numeral_to_int("abc") is None


# ─────────────────────────────────────────────
# 2. 单章数值事实扫描
# ─────────────────────────────────────────────

def test_scan_duration_and_age():
    facts = scan_numeric_facts("陈默修了十一年罪忆水晶。")
    assert any(f.subject == "陈默" and f.predicate == "时长" and f.value == 11 for f in facts)

    facts2 = scan_numeric_facts("陈默今年三十岁。")
    assert any(f.subject == "陈默" and f.predicate == "年龄" and f.value == 30 for f in facts2)


def test_scan_rejects_modifier_and_org():
    # "曹渊的女儿今年八岁"——"的女儿"是修饰关系，不是独立人名
    assert scan_numeric_facts("曹渊的女儿今年八岁。") == []
    # "安全局在…待了九年"——机构名不作人物 subject
    assert scan_numeric_facts("安全局在洛阳待了九年。") == []


def test_scan_rejects_clean_prose():
    for t in [
        "洛阳星港的夜空很安静。",
        "他把水晶推回去，说这不是价格的问题。",
        "他修了十一年水晶。",  # 代词"他"非汉字姓名，不匹配
    ]:
        assert scan_numeric_facts(t) == [], f"应无事实：{t}"


# ─────────────────────────────────────────────
# 3. 跨章数值矛盾比对
# ─────────────────────────────────────────────

def test_cross_chapter_detects_duration_contradiction():
    conflicts = find_cross_chapter_numeric_conflicts(
        "第二章：陈默修了二十一年罪忆水晶。",
        [(1, "第一章：陈默修了十一年罪忆水晶。")],
    )
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c["type"] == "csn_numeric_contradiction"
    assert c["severity"] == "BLOCK"
    assert c["subject"] == "陈默"
    assert c["before"] == "11年" and c["after"] == "21年"


def test_cross_chapter_no_false_positive_same_value():
    conflicts = find_cross_chapter_numeric_conflicts(
        "第二章：陈默依然修了十一年水晶。",
        [(1, "第一章：陈默修了十一年罪忆水晶。")],
    )
    assert conflicts == []


def test_cross_chapter_empty_on_clean():
    assert find_cross_chapter_numeric_conflicts(
        "第二章：窗外雨声渐大。", [(1, "第一章：他走进工坊。")]
    ) == []
