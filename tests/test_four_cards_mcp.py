"""
四卡 MCP 后端接入测试（FOUR_CARD_PLAN 里程碑5）
直调 mcp_server_fast 暴露的 2 个工具（FastMCP 装饰保留原函数签名）。
Run: python -X utf8 -m pytest tests/test_four_cards_mcp.py -v
"""

import asyncio

import pytest
from pydantic import ValidationError

import mcp_server_fast as server
from mcp_server_fast import AssembleFromSampleInput, EditFourCardsInput

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


class TestAssembleTool:
    def test_assemble_from_sample_story(self):
        r = run(server.assemble_from_sample_story(AssembleFromSampleInput(text=SAMPLE_500)))
        p = r["project"]
        assert r["summary"]["anchored"] is True
        assert len(p["biographies"]) >= 1
        bio = p["biographies"][0]
        assert bio["name"] and bio["want"] and bio["lie"]
        assert len(p["framework"]) >= 3
        assert len(p["chapters"]) >= 1
        assert p["sample"]["text"] == SAMPLE_500
        assert p["sample"]["transportation_score"] > 0

    def test_assemble_rejects_short_text(self):
        with pytest.raises(ValidationError):
            run(server.assemble_from_sample_story(AssembleFromSampleInput(text="短")))


class TestEditTool:
    def _assemble(self):
        r = run(server.assemble_from_sample_story(AssembleFromSampleInput(text=SAMPLE_500)))
        return r["project"]

    def test_edit_lie_produces_fanout_and_rulings(self):
        p = self._assemble()
        r1 = run(
            server.edit_four_cards(
                EditFourCardsInput(
                    project=p,
                    edit={
                        "card": "biographies",
                        "index": 0,
                        "field": "lie",
                        "before": p["biographies"][0]["lie"],
                        "after": "交出真心的人才会被记住",
                    },
                )
            )
        )
        diffs = r1["diffs"]
        targets = {d["target_card"] for d in diffs}
        assert {"framework", "chapters", "sample"} <= targets
        assert r1["pending"] == len(diffs)

        # 第二轮：携带上一轮 project（内含 pending diffs）裁决接受其一
        target_id = diffs[0]["id"]
        r2 = run(
            server.edit_four_cards(
                EditFourCardsInput(
                    project=r1["project"],
                    edit={
                        "card": "biographies",
                        "index": 0,
                        "field": "lie",
                        "before": "x",
                        "after": "y",
                    },
                    decisions=[{"id": target_id, "action": "accept"}],
                )
            )
        )
        pending = {d["id"]: d["status"] for d in r2["project"]["pending_diffs"]}
        assert pending[target_id] == "accepted"
        # 其余新批 diff 仍是 pending
        new_ids = [d["id"] for d in r2["diffs"]]
        assert all(pending[i] == "pending" for i in new_ids)

    def test_edit_unknown_card_returns_empty(self):
        p = self._assemble()
        r = run(
            server.edit_four_cards(
                EditFourCardsInput(
                    project=p,
                    edit={"card": "nope", "field": "x", "before": "", "after": "y"},
                )
            )
        )
        assert r["diffs"] == [] and r["pending"] == 0


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "-s"])
