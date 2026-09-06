"""文鉴 NLP Engine — 中文分词 + POS 词性标注 + 可读性评分。

v3.1: 集成 jieba 分词器, 标准 POS 标注, 多重可读性指标。
若 jieba 不可用则自动 fallback 到正则模式。
"""

from __future__ import annotations

import math
import re
from collections import Counter

# ── 尝试导入 jieba ──────────────────────────────────────────────────────
_JIEBA_AVAILABLE = False
_jieba_posseg = None

try:
    import jieba
    import jieba.posseg as _jieba_posseg

    _JIEBA_AVAILABLE = True
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════════════
# POS 标签映射表（jieba → 标准）
# ═══════════════════════════════════════════════════════════════════════════

_JIEBA_TAG_MAP = {
    # 名词类 → NOUN
    "n": "NOUN",
    "nr": "NOUN",
    "nrfg": "NOUN",
    "nrt": "NOUN",
    "ns": "NOUN",
    "nt": "NOUN",
    "nz": "NOUN",
    "ng": "NOUN",
    # 动词类 → VERB
    "v": "VERB",
    "vd": "VERB",
    "vg": "VERB",
    "vi": "VERB",
    "vn": "VERB",
    "vq": "VERB",
    # 形容词 → ADJ
    "a": "ADJ",
    "ad": "ADJ",
    "an": "ADJ",
    "ag": "ADJ",
    # 副词 → ADV
    "d": "ADV",
    "df": "ADV",
    "dg": "ADV",
    # 代词 → PRON
    "r": "PRON",
    "rg": "PRON",
    "rr": "PRON",
    "rz": "PRON",
    # 助词 → AUX
    "u": "AUX",
    "ud": "AUX",
    "ug": "AUX",
    "uj": "AUX",
    "ul": "AUX",
    "uv": "AUX",
    "uz": "AUX",
    # 连词 → CONJ
    "c": "CONJ",
    # 数词 → NUM
    "m": "NUM",
    "mg": "NUM",
    "mq": "NUM",
    # 量词 → QUANT
    "q": "QUANT",
    # 介词 → ADP
    "p": "ADP",
    # 时间词 → TIME
    "t": "TIME",
    "tg": "TIME",
    # 方位词 → LOC
    "f": "LOC",
    # 叹词 → INTJ
    "e": "INTJ",
    # 拟声词 → ONOM
    "o": "ONOM",
    # 状态词 → STATE
    "z": "STATE",
    "zg": "STATE",
    # 区别词 → DIFF
    "b": "DIFF",
    # 处所词 → NOUN
    "s": "NOUN",
    # 语素 → MORPH
    "g": "MORPH",
    # 其他
    "x": "OTHER",
    "y": "PUNCT",
    "h": "PREFIX",
    "k": "SUFFIX",
    "i": "IDIOM",
    "l": "IDIOM",
    "j": "ABBR",
}

# 虚词标签集合（用于 function_word_ratio）
_FUNCTION_POS = {"AUX", "ADP", "CONJ", "PRON"}

# 实词标签集合（名词 + 动词）
_CONTENT_POS_NV = {"NOUN", "VERB"}


# ═══════════════════════════════════════════════════════════════════════════
# Fallback 正则模式（jieba 不可用时使用）
# ═══════════════════════════════════════════════════════════════════════════

_FALLBACK_POS_PATTERNS = {
    "NOUN": re.compile(
        r"(?:修士|仙人|妖兽|灵气|丹药|法术|功法|道|剑|阵|山|水|天|地"
        r"|人|手|眼|心|头|身|脸|声|光|影|血|火|风|云|雷|电"
        r"|世界|力量|时间|空间|修炼|境界|宗门|弟子|师父|师兄弟)"
    ),
    "VERB": re.compile(
        r"(?:修炼|突破|攻击|防御|飞行|施展|释放|运转|凝聚|吸收|打坐"
        r"|走|跑|说|道|看|想|来|去|做|给|让|使|拿|放"
        r"|出现|消失|战斗|出手|爆发|斩杀|得到|成为|发现|知道)"
    ),
    "ADJ": re.compile(
        r"(?:强大|恐怖|惊人|可怕|神秘|古老|巨大|渺小|危险|美丽|丑陋"
        r"|冷|热|快|慢|好|坏|多|少|大|小|强|弱)"
    ),
    "PRON": re.compile(r"(?:他|她|它|我|你|您|我们|你们|他们|她们|自己|自身|彼此|其)"),
    "ADV": re.compile(
        r"(?:忽然|突然|渐渐|逐渐|已经|正在|一直|总是|终于|仍然"
        r"|非常|很|更|最|也|还|就|才|都|只)"
    ),
    "AUX": re.compile(r"(?:的|了|着|过|得|地|之|所|被|把|将|以|而|与|和|或)"),
    "CONJ": re.compile(r"(?:但是|然而|虽然|如果|因为|所以|于是|而且|或者|还是|只是|甚至|并且)"),
    "NUM": re.compile(
        r"(?:一|二|三|四|五|六|七|八|九|十|百|千|万|亿"
        r"|[一二三四五六七八九十百千万亿])"
    ),
    "ADP": re.compile(r"(?:在|从|到|向|往|朝|比|跟|对|为|给|替|于|以|将|把|被|叫|让)"),
}


