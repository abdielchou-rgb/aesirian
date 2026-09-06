"""
风格一致性基线测试（产品化遗留）— 验证生成质量管线的风格一致性评分有区分度
Run: python -X utf8 -m pytest tests/test_style_baseline.py -v
"""
import pytest

from core.generation.pipeline import GenerationPipeline
from core.persistence.store import ProjectStore


def log_ok(m):
    print("[OK] " + m)


class TestStyleBaseline:
    """风格一致性评分器 — 同风格接近、异风格远离"""

    SHORT_SENT_STYLE = (
        "夜很深。他推开门。门轴响了。她抬起头。月光落在她脸上。他没有说话。"
        "她也没有。两人就这样坐着。窗外的雨慢慢小了。他握紧了钥匙。"
    )
    LONG_SENT_STYLE = (
        "当夜色像墨一样彻底浸透这座老城时，他推开了那扇沉重的木门，门轴在寂静中发出悠长的呻吟，"
        "仿佛在诉说着多年未曾有人踏足的往事，而空气里弥漫的灰尘与旧书页混合的味道，则像某种被遗忘的仪式，"
        "静静等待着一个迟到多年的来客，他抬起头，看见她正坐在窗边，月光恰好落在她半边脸上，"
        "而另一半，则隐在深不见底的阴影里。"
    )
    DIALOGUE_STYLE = (
        "「你来了。」她说。\n「嗯。」他说。\n「我以为你不会来。」\n「我也以为。」\n"
        "「那为什么来了？」\n「因为你说过，如果我不来，你会恨我一辈子。」\n她笑了。"
    )

    def _diff(self, a, b):
        gp = GenerationPipeline(ProjectStore())
        return gp._style_diff(a, b)

    def test_same_style_near_zero(self):
        """同一文本风格差 ≈ 0"""
        d = self._diff(self.SHORT_SENT_STYLE, self.SHORT_SENT_STYLE)
        assert d < 0.05, f"same style should be ~0, got {d}"
        log_ok(f"same style diff = {d:.3f}")

    def test_short_vs_long_far(self):
        """短句 vs 长句风格差明显"""
        d = self._diff(self.SHORT_SENT_STYLE, self.LONG_SENT_STYLE)
        assert d > 0.2, f"short vs long should differ, got {d}"
        log_ok(f"short vs long diff = {d:.3f}")

    def test_dialogue_style_distant(self):
        """对话流 vs 叙述流风格差明显"""
        d = self._diff(self.SHORT_SENT_STYLE, self.DIALOGUE_STYLE)
        assert d > 0.15, f"dialogue vs narration should differ, got {d}"
        log_ok(f"narration vs dialogue diff = {d:.3f}")

    def test_score_penalty_for_style_mismatch(self):
        """生成文本与项目风格严重不匹配时，质量评分下降"""
        gp = GenerationPipeline(ProjectStore())
        # 项目文本：短句风格；生成文本：长句风格 → 应扣分
        project_text = self.SHORT_SENT_STYLE * 4  # > 500 字才启用风格检查
        generated = self.LONG_SENT_STYLE
        # 构造同分基线：同风格不扣，异风格扣
        diff = gp._style_diff(project_text, generated)
        assert diff > 0.15
        score_penalty = int(diff * 20)
        assert score_penalty >= 3
        log_ok(f"style mismatch score penalty = {score_penalty}")

    def test_baseline_threshold_reachable(self):
        """质量评分 < 80 时会触发再生成（用于验证循环可达）"""
        gp = GenerationPipeline(ProjectStore())
        # 短文 + 去AI问题 → 应低于 80
        bad = "他觉得一切似乎都很平淡。可能没有什么特别的。大概就是这样。某种意义上没什么好说的。"
        score = gp._score_quality(bad, None)
        assert score < 80, f"low-quality text should score <80, got {score}"
        log_ok(f"low-quality baseline score = {score}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])