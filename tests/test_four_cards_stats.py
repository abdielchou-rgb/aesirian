"""P3-12 (2026-09-07): diff 决策埋点 + provenance 统计。

深度审计 P3-12：四卡提案制缺少"作者决策遥测"——diff 接受/拒绝率无法可查，
无法回答"作者是否信任 AI 提案 / 哪些来源卡的建议被拒绝最多"，周级门禁调参
只能靠感觉。

修复：
- core/diff_engine.py：进程内 append-only 决策日志（_record_decision in apply_diff）
  + decision_stats() 聚合（accept/reject 率、来源卡/去向卡/字段分布）；线程安全、
  上限 5000 条，不落库（轻量遥测）；reset_decision_log() 供测试。
- mcp_server_fast.py：新增 four_cards_stats MCP 工具暴露统计。
- pwa/four_cards.html：renderDiffs 展示已裁决 provenance（来源→去向 + ✓/✗），
  新增"决策统计"按钮调用 four_cards_stats。

本测试验证：裁决被记录、统计聚合正确、reset 干净、MCP 工具可调。

Run: python -X utf8 -m pytest tests/test_four_cards_stats.py -v
"""
import asyncio

import mcp_server_fast as server
from core.diff_engine import (
    apply_diff,
    decision_stats,
    reset_decision_log,
)
from core.four_cards import FourCardProject
from mcp_server_fast import EditFourCardsInput

SAMPLE_500 = (
    "当铺学徒沈砚在雨夜发现账本夹层里有一张泛黄的当票，当的是一把带血的短刀，"
    "当主签名是他失踪七年的父亲。他想要夺回家族当铺，那是父亲被诬陷前留给他的唯一念想。"
    "那年冬天父亲被至亲当众押走，他七岁，站在人群外喊不出声。从此他相信，"
    "对人交心等于死于背叛，夜里他总把短刀压在枕头下。"
    "如今他找到那把刀，刀柄刻着舅舅的名字。他握着刀，站在舅舅面前，"
    "忽然想起自己答应过要守护这家当铺。他把刀递了过去，说，我还你，但你欠我一句实话。"
    "舅舅没有接刀，却跪了下来。窗外雨声渐小，沈砚第一次觉得胸口那道旧伤，"
    "好像没那么疼了。"
)


def run(coro):
    return asyncio.run(coro)


def _assemble_project() -> dict:
    from mcp_server_fast import AssembleFromSampleInput

    r = run(server.assemble_from_sample_story(AssembleFromSampleInput(text=SAMPLE_500)))
    return r["project"]


def _mk_diffs(project: dict) -> dict:
    """触发一次锚级编辑产生 fanout diffs，返回 edit_four_cards 结果。"""
    return run(
        server.edit_four_cards(
            EditFourCardsInput(
                project=project,
                edit={
                    "card": "biographies",
                    "index": 0,
                    "field": "lie",
                    "before": project["biographies"][0]["lie"],
                    "after": "交出真心的人才会被记住",
                },
            )
        )
    )


def _reset():
    reset_decision_log()


def test_accept_and_reject_are_recorded():
    _reset()
    p = _assemble_project()
    r = _mk_diffs(p)
    diffs = r["diffs"]
    assert len(diffs) >= 2

    # 接受第一个、拒绝第二个
    accept_id, reject_id = diffs[0]["id"], diffs[1]["id"]
    run(
        server.edit_four_cards(
            EditFourCardsInput(
                project=r["project"],
                edit={"card": "biographies", "index": 0, "field": "lie", "before": "", "after": ""},
                decisions=[
                    {"id": accept_id, "action": "accept"},
                    {"id": reject_id, "action": "reject"},
                ],
            )
        )
    )
    st = decision_stats()
    assert st["total"] == 2
    assert st["accept"] == 1 and st["reject"] == 1
    assert st["accept_rate"] == 0.5
    # 来源/去向有记录
    assert st["by_source_card"].get("biographies") == 2
    assert len(st["by_target_card"]) >= 1


def test_stats_empty_after_reset():
    _reset()
    st = decision_stats()
    assert st["total"] == 0
    assert st["accept_rate"] is None


def test_apply_diff_records_directly():
    _reset()
    p = FourCardProject.model_validate(_assemble_project())
    r = _mk_diffs(p.model_dump())
    # 用 edit_four_cards 返回的 project（内含 pending diffs）做直接裁决
    edited_project = FourCardProject.model_validate(r["project"])
    pid = r["diffs"][0]["id"]
    ok = apply_diff(edited_project, pid, accept=True)
    assert ok is True
    st = decision_stats()
    assert st["total"] == 1 and st["accept"] == 1


def test_mcp_four_cards_stats_tool_available():
    _reset()
    p = _assemble_project()
    r = _mk_diffs(p)
    run(
        server.edit_four_cards(
            EditFourCardsInput(
                project=r["project"],
                edit={"card": "biographies", "index": 0, "field": "lie", "before": "", "after": ""},
                decisions=[{"id": r["diffs"][0]["id"], "action": "accept"}],
            )
        )
    )
    out = run(server.four_cards_stats(server.FourCardsStatsInput()))
    assert out["total"] >= 1
    assert "accept_rate" in out
    _reset()  # 测试收尾清空，避免污染其他用例


def test_provenance_fields_in_diff_payload():
    """diff 载荷含 provenance 字段（source_card/target_card/field/status）。"""
    _reset()
    p = _assemble_project()
    r = _mk_diffs(p)
    for d in r["diffs"]:
        assert d["source_card"] == "biographies"
        assert d["target_card"] in {"framework", "chapters", "sample"}
        assert d["status"] == "pending"
        assert "rationale" in d