# ═══════════════════════════════════════════════════════════════════════════
# NLPEngine 主类
# ═══════════════════════════════════════════════════════════════════════════


class NLPEngine:
    """统一 NLP 引擎：封装 jieba 分词、POS 标注 + fallback。"""

    def __init__(self):
        self._available = _JIEBA_AVAILABLE
        if self._available:
            # 静默模式
            jieba.setLogLevel(20)

    # ── 基本接口 ──────────────────────────────────────────────────────

    def segment(self, text: str) -> list[str]:
        """中文分词，返回词语列表。"""
        if not text:
            return []
        if self._available:
            return list(jieba.cut(text))
        return self._fallback_segment(text)

    def pos_tag(self, text: str) -> list[tuple[str, str]]:
        """词性标注，返回 [(word, pos_tag), ...]。

        POS 标签已映射到标准类别（NOUN/VERB/ADJ/ADV/PRON/AUX/CONJ/NUM/ADP...）。
        """
        if not text:
            return []
        if self._available:
            result = []
            for word, flag in _jieba_posseg.cut(text):
                std_tag = _JIEBA_TAG_MAP.get(flag, flag.upper())
                result.append((word, std_tag))
            return result
        return self._fallback_pos_tag(text)

    def tokenize(self, text: str, mode: str = "default") -> list[tuple[str, int, int]]:
        """分词并返回位置信息。

        Args:
            text: 待分词文本
            mode: "default" 精确模式 / "search" 搜索引擎模式

        Returns:
            [(word, start_pos, end_pos), ...]
        """
        if not text:
            return []
        if self._available:
            cut_mode = mode == "search"
            return list(jieba.tokenize(text, mode=cut_mode))
        # fallback：逐字分割
        return [(c, i, i + 1) for i, c in enumerate(text)]

    # ── POS 分布 ──────────────────────────────────────────────────────

    def get_pos_distribution(self, text: str) -> dict[str, dict]:
        """返回词性分布统计。

        Returns:
            {
                "counts": {"NOUN": 123, "VERB": 89, ...},
                "ratios": {"NOUN": 0.234, "VERB": 0.169, ...},
                "total_tokens": 527,
                "unique_pos_tags": 12,
            }
        """
        tagged = self.pos_tag(text)
        if not tagged:
            return {"counts": {}, "ratios": {}, "total_tokens": 0, "unique_pos_tags": 0}

        pos_counter = Counter(tag for _, tag in tagged)
        total = len(tagged)

        return {
            "counts": dict(pos_counter.most_common()),
            "ratios": {tag: round(cnt / total, 4) for tag, cnt in pos_counter.items()},
            "total_tokens": total,
            "unique_pos_tags": len(pos_counter),
        }

    def get_pos_bigram_entropy(self, text: str) -> dict:
        """POS bigram 转移概率矩阵 + 熵。

        Returns:
            {
                "bigram_counts": {"NOUN_VERB": 34, "VERB_NOUN": 28, ...},
                "bigram_probabilities": {"NOUN_VERB": 0.12, ...},
                "bigram_entropy": 3.456,      # 转移熵（越高越不可预测）
                "conditional_entropy": {...},  # 每种前驱的条件熵
                "top_bigrams": [("NOUN_VERB", 34), ...],
            }
        """
        tagged = self.pos_tag(text)
        if len(tagged) < 2:
            return {
                "bigram_counts": {},
                "bigram_probabilities": {},
                "bigram_entropy": 0.0,
                "conditional_entropy": {},
                "top_bigrams": [],
            }

        # 构建 bigram 计数
        bigrams = Counter()
        prev_tags_count = Counter()

        for i in range(len(tagged) - 1):
            prev_tag = tagged[i][1]
            curr_tag = tagged[i + 1][1]
            bg = f"{prev_tag}_{curr_tag}"
            bigrams[bg] += 1
            prev_tags_count[prev_tag] += 1

        # 转移概率 P(B|A)
        probabilities = {}
        conditional = {}
        for bg, cnt in bigrams.items():
            prev, _ = bg.split("_", 1)
            prob = cnt / prev_tags_count[prev] if prev_tags_count[prev] > 0 else 0
            probabilities[bg] = round(prob, 4)
            conditional.setdefault(prev, {})[bg] = prob

        # bigram 联合熵 H(A,B) = -Σ P(a,b) log₂ P(a,b)
        total_bigrams = sum(bigrams.values())
        joint_entropy = 0.0
        for cnt in bigrams.values():
            p = cnt / total_bigrams
            joint_entropy -= p * math.log2(p)

        # 条件熵 H(B|A) 按前驱标签
        cond_entropy = {}
        for prev, cond_probs in conditional.items():
            h = 0.0
            for p in cond_probs.values():
                if p > 0:
                    h -= p * math.log2(p)
            cond_entropy[prev] = round(h, 4)

        return {
            "bigram_counts": dict(bigrams),
            "bigram_probabilities": probabilities,
            "bigram_entropy": round(joint_entropy, 4),
            "conditional_entropy": cond_entropy,
            "top_bigrams": [(bg, cnt) for bg, cnt in bigrams.most_common(30)],
        }

    def get_noun_verb_ratio(self, text: str) -> float:
        """名词/动词比（衡量描述型 vs 动作型的倾向）。"""
        dist = self.get_pos_distribution(text)
        ratios = dist.get("ratios", {})
        noun_r = ratios.get("NOUN", 0)
        verb_r = ratios.get("VERB", 0)
        if verb_r == 0:
            return 999.0 if noun_r > 0 else 0.0
        return round(noun_r / verb_r, 4)

    def get_function_word_ratio(self, text: str) -> float:
        """虚词占比（AUX + ADP + CONJ + PRON）"""
        dist = self.get_pos_distribution(text)
        ratios = dist.get("ratios", {})
        return round(sum(ratios.get(tag, 0) for tag in _FUNCTION_POS), 4)

    # ── 可读性评分 ────────────────────────────────────────────────────

    def readability_scores(self, text: str) -> dict:
        """多重可读性评分。自动检测中文/英文。

        Returns:
            {
                "language": "zh" | "en",
                "avg_sentence_len": 25.3,
                "max_sentence_len": 180,
                "short_sentence_ratio": 0.35,     # 短句占比 (≤10字)
                "difficult_word_ratio": 0.12,     # 难词比 (≥4字词)
                "char_density": 0.85,             # 汉字密度
                # 英文专属
                "flesch_kincaid": 8.5,            # Flesch-Kincaid Grade
                "smog": 7.2,                      # SMOG
                "gunning_fog": 10.1,              # Gunning Fog Index
            }
        """
        if not text:
            return {"language": "unknown", "error": "empty text"}

        # 检测语言：中文字符占比
        chinese_chars = sum(1 for c in text if "一" <= c <= "鿿")
        total_chars = len(text.replace("\n", "").replace("\r", "").replace(" ", ""))
        chinese_ratio = chinese_chars / max(total_chars, 1)

        if chinese_ratio > 0.3:
            return self._readability_zh(text)
        return self._readability_en(text)

    def _readability_zh(self, text: str) -> dict:
        """中文可读性指标。"""
        # 分句（按句末标点）
        sentences = [s.strip() for s in re.split(r"[。！？!?\n]+", text) if s.strip()]
        sent_lens = [len(s) for s in sentences]

        avg_sent_len = round(mean_or_zero(sent_lens), 1)
        max_sent_len = max(sent_lens) if sent_lens else 0
        short_ratio = round(sum(1 for ln in sent_lens if ln <= 10) / max(len(sent_lens), 1), 4)

        # 难词比：≥4字词（分词后）
        words = self.segment(text)
        total_words = len(words)
        difficult = sum(1 for w in words if len(w) >= 4 and any("一" <= c <= "鿿" for c in w))
        difficult_ratio = round(difficult / max(total_words, 1), 4)

        # 汉字密度
        zh_chars = sum(1 for c in text if "一" <= c <= "鿿")
        all_text = text.replace("\n", "").replace("\r", "").replace(" ", "")
        char_density = round(zh_chars / max(len(all_text), 1), 4)

        return {
            "language": "zh",
            "avg_sentence_len": avg_sent_len,
            "max_sentence_len": max_sent_len,
            "short_sentence_ratio": short_ratio,
            "difficult_word_ratio": difficult_ratio,
            "char_density": char_density,
            "total_sentences": len(sentences),
            "total_words": total_words,
        }

    def _readability_en(self, text: str) -> dict:
        """英文可读性指标（Flesch-Kincaid, SMOG, Gunning Fog）。"""
        # 分句
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", text) if s.strip()]
        # 分词
        words = [w for w in re.findall(r"[a-zA-Z]+", text) if w]
        # 音节数（近似）
        syllables = [self._count_syllables(w) for w in words]

        total_words = len(words)
        total_sentences = len(sentences)
        total_syllables = sum(syllables)

        if total_words == 0 or total_sentences == 0:
            return {"language": "en", "error": "insufficient text"}

        avg_sent_len = round(total_words / total_sentences, 1)

        # Flesch-Kincaid Grade Level
        fk_grade = round(
            0.39 * (total_words / total_sentences) + 11.8 * (total_syllables / total_words) - 15.59,
            1,
        )

        # SMOG
        polysyllable_count = sum(1 for s in syllables if s >= 3)
        smog = round(1.043 * math.sqrt(polysyllable_count * 30.0 / total_sentences) + 3.1291, 1)

        # Gunning Fog Index
        complex_count = polysyllable_count
        gfi = round(
            0.4 * ((total_words / total_sentences) + 100.0 * (complex_count / total_words)), 1
        )

        return {
            "language": "en",
            "avg_sentence_len": avg_sent_len,
            "max_sentence_len": max(len(w) for w in words),
            "flesch_kincaid_grade": fk_grade,
            "smog": smog,
            "gunning_fog": gfi,
            "total_words": total_words,
            "total_sentences": total_sentences,
            "total_syllables": total_syllables,
            "polysyllable_count": polysyllable_count,
        }

    @staticmethod
    def _count_syllables(word: str) -> int:
        """近似音节计数（英文）。"""
        word = word.lower().strip(".:;?!")
        if not word:
            return 0
        # 简单元音规则
        vowels = "aeiouy"
        count = 0
        prev_vowel = False
        for ch in word:
            if ch in vowels:
                if not prev_vowel:
                    count += 1
                prev_vowel = True
            else:
                prev_vowel = False
        # 结尾 e 不发音
        if word.endswith("e") and count > 1:
            count -= 1
        # 末尾 le 特殊情况
        if word.endswith("le") and len(word) > 2 and word[-3] not in vowels:
            count += 1
        return max(1, count)

    # ── Fallback 模式 ─────────────────────────────────────────────────

    def _fallback_segment(self, text: str) -> list[str]:
        """Fallback: 逐字 + 简单切词。"""
        # 将连续汉字组合为一个词
        result = []
        buf = ""
        for ch in text:
            if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿":
                buf += ch
            else:
                if buf:
                    result.append(buf)
                    buf = ""
                if ch.strip():
                    result.append(ch)
        if buf:
            result.append(buf)
        return result

    def _fallback_pos_tag(self, text: str) -> list[tuple[str, str]]:
        """Fallback: 正则近似 POS 标注。"""
        results = []
        words = self._fallback_segment(text)
        for word in words:
            tag = "OTHER"
            for pos, pattern in _FALLBACK_POS_PATTERNS.items():
                if pattern.fullmatch(word.strip()):
                    tag = pos
                    break
            results.append((word, tag))
        return results

    # ── 分词质量标记 ──────────────────────────────────────────────────

    @property
    def nlp_quality(self) -> dict:
        """返回当前 NLP 引擎的质量标记。"""
        return {
            "jieba_available": self._available,
            "pos_tagger": "jieba.posseg" if self._available else "regex_fallback",
            "segmenter": "jieba" if self._available else "char_based_fallback",
            "accuracy_warning": not self._available,
            "recommendation": (
                "Full NLP features active"
                if self._available
                else "Install jieba for accurate POS tagging and segmentation"
            ),
        }


# ═══════════════════════════════════════════════════════════════════════════
# 模块级便捷函数（自动管理单例）
# ═══════════════════════════════════════════════════════════════════════════

_engine: NLPEngine | None = None


def get_engine() -> NLPEngine:
    """获取 NLPEngine 单例。"""
    global _engine
    if _engine is None:
        _engine = NLPEngine()
    return _engine


def segment(text: str) -> list[str]:
    return get_engine().segment(text)


def pos_tag(text: str) -> list[tuple[str, str]]:
    return get_engine().pos_tag(text)


def tokenize(text: str, mode: str = "default") -> list[tuple[str, int, int]]:
    return get_engine().tokenize(text, mode)


def get_pos_distribution(text: str) -> dict[str, dict]:
    return get_engine().get_pos_distribution(text)


def get_pos_bigram_entropy(text: str) -> dict:
    return get_engine().get_pos_bigram_entropy(text)


def readability_scores(text: str) -> dict:
    return get_engine().readability_scores(text)


# ═══════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════


def mean_or_zero(values: list) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
