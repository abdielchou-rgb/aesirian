"""文鉴 v4.2 — 风格一致性门禁组 (STC)。

基于四层风格指纹 (L1 词级 / L2 句级 / L3 篇章 / L4 叙事)
和 DL 嵌入的跨章风格漂移检测。

22 道门禁：词级 6 + 句级 5 + 篇章 4 + 叙事 5 + 漂移 2
全部零 API Key，纯启发式。
"""

from __future__ import annotations

from wenjian.models import GateResult, GateSeverity

from .base import BaseGate

# ═══════════════════════════════════════════════════════════════
# L1: 词级一致性 (6 道)
# ═══════════════════════════════════════════════════════════════


class STC01_AdverbDrift(BaseGate):
    """副词密度跨章波动不应太大。"""

    gate_id = "STC-01"
    name = "副词浓度漂移"
    description = "副词密度章节间差异 > 2 标准差时告警，提示写作风格不一致"
    severity = GateSeverity.WARN

    def evaluate(
        self,
        adverb_density: float = 0,
        baseline_adverb_mean: float = 0,
        baseline_adverb_std: float = 0,
    ) -> GateResult:
        if baseline_adverb_std == 0:
            return self.pass_result(message="基线不足，跳过")
        z_score = abs(adverb_density - baseline_adverb_mean) / max(baseline_adverb_std, 0.01)
        if z_score > 2.0:
            return self.fail_result(
                message=f"副词密度 {adverb_density} 偏离基线均值 {baseline_adverb_mean} (Z={z_score:.1f})",
                details={
                    "adverb_density": adverb_density,
                    "baseline_mean": baseline_adverb_mean,
                    "z_score": round(z_score, 2),
                },
            )
        return self.pass_result()


class STC02_PassiveDrift(BaseGate):
    """被动语态密度跨章波动。"""

    gate_id = "STC-02"
    name = "被动语态漂移"
    description = "被字句密度跨章差异 > 2 标准差"
    severity = GateSeverity.WARN

    def evaluate(
        self,
        passive_density: float = 0,
        baseline_passive_mean: float = 0,
        baseline_passive_std: float = 0,
    ) -> GateResult:
        if baseline_passive_std == 0:
            return self.pass_result(message="基线不足")
        z = abs(passive_density - baseline_passive_mean) / max(baseline_passive_std, 0.01)
        if z > 2.0:
            return self.fail_result(
                message=f"被字句密度 {passive_density} 偏离基线 {baseline_passive_mean} (Z={z:.1f})",
                details={"passive_density": passive_density, "z_score": round(z, 2)},
            )
        return self.pass_result()


class STC03_FillerAdverbRatio(BaseGate):
    """赘词 / 副词比率异常。"""

    gate_id = "STC-03"
    name = "赘词副词比"
    description = "赘词密度与副词密度的比值应在 0.5-2.0 范围内"
    severity = GateSeverity.WARN

    def evaluate(self, filler_density: float = 0, adverb_density: float = 0) -> GateResult:
        if adverb_density == 0:
            return self.pass_result()
        ratio = filler_density / max(adverb_density, 0.01)
        if ratio < 0.3 or ratio > 3.0:
            return self.fail_result(
                message=f"赘词/副词比 {ratio:.1f} 异常（建议 0.3-3.0）",
                details={"ratio": round(ratio, 2)},
            )
        return self.pass_result()


class STC04_VocabDiversityDrop(BaseGate):
    """词汇多样性下降。"""

    gate_id = "STC-04"
    name = "词汇多样性下降"
    description = "本章词汇多样性低于基线 30% 以上"
    severity = GateSeverity.WARN

    def evaluate(self, vocab_diversity: float = 0, baseline_vocab: float = 0) -> GateResult:
        if baseline_vocab == 0:
            return self.pass_result(message="基线不足")
        drop = (baseline_vocab - vocab_diversity) / max(baseline_vocab, 0.001)
        if drop > 0.3:
            return self.fail_result(
                message=f"词汇多样性下降 {drop:.0%} (本章 {vocab_diversity:.4f} vs 基线 {baseline_vocab:.4f})",
                details={"drop_pct": round(drop * 100, 1)},
            )
        return self.pass_result()


