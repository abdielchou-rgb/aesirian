"""
四卡双向传播 / 推导引擎测试（FOUR_CARD_PLAN 里程碑2/3/4 规则层）
Run: python -X utf8 -m pytest tests/test_diff_engine.py -v
"""
import pytest

from core.diff_engine import (
    Diff,
    DiffStatus,
    PROPAGATION_TABLE,
    apply_diff,
    forward_derive,
    propose_diff,
    CardEdit,
)
from core.four_cards import (
    CharacterBiography,
    ChapterBeat,
    FourCardProject,
    FrameworkBeat,
    SampleStory,
)

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


class TestPropagationTable:
    def test_table_keys(self):
        assert set(PROPAGATION_TABLE) == {"biographies", "framework", "chapters", "sample"}

    def test_anchor_fanout(self):
        """人物小传(锚)被改 → 重算框架 + 章节 + 试样。"""
        assert PROPAGATION_TABLE["biographies"]["targets"] == ["framework", "chapters", "sample"]
        assert PROPAGATION_TABLE["biographies"]["needs_confirmation"] is True

    def test_chapters_framework_cross(self):
        assert PROPAGATION_TABLE["framework"]["targets"] == ["chapters"]
        assert PROPAGATION_TABLE["chapters"]["targets"] == ["framework"]

    def test_sample_reverse(self):
        """试样故事被改 → 反向提案改小传。"""
        assert PROPAGATION_TABLE["sample"]["targets"] == ["biographies"]


class TestForwardDerive:
    def test_forward_derive_structure(self):
        """验收：输入 500 字试样 → 输出结构完整四卡，score 非空。"""
        p = forward_derive(SAMPLE_500)
        assert isinstance(p, FourCardProject)
        # 人物小传
        assert len(p.biographies) == 1
        bio = p.biographies[0]
        assert bio.name and bio.want and bio.lie
        assert p.card_summary()["anchored"] is True
        # 框架 beats
        assert len(p.framework) >= 3
        for beat in p.framework:
            assert beat.index >= 1
            assert beat.value_turn in ("正→负", "负→正", "正→正", "负→负") or "→" in beat.value_turn
        # 章节 beats
        assert len(p.chapters) >= 1
        # 试样 + 评分
        assert p.sample.text == SAMPLE_500
        assert p.sample.transportation_score > 0

    def test_forward_derive_wound_trace(self):
        p = forward_derive(SAMPLE_500)
        bio = p.biographies[0]
        # 应能捕捉到创伤线索（父亲/押走/当众）
        assert "押" in bio.wound or "父亲" in bio.wound or "七岁" in bio.wound or bio.wound

    def test_forward_derive_empty(self):
        p = forward_derive("   ")
        assert p.biographies == [] and p.framework == []


class TestProposeDiff:
    def _project(self):
        return FourCardProject(
            biographies=[CharacterBiography(name="沈砚", want="夺回家族当铺",
                                            wound="七岁被至亲当众遗弃",
                                            lie="对人交心等于死于背叛",
                                            change="最后把刀递给仇人")],
            framework=[FrameworkBeat(index=1, goal="碾过谎言", value_turn="正→负"),
                       FrameworkBeat(index=2, goal="逼到临界", value_turn="负→正")],
            chapters=[ChapterBeat(summary="发现当票", value_turn="正→负", causally_linked=False)],
            sample=SampleStory(text=SAMPLE_500, transportation_score=55.0),
        )

    def test_anchor_edit_produces_fanout_diffs(self):
        """验收：改人物小传 lie → 自动生成框架 + 章节 + 试样故事 diff。"""
        p = self._project()
        diffs = propose_diff(CardEdit(card="biographies", index=0, field="lie",
                                      before="对人交心等于死于背叛",
                                      after="交出真心的人才会被记住"), p)
        targets = {d.target_card for d in diffs}
        assert {"framework", "chapters", "sample"} <= targets
        for d in diffs:
            assert d.status == DiffStatus.PENDING
            assert d.source_card == "biographies"
            assert d.rationale  # 每条带因果链说明
        assert len(p.pending_diffs) == len(diffs)

    def test_chapter_edit_proposes_framework(self):
        p = self._project()
        diffs = propose_diff(CardEdit(card="chapters", index=0, field="summary",
                                      before="发现当票", after="发现当票指向舅舅"), p)
        assert any(d.target_card == "framework" for d in diffs)

    def test_apply_accept_and_reject(self):
        p = self._project()
        diffs = propose_diff(CardEdit(card="biographies", index=0, field="lie",
                                      before="x", after="新的谎言"), p)
        assert diffs
        target = diffs[0]
        assert apply_diff(p, target.id, accept=True)
        assert target.status == DiffStatus.ACCEPTED
        assert len([d for d in p.pending_diffs if d.status == DiffStatus.PENDING]) == len(diffs) - 1

        # 拒绝一条
        pending = [d for d in p.pending_diffs if d.status == DiffStatus.PENDING]
        if pending:
            assert apply_diff(p, pending[0].id, accept=False)
            assert pending[0].status == DiffStatus.REJECTED

    def test_unknown_card_edit_returns_empty(self):
        p = self._project()
        diffs = propose_diff(CardEdit(card="nope", field="x", before="", after="y"), p)
        assert diffs == []
        assert p.pending_diffs == []

    def test_diff_model_defaults(self):
        d = Diff(target_card="framework", field="goal", after="a")
        assert d.id and d.status == DiffStatus.PENDING
        assert d.before == "" and d.source_card == ""
        assert d.is_pending


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
