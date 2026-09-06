"""
四卡数据模型测试（FOUR_CARD_PLAN 里程碑1）
Run: python -X utf8 -m pytest tests/test_four_cards.py -v
"""

import pytest

from core.four_cards import (
    ChapterBeat,
    CharacterBiography,
    FourCardProject,
    FrameworkBeat,
    SampleStory,
)


class TestDataModels:
    def test_biography_defaults(self):
        bio = CharacterBiography()
        assert bio.name == "未命名主角"
        assert bio.want == "" and bio.wound == "" and bio.lie == "" and bio.change == ""
        assert bio.voice_traits == []

    def test_biography_full_roundtrip(self):
        bio = CharacterBiography(
            name="沈砚",
            want="夺回家族当铺",
            wound="七岁被至亲当众遗弃",
            lie="对人交心等于死于背叛",
            change="最后把刀递给仇人",
            voice_traits=["短句克制"],
        )
        d = bio.model_dump()
        bio2 = CharacterBiography.model_validate(d)
        assert bio2.name == "沈砚"
        assert bio2.want == bio.want and bio2.voice_traits == ["短句克制"]

    def test_framework_beat_defaults(self):
        beat = FrameworkBeat()
        assert beat.index == 0
        assert beat.value_turn == "负→正"
        assert beat.tension_source == "目标冲突"

    def test_four_card_project_summary(self):
        p = FourCardProject(
            biographies=[CharacterBiography(name="A", want="w", wound="wd", lie="l")],
            framework=[FrameworkBeat(index=1, goal="g")],
            chapters=[ChapterBeat(summary="s")],
            sample=SampleStory(text="t", transportation_score=62.5),
        )
        s = p.card_summary()
        assert s["biography_count"] == 1
        assert s["framework_beats"] == 1 and s["chapter_beats"] == 1
        assert s["transportation_score"] == 62.5
        assert s["anchored"] is True

    def test_empty_project(self):
        p = FourCardProject.empty()
        assert p.biographies == [] and p.framework == [] and p.chapters == []
        assert p.sample.transportation_score == 0.0
        assert p.pending_diffs == []

    def test_json_roundtrip(self):
        p = FourCardProject.empty()
        p.biographies.append(CharacterBiography(name="B", want="w"))
        j = p.model_dump_json()
        p2 = FourCardProject.model_validate_json(j)
        assert p2.biographies[0].name == "B"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "-s"])