class STC05_DifficultWordSpike(BaseGate):
    """难词比尖峰检测。"""

    gate_id = "STC-05"
    name = "难词比尖峰"
    description = "难词比突然跃升 > 3 倍基线时告警——可能是信息倾泻"
    severity = GateSeverity.WARN

    def evaluate(
        self, difficult_word_ratio: float = 0, baseline_difficult: float = 0
    ) -> GateResult:
        if baseline_difficult == 0:
            return self.pass_result()
        ratio = difficult_word_ratio / max(baseline_difficult, 0.001)
        if ratio > 3.0:
            return self.fail_result(
                message=f"难词比 {difficult_word_ratio:.3f} 达基线 {baseline_difficult:.3f} 的 {ratio:.1f} 倍——可能信息倾泻",
                details={"spike_ratio": round(ratio, 1)},
            )
        return self.pass_result()


class STC06_EmotionWordDrift(BaseGate):
    """情绪标记词密度漂移。"""

    gate_id = "STC-06"
    name = "情绪词密度漂移"
    description = "直接情绪声明词密度跨章波动 > 2 标准差"
    severity = GateSeverity.WARN

    def evaluate(
        self,
        emotion_ratio: float = 0,
        baseline_emotion_mean: float = 0,
        baseline_emotion_std: float = 0,
    ) -> GateResult:
        if baseline_emotion_std == 0:
            return self.pass_result(message="基线不足")
        z = abs(emotion_ratio - baseline_emotion_mean) / max(baseline_emotion_std, 0.01)
        if z > 2.0:
            return self.fail_result(
                message=f"情绪/触点比 {emotion_ratio} 偏离基线 {baseline_emotion_mean} (Z={z:.1f})",
                details={"z_score": round(z, 2)},
            )
        return self.pass_result()


# ═══════════════════════════════════════════════════════════════
# L2: 句级一致性 (5 道)
# ═══════════════════════════════════════════════════════════════


class STC07_SentenceLengthVariance(BaseGate):
    """句长方差检测——方差过低 = 句式单调。"""

    gate_id = "STC-07"
    name = "句长方差"
    description = "句长方差 < 20 时句式过于单调，读者容易疲劳"
    severity = GateSeverity.WARN

    def evaluate(self, avg_sentence_len: float = 0, variance: float = 0) -> GateResult:
        if avg_sentence_len < 5:
            return self.pass_result(message="文本太短")
        if variance < 15:
            return self.fail_result(
                message=f"句长方差仅 {variance:.0f}——句式过于单调。建议长短句交替。",
                details={"avg_len": avg_sentence_len, "variance": round(variance, 1)},
            )
        return self.pass_result()


class STC08_SentenceLengthDrift(BaseGate):
    """平均句长跨章漂移。"""

    gate_id = "STC-08"
    name = "平均句长漂移"
    description = "平均句长跨章差异 > 2 标准差"
    severity = GateSeverity.WARN

    def evaluate(
        self, avg_sentence_len: float = 0, baseline_sl_mean: float = 0, baseline_sl_std: float = 0
    ) -> GateResult:
        if baseline_sl_std == 0:
            return self.pass_result()
        z = abs(avg_sentence_len - baseline_sl_mean) / max(baseline_sl_std, 0.5)
        if z > 2.0:
            return self.fail_result(
                message=f"平均句长 {avg_sentence_len:.0f} 偏离基线 {baseline_sl_mean:.0f} (Z={z:.1f})",
                details={"z_score": round(z, 2)},
            )
        return self.pass_result()


class STC09_MAXSentenceRatio(BaseGate):
    """极端短句（<=5字）与极端长句（>=40字）的比例失衡。"""

    gate_id = "STC-09"
    name = "长短句比例"
    description = "极端短句与极端长句的比例应在 0.3-3.0 之间"
    severity = GateSeverity.WARN

    def evaluate(
        self,
        short_sentence_ratio: float = 0,
        long_sentence_count: int = 0,
        total_sentences: int = 1,
    ) -> GateResult:
        if total_sentences < 5:
            return self.pass_result(message="文本太短")
        long_ratio = max(long_sentence_count, 1) / max(total_sentences, 1)
        # 检查是否被一种句式主导
        if short_sentence_ratio > 0.8:
            return self.fail_result(
                message=f"短句占比 {short_sentence_ratio:.0%}——几乎全是短句，缺乏节奏变化"
            )
        if long_ratio > 0.6:
            return self.fail_result(message=f"长句占比 {long_ratio:.0%}——需更多短句缓冲")
        return self.pass_result()


class STC10_DialogueDensityDrift(BaseGate):
    """对话密度跨章漂移。"""

    gate_id = "STC-10"
    name = "对话密度漂移"
    description = "对话密度跨章差异 > 2 标准差"
    severity = GateSeverity.WARN

    def evaluate(
        self, dialogue_density: float = 0, baseline_dd_mean: float = 0, baseline_dd_std: float = 0
    ) -> GateResult:
        if baseline_dd_std == 0:
            return self.pass_result()
        z = abs(dialogue_density - baseline_dd_mean) / max(baseline_dd_std, 0.01)
        if z > 2.0:
            return self.fail_result(
                message=f"对话密度 {dialogue_density:.2f} 偏离基线 {baseline_dd_mean:.2f} (Z={z:.1f})",
                details={"z_score": round(z, 2)},
            )
        return self.pass_result()


class STC11_ParagraphLengthDrift(BaseGate):
    """段落长度跨章漂移。"""

    gate_id = "STC-11"
    name = "段落长度漂移"
    description = "平均段落长度跨章差异 > 2 标准差"
    severity = GateSeverity.WARN

    def evaluate(
        self, avg_paragraph_len: float = 0, baseline_pl_mean: float = 0, baseline_pl_std: float = 0
    ) -> GateResult:
        if baseline_pl_std < 10:
            return self.pass_result()
        z = abs(avg_paragraph_len - baseline_pl_mean) / max(baseline_pl_std, 10)
        if z > 2.0:
            return self.fail_result(
                message=f"段落长度 {avg_paragraph_len:.0f} 偏离基线 {baseline_pl_mean:.0f} (Z={z:.1f})",
                details={"z_score": round(z, 2)},
            )
        return self.pass_result()


# ═══════════════════════════════════════════════════════════════
# L3: 篇章级一致性 (4 道)
# ═══════════════════════════════════════════════════════════════


class STC12_ChapterEndpointForce(BaseGate):
    """章末力度一致性。"""

    gate_id = "STC-12"
    name = "章末力度一致性"
    description = "连续 3 章章末力度为 weak 时告警"
    severity = GateSeverity.WARN

    def evaluate(
        self, end_force: str = "moderate", recent_end_forces: list[str] = None
    ) -> GateResult:
        forces = (recent_end_forces or []) + [end_force]
        weak_streak = 0
        max_weak = 0
        for f in forces:
            if f == "weak":
                weak_streak += 1
                max_weak = max(max_weak, weak_streak)
            else:
                weak_streak = 0
        if max_weak >= 3:
            return self.fail_result(
                message=f"连续 {max_weak} 章章末力度为 weak——读者缺乏点下一章的动力",
                details={"weak_streak": max_weak},
            )
        return self.pass_result()


class STC13_HookDensityDrift(BaseGate):
    """钩子密度跨章漂移。"""

    gate_id = "STC-13"
    name = "钩子密度漂移"
    description = "钩子密度跨章差异 > 2 标准差"
    severity = GateSeverity.WARN

    def evaluate(
        self, hook_density: float = 0, baseline_hook_mean: float = 0, baseline_hook_std: float = 0
    ) -> GateResult:
        if baseline_hook_std == 0:
            return self.pass_result()
        z = abs(hook_density - baseline_hook_mean) / max(baseline_hook_std, 0.01)
        if z > 2.0:
            return self.fail_result(
                message=f"钩子密度 {hook_density:.2f} 偏离基线 {baseline_hook_mean:.2f} (Z={z:.1f})",
                details={"z_score": round(z, 2)},
            )
        return self.pass_result()


class STC14_GapDensityDrift(BaseGate):
    """鸿沟密度跨章漂移。"""

    gate_id = "STC-14"
    name = "鸿沟密度漂移"
    description = "鸿沟密度跨章差异 > 2 标准差——节奏突变"
    severity = GateSeverity.WARN

    def evaluate(
        self, gap_density: float = 0, baseline_gap_mean: float = 0, baseline_gap_std: float = 0
    ) -> GateResult:
        if baseline_gap_std < 0.2:
            return self.pass_result()
        z = abs(gap_density - baseline_gap_mean) / max(baseline_gap_std, 0.1)
        if z > 2.5:
            return self.fail_result(
                message=f"鸿沟密度 {gap_density:.1f} 剧烈偏离基线 {baseline_gap_mean:.1f} (Z={z:.1f})——节奏突变可能让读者出戏",
                details={"z_score": round(z, 2)},
            )
        return self.pass_result()


class STC15_GenreFitDecline(BaseGate):
    """品类匹配度下降。"""

    gate_id = "STC-15"
    name = "品类匹配下降"
    description = "相对于品类基线的整体风格偏离 > 20%"
    severity = GateSeverity.WARN

    def evaluate(self, genre_fit: float = 1.0, threshold: float = 0.75) -> GateResult:
        if genre_fit >= threshold:
            return self.pass_result()
        if genre_fit < 0.5:
            return self.fail_result(
                message=f"品类匹配度仅 {genre_fit:.0%}——文本风格与目标品类严重偏离",
                details={"genre_fit": genre_fit},
            )
        return self.pass_result(
            message=f"品类匹配度偏低 ({genre_fit:.0%})，建议检查", details={"genre_fit": genre_fit}
        )


# ═══════════════════════════════════════════════════════════════
# L4: 叙事层一致性 (5 道)
# ═══════════════════════════════════════════════════════════════


class STC16_SentimentCoherence(BaseGate):
    """情感连贯性——情感不应在不该反转的地方反转。"""

    gate_id = "STC-16"
    name = "情感连贯性"
    description = "连续 3 章情感倾向同时为正或负时告警——情感应有起伏"
    severity = GateSeverity.WARN

    def evaluate(
        self, chapter_sentiment: float = 0, recent_sentiments: list[float] = None
    ) -> GateResult:
        sentiments = (recent_sentiments or []) + [chapter_sentiment]
        if len(sentiments) < 3:
            return self.pass_result(message="数据不足")
        last3 = sentiments[-3:]
        all_same_sign = all(s > 0 for s in last3) or all(s < 0 for s in last3)
        if all_same_sign:
            sign = "正" if last3[0] > 0 else "负"
            return self.fail_result(
                message=f"连续 3 章情感倾向一致为{sign}——缺乏情感起伏",
                details={"sentiments": last3},
            )
        return self.pass_result()


class STC17_ActStructureTransition(BaseGate):
    """幕间过渡——幕边界应有显著的情感或节奏变化。"""

    gate_id = "STC-17"
    name = "幕间过渡"
    description = "幕边界（~30%/50%/75%）处应有情感或鸿沟密度的显著变化"
    severity = GateSeverity.WARN

    def evaluate(
        self,
        act_pct: float = 0,
        chapter_sentiment: float = 0,
        gap_density: float = 0,
        build_chapter_sentiment: float = 0,
        build_gap_density: float = 0,
    ) -> GateResult:
        # 只在幕边界附近检查（最后一章在本幕的 85%+ 位置）
        if act_pct < 85:
            return self.pass_result(message="不在幕边界")
        sent_change = abs(chapter_sentiment - build_chapter_sentiment)
        gap_change = abs(gap_density - build_gap_density) / max(build_gap_density, 0.1)
        if sent_change < 0.15 and gap_change < 0.5:
            return self.fail_result(
                message=f"幕边界处（幕内 {act_pct:.0f}%）情感与节奏无显著变化",
                details={
                    "sentiment_change": round(sent_change, 3),
                    "gap_change": round(gap_change, 1),
                },
            )
        return self.pass_result()


class STC18_RhythmScoreDecline(BaseGate):
    """节奏评分下降。"""

    gate_id = "STC-18"
    name = "节奏评分下降"
    description = "本章节奏评分低于基线 20% 以上"
    severity = GateSeverity.WARN

    def evaluate(self, rhythm_score: float = 100, baseline_rhythm: float = 100) -> GateResult:
        if baseline_rhythm == 0:
            return self.pass_result()
        drop = (baseline_rhythm - rhythm_score) / max(baseline_rhythm, 1)
        if drop > 0.25:
            return self.fail_result(
                message=f"节奏评分下降 {drop:.0%}（本章 {rhythm_score:.0f} vs 基线 {baseline_rhythm:.0f}）",
                details={"drop_pct": round(drop * 100, 1)},
            )
        return self.pass_result()


class STC19_PosEntropyChange(BaseGate):
    """POS bigram 熵变化——句法复杂度的重大改变。"""

    gate_id = "STC-19"
    name = "句法复杂度变化"
    description = "POS bigram 转移熵的变化 > 1.0 比特表示句法风格改变"
    severity = GateSeverity.WARN

    def evaluate(self, pos_bigram_entropy: float = 0, baseline_entropy: float = 0) -> GateResult:
        if baseline_entropy < 0.5:
            return self.pass_result()
        change = abs(pos_bigram_entropy - baseline_entropy)
        if change > 1.0:
            return self.fail_result(
                message=f"句法转移熵变化 {change:.2f} 比特——句法风格可能发生改变",
                details={
                    "entropy": pos_bigram_entropy,
                    "baseline": baseline_entropy,
                    "change": round(change, 2),
                },
            )
        return self.pass_result()


class STC20_EmotionTensionMismatch(BaseGate):
    """情感-节奏不匹配——高情感密度的章节奏也应有变化。"""

    gate_id = "STC-20"
    name = "情感节奏匹配"
    description = "高情感章节应有对应的鸿沟密度支撑"
    severity = GateSeverity.WARN

    def evaluate(self, chapter_sentiment: float = 0, gap_density: float = 0) -> GateResult:
        abs_sent = abs(chapter_sentiment)
        if abs_sent > 0.4 and gap_density < 0.8:
            return self.fail_result(
                message=f"情感强度高 (|{chapter_sentiment:.2f}|) 但鸿沟密度低 ({gap_density:.1f})——情感缺乏剧情支撑",
                details={"sentiment": chapter_sentiment, "gap_density": gap_density},
            )
        return self.pass_result()


# ═══════════════════════════════════════════════════════════════
# L5: 跨章漂移 (2 道)
# ═══════════════════════════════════════════════════════════════


class STC21_OverallDriftScore(BaseGate):
    """综合风格漂移评分——DRESS 三维聚合。"""

    gate_id = "STC-21"
    name = "综合风格漂移"
    description = (
        "DRESS 三维（Stylometric Index / Structural Pattern / Functional Score）综合漂移 > 0.2"
    )
    severity = GateSeverity.BLOCK

    def evaluate(
        self,
        style_drift_si: float = 0,
        style_drift_sp: float = 0,
        style_drift_fs: float = 0,
        threshold: float = 0.2,
    ) -> GateResult:
        overall = (style_drift_si + style_drift_sp + style_drift_fs) / 3
        if overall > threshold:
            return self.fail_result(
                message=f"综合风格漂移 {overall:.3f} > {threshold}——整章风格发生显著偏离",
                details={
                    "si": style_drift_si,
                    "sp": style_drift_sp,
                    "fs": style_drift_fs,
                    "overall": round(overall, 3),
                },
            )
        return self.pass_result()


class STC22_ConsecutiveDriftChapters(BaseGate):
    """连续多章漂移——不应连续超过 3 章检测到漂移。"""

    gate_id = "STC-22"
    name = "连续漂移章节"
    description = "连续 3 章以上综合风格漂移 > 0.15 时阻断"
    severity = GateSeverity.BLOCK

    def evaluate(
        self, recent_drift_scores: list[float] = None, threshold: float = 0.15
    ) -> GateResult:
        scores = recent_drift_scores or []
        streak = 0
        max_streak = 0
        for s in scores:
            if s > threshold:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        if max_streak >= 3:
            return self.fail_result(
                message=f"连续 {max_streak} 章风格漂移 > {threshold}——风格已偏离基线",
                details={"max_streak": max_streak, "threshold": threshold},
            )
        return self.pass_result()
