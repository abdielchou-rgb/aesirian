"""文鉴 StyleFingerprint Engine — 四层风格指纹提取与漂移检测。

吸收 28 家同行项目的设计模式：
  L1 词级指纹 — 虚词频率谱 / POS bigram / 词汇多样性 / 高频字偏好
     ← 李贤平47虚字法(红楼梦) / pystylometry / stylo(MFW扫描) / 汉语语体计量
  L2 句级指纹 — 句长分布(均值+离散度+分位数) / 标点密度谱(32种) / 句式类型比 / 从句深度
     ← 金庸古龙聚类 / 中文Web作者识别 / 韩寒郭敬明对比
  L3 篇章指纹 — 段落呼吸节奏 / 对话叙述比 / 感官描写密度 / 过渡词偏好
     ← ProseEngine / ProWritingAid 25+报告 / Revise跨章一致性
  L4 叙事指纹 — 情节因果链密度 / 视角切换频率 / 意象复用间隔 / 幕结构比例
     ← StoryTangl / DRESS风格子空间

评估框架：StyleFidelity × ContentIndependence × Fluency = OverallAuthenticity (DRESS)
漂移追踪：跨章节风格向量变化 + 参数扫描稳定性 (stylo)
"""

from __future__ import annotations
import re
import json
import math
from pathlib import Path
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional
from statistics import mean, stdev, median, quantiles

from .analyzer import analyzer
from .nlp_engine import NLPEngine, get_engine
from .dl_engine import get_dl_engine, DLEngine


# ═══════════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class LexicalFingerprint:
    """L1: 词级指纹。"""
    # 虚词频率谱 — 李贤平47虚字 + 现代扩展
    function_word_spectrum: dict[str, float] = field(default_factory=dict)
    top_function_words: list[tuple[str, float]] = field(default_factory=list)

    # POS bigram — 汉语语体计量（v3.1: jieba.posseg 替代正则）
    pos_bigram_top: list[tuple[str, float]] = field(default_factory=list)
    pos_ratio: dict[str, float] = field(default_factory=dict)  # 名词/动词/形容词/代词/副词/助词比
    pos_bigram_entropy: float = 0.0         # v3.1: POS bigram 转移熵
    noun_verb_ratio: float = 0.0            # v3.1: 名词/动词比
    function_word_ratio: float = 0.0        # v3.1: 虚词占比(AUX+ADP+CONJ+PRON)

    # 词汇多样性 — pystylometry
    ttr: float = 0.0          # Type-Token Ratio
    mtld: float = 0.0         # Measure of Textual Lexical Diversity
    yule_k: float = 0.0       # Yule's K
    hapax_ratio: float = 0.0  # 单现词比例
    unique_char_ratio: float = 0.0

    # 高频字偏好 Top-50 — stylo
    top_chars: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class SyntacticFingerprint:
    """L2: 句级指纹。"""
    # 句长分布 — 金庸古龙
    mean_sentence_len: float = 0.0
    std_sentence_len: float = 0.0
    sentence_len_quantiles: list[float] = field(default_factory=list)  # [p25, p50, p75]
    sentence_len_discreteness: float = 0.0  # 离散度 = std/mean

    # 标点密度谱(32种) — 中文Web作者识别
    punctuation_spectrum: dict[str, float] = field(default_factory=dict)
    total_punctuation_ratio: float = 0.0  # 标点占字数的比例

    # 句式类型比 — 韩寒郭敬明
    declarative_ratio: float = 0.0   # 陈述句
    interrogative_ratio: float = 0.0 # 疑问句
    exclamatory_ratio: float = 0.0   # 感叹句
    ellipsis_density: float = 0.0    # 省略号密度

    # 从句嵌套
    avg_clause_depth: float = 0.0
    subordination_ratio: float = 0.0  # 从属连词密度


@dataclass
class DiscourseFingerprint:
    """L3: 篇章指纹。"""
    # 段落呼吸节奏 — ProseEngine
    mean_paragraph_len: float = 0.0
    std_paragraph_len: float = 0.0
    paragraph_len_discreteness: float = 0.0
    paragraph_len_distribution: list[int] = field(default_factory=list)  # 每段字数列表

    # 对话/叙述比 — ProseEngine
    dialogue_ratio: float = 0.0       # 对话占总字数比
    narration_ratio: float = 0.0      # 叙述占总字数比
    inner_monologue_ratio: float = 0.0

    # 感官描写密度 — ProWritingAid
    visual_density: float = 0.0       # 视觉词密度
    auditory_density: float = 0.0     # 听觉词密度
    tactile_density: float = 0.0      # 触觉词密度
    olfactory_density: float = 0.0    # 嗅觉词密度
    gustatory_density: float = 0.0    # 味觉词密度
    total_sensory_density: float = 0.0

    # 过渡词偏好 — ProWritingAid
    transition_density: float = 0.0
    top_transitions: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class NarrativeFingerprint:
    """L4: 叙事指纹。"""
    # 情节因果链
    causality_marker_density: float = 0.0  # 因为/所以/因此/于是/结果 密度
    foreshadowing_density: float = 0.0     # 伏笔密度

    # 视角切换
    pov_switch_frequency: float = 0.0      # 每千字视角切换次数

    # 意象复用间隔
    top_images: list[tuple[str, int]] = field(default_factory=list)
    image_reuse_interval_mean: float = 0.0

    # 幕结构
    chapter_tension_curve: list[float] = field(default_factory=list)

    # v3.3: 叙事增强字段
    act_coherence: float = 0.0             # 幕间连贯性
    causal_density: float = 0.0            # 因果密度（每千字因果节点数）
    climax_position: float = 0.0           # 高潮位置百分比
    character_arc_count: int = 0           # 弧光变化角色数（非flat）

    # v3.4: 网文专项字段
    shuang_dian_density: float = 0.0       # 爽点密度（每千字爽点数）
    power_progression_speed: float = 0.0   # 升级速度（每章平均升级次数）
    avg_hook_score: float = 0.0            # 平均钩子强度
    twist_density: float = 0.0             # 反转密度（每万字反转次数）
    foreshadow_recovery: float = 0.0       # 伏笔回收率


@dataclass
class StyleFingerprint:
    """四层风格指纹完整结果。"""
    novel_name: str = ""
    author: str = ""
    genre: str = "xianxia_modern"
    total_chars: int = 0
    chapter_count: int = 0

    lexical: LexicalFingerprint = field(default_factory=LexicalFingerprint)
    syntactic: SyntacticFingerprint = field(default_factory=SyntacticFingerprint)
    discourse: DiscourseFingerprint = field(default_factory=DiscourseFingerprint)
    narrative: NarrativeFingerprint = field(default_factory=NarrativeFingerprint)

    # 原始数据（用于参数扫描和多基线）
    raw_sentence_lengths: list[int] = field(default_factory=list)
    raw_paragraph_lengths: list[int] = field(default_factory=list)
    chapter_fingerprints: list[dict] = field(default_factory=list)  # 逐章指纹

    # v3.1: NLP 质量标记
    nlp_quality: dict = field(default_factory=dict)

    # v4.0: DL 风格嵌入向量（仅 DL 可用时填充）
    dl_embedding: Optional[list[float]] = field(default=None)

    def to_dict(self) -> dict:
        return {
            "meta": {
                "novel": self.novel_name, "author": self.author,
                "genre": self.genre, "total_chars": self.total_chars,
                "chapter_count": self.chapter_count,
            },
            "L1_lexical": {
                "function_word_spectrum": self.lexical.function_word_spectrum,
                "top_function_words": self.lexical.top_function_words,
                "pos_bigram_top": self.lexical.pos_bigram_top,
                "pos_bigram_entropy": self.lexical.pos_bigram_entropy,
                "noun_verb_ratio": self.lexical.noun_verb_ratio,
                "function_word_ratio": self.lexical.function_word_ratio,
                "pos_ratio": self.lexical.pos_ratio,
                "diversity": {
                    "ttr": self.lexical.ttr, "mtld": self.lexical.mtld,
                    "yule_k": self.lexical.yule_k, "hapax_ratio": self.lexical.hapax_ratio,
                    "unique_char_ratio": self.lexical.unique_char_ratio,
                },
                "top_chars": self.lexical.top_chars,
            },
            "L2_syntactic": {
                "sentence_length": {
                    "mean": self.syntactic.mean_sentence_len,
                    "std": self.syntactic.std_sentence_len,
                    "discreteness": self.syntactic.sentence_len_discreteness,
                    "quantiles": self.syntactic.sentence_len_quantiles,
                },
                "punctuation_spectrum": self.syntactic.punctuation_spectrum,
                "total_punctuation_ratio": self.syntactic.total_punctuation_ratio,
                "sentence_types": {
                    "declarative": self.syntactic.declarative_ratio,
                    "interrogative": self.syntactic.interrogative_ratio,
                    "exclamatory": self.syntactic.exclamatory_ratio,
                    "ellipsis_density": self.syntactic.ellipsis_density,
                },
                "clause": {
                    "avg_depth": self.syntactic.avg_clause_depth,
                    "subordination_ratio": self.syntactic.subordination_ratio,
                },
            },
            "L3_discourse": {
                "paragraph_rhythm": {
                    "mean_len": self.discourse.mean_paragraph_len,
                    "std_len": self.discourse.std_paragraph_len,
                    "discreteness": self.discourse.paragraph_len_discreteness,
                },
                "mode_ratio": {
                    "dialogue": self.discourse.dialogue_ratio,
                    "narration": self.discourse.narration_ratio,
                    "inner_monologue": self.discourse.inner_monologue_ratio,
                },
                "sensory_density": {
                    "visual": self.discourse.visual_density,
                    "auditory": self.discourse.auditory_density,
                    "tactile": self.discourse.tactile_density,
                    "olfactory": self.discourse.olfactory_density,
                    "gustatory": self.discourse.gustatory_density,
                    "total": self.discourse.total_sensory_density,
                },
                "transitions": {
                    "density": self.discourse.transition_density,
                    "top": self.discourse.top_transitions,
                },
            },
            "L4_narrative": {
                "causality_density": self.narrative.causality_marker_density,
                "foreshadowing_density": self.narrative.foreshadowing_density,
                "pov_switch_freq": self.narrative.pov_switch_frequency,
                "top_images": self.narrative.top_images,
                "image_reuse_interval": self.narrative.image_reuse_interval_mean,
                # v3.3 叙事增强
                "act_coherence": self.narrative.act_coherence,
                "causal_density": self.narrative.causal_density,
                "climax_position": self.narrative.climax_position,
                "character_arc_count": self.narrative.character_arc_count,
                # v3.4 网文专项
                "shuang_dian_density": self.narrative.shuang_dian_density,
                "power_progression_speed": self.narrative.power_progression_speed,
                "avg_hook_score": self.narrative.avg_hook_score,
                "twist_density": self.narrative.twist_density,
                "foreshadow_recovery": self.narrative.foreshadow_recovery,
            },
            "nlp_quality": self.nlp_quality,
            # v4.0: DL 嵌入摘要（仅存储维度和前3个值，完整向量太大）
            "dl_embedding": {
                "available": self.dl_embedding is not None,
                "dim": len(self.dl_embedding) if self.dl_embedding else 0,
                "preview": self.dl_embedding[:3] if self.dl_embedding else None,
            } if self.dl_embedding else None,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str):
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @staticmethod
    def load(path: str) -> "StyleFingerprint":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return _dict_to_fingerprint(d)


# ═══════════════════════════════════════════════════════════════════════════
# Style Drift Detection (DRESS / Revise 跨章漂移)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class StyleDriftResult:
    """风格漂移检测结果。"""
    passed: bool = True
    overall_authenticity: float = 0.0  # DRESS: SI × SP × FS
    style_fidelity: float = 0.0        # SI: Style Intensity
    content_independence: float = 0.0  # SP: Semantic Preservation (1.0 = 无内容干扰)
    fluency: float = 0.0               # FS: Fluency Score (1.0 = 流畅)

    drift_dimensions: list[dict] = field(default_factory=list)
    chapter_fingerprint: Optional[StyleFingerprint] = None

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "overall_authenticity": round(self.overall_authenticity, 4),
            "style_fidelity": round(self.style_fidelity, 4),
            "content_independence": round(self.content_independence, 4),
            "fluency": round(self.fluency, 4),
            "drift_dimensions": self.drift_dimensions,
        }


# ═══════════════════════════════════════════════════════════════════════════
# ── 常量：中文风格特征词典 ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

# 李贤平47虚字 + 现代扩展 → 共80个虚词
FUNCTION_WORDS = [
    # 文言虚字(13) — 李贤平
    "之", "其", "或", "亦", "方", "于", "即", "皆", "因", "仍", "故", "尚", "乃",
    # 句尾虚字(9) — 李贤平
    "呀", "吗", "咧", "罢咧", "啊", "罢", "罢了", "么", "呢",
    # 现代高频虚词 — 扩展
    "的", "了", "在", "是", "有", "和", "与", "而", "但", "却", "就", "也",
    "还", "又", "再", "才", "都", "只", "很", "更", "最", "非常", "已经",
    "正在", "一直", "总是", "终于", "仍然", "忽然", "突然", "其实", "确实",
    "所以", "因为", "如果", "虽然", "但是", "然而", "于是", "然后", "接着",
    "不过", "而且", "并且", "或者", "还是", "只是", "甚至", "尤其", "居然",
    "竟然", "果然", "当然", "自然", "似乎", "仿佛", "好像",
]

# 32种标点符号 — 中文Web作者识别
PUNCTUATION_MAP = {
    # 中文标点
    "。": "period_cn", "！": "exclamation_cn", "？": "question_cn",
    "，": "comma_cn", "；": "semicolon_cn", "：": "colon_cn",
    "、": "enumeration_cn", "……": "ellipsis_cn", "——": "dash_cn",
    "「": "quote_cn_l", "」": "quote_cn_r",
    "“": "quote_double_l", "”": "quote_double_r",
    "‘": "quote_single_l", "’": "quote_single_r",
    "（": "paren_l", "）": "paren_r",
    "《": "book_l", "》": "book_r",
    "【": "bracket_l", "】": "bracket_r",
    # 英文标点（中文小说中混用）
    ".": "period_en", "!": "exclamation_en", "?": "question_en",
    ",": "comma_en", ";": "semicolon_en", ":": "colon_en",
    "...": "ellipsis_en", "—": "dash_em", "–": "dash_en",
    '"': "quote_double", "'": "quote_single",
    "~": "tilde", "·": "dot_middle",
}

# 五感词库 — ProWritingAid
SENSORY_WORDS = {
    "visual": ["看", "见", "望", "观", "视", "注视", "凝视", "瞥", "盯", "瞪",
                "瞧", "眺", "俯瞰", "仰望", "光明", "黑暗", "亮", "暗", "闪烁",
                "颜色", "红", "蓝", "绿", "白", "黑", "金黄", "苍白", "昏暗", "明亮"],
    "auditory": ["听", "闻", "声", "音", "响", "叫", "喊", "吼", "啸", "鸣",
                 "低语", "耳语", "喧闹", "寂静", "轰鸣", "清脆", "低沉", "尖锐", "沙哑"],
    "tactile": ["触", "摸", "碰", "抚", "拍", "按", "捏", "握", "抓", "抱",
                "冷", "热", "凉", "暖", "烫", "冰", "粗糙", "光滑", "柔软", "坚硬",
                "湿", "干", "粘", "滑", "刺痛", "麻木", "沉", "轻"],
    "olfactory": ["嗅", "闻", "香", "臭", "腥", "芬芳", "清香", "刺鼻", "浓郁",
                  "淡雅", "霉", "腐", "焦", "烟味", "花香", "草香"],
    "gustatory": ["尝", "吃", "喝", "品", "舔", "吞咽",
                  "甜", "苦", "酸", "辣", "咸", "涩", "鲜", "甘", "醇", "清淡"],
}

# 过渡词 — ProWritingAid
TRANSITION_WORDS = [
    "然而", "但是", "不过", "虽然", "尽管", "可是", "却",
    "因此", "所以", "于是", "因而", "故此",
    "接着", "然后", "随后", "之后", "此后", "接下来",
    "同时", "与此同时", "另一方面",
    "此外", "另外", "而且", "并且", "况且",
    "总之", "总而言之", "综上所述",
    "首先", "其次", "最后", "第一", "第二", "第三",
    "例如", "比如", "譬如", "像是",
    "换句话说", "换言之", "也就是说",
    "实际上", "事实上", "其实",
    "当然", "自然", "显然", "明显",
    "突然", "忽然", "猛然", "骤然",
    "渐渐", "逐渐", "慢慢", "缓缓",
]

# 因果标记 — StoryTangl
CAUSALITY_MARKERS = [
    "因为", "所以", "因此", "于是", "由于", "结果", "导致",
    "造成", "引起", "从而", "故而", "既然", "既然……就",
    "之所以", "是因为", "以致", "以至",
]

# 视角标记
POV_MARKERS = [
    "他想", "她感到", "他认为", "她觉得", "他心想", "她心想",
    "他意识到", "她意识到", "他明白", "她明白",
    "内心", "心里", "心头", "心底", "暗自", "默默",
]

# POS 近似映射（启发式，零外部依赖）
POS_PATTERNS = {
    "noun": re.compile(r'(?:修士|仙人|妖兽|灵气|丹药|法术|功法|道|剑|阵|山|水|天|地'
                            r'|人|手|眼|心|头|身|脸|声|光|影|血|火|风|云|雷|电)'),
    "verb": re.compile(r'(?:修炼|突破|攻击|防御|飞行|施展|释放|运转|凝聚|吸收|打坐'
                           r'|走|跑|说|道|看|想|来|去|做|给|让|使|拿|放)'),
    "adj": re.compile(r'(?:强大|恐怖|惊人|可怕|神秘|古老|巨大|渺小|危险|美丽|丑陋'
                           r'|冷|热|快|慢|好|坏|多|少|大|小|强|弱)'),
    "pronoun": re.compile(r'(?:他|她|它|我|你|您|我们|你们|他们|她们|自己|自身|彼此|其)'),
    "adverb": re.compile(r'(?:忽然|突然|渐渐|逐渐|已经|正在|一直|总是|终于|仍然|非常|很|更|最|也|还|就|才|都|只)'),
    "auxiliary": re.compile(r'(?:的|了|着|过|得|地|之|所|被|把|将|以|而|与|和|或)'),
    "conjunction": re.compile(r'(?:但是|然而|虽然|如果|因为|所以|于是|而且|或者|还是|只是|甚至|并且)'),
    "numeral": re.compile(r'(?:一|二|三|四|五|六|七|八|九|十|百|千|万|亿|[一二三四五六七八九十百千万亿])'),
    "modal": re.compile(r'(?:能|可以|会|要|想|敢|愿意|必须|应该|能够|可能|一定)'),
}


# ═══════════════════════════════════════════════════════════════════════════
# Core Extraction
# ═══════════════════════════════════════════════════════════════════════════


def extract_style_fingerprint(
    text: str,
    novel_name: str = "unknown",
    author: str = "",
    genre: str = "xianxia_modern",
    dl: bool = False,
) -> StyleFingerprint:
    """从文本提取四层风格指纹。

    一次调用完成 L1~L4 全部特征提取，零 API Key，纯启发式。
    dl=True 且 DL 引擎可用时，附加 384/768 维风格嵌入向量。
    """
    chapters = _split_chapters(text)
    if not chapters:
        chapters = [{"title": novel_name, "text": text[:5000]}]

    total_chars = sum(len(ch["text"]) for ch in chapters)

    # ── L1: 词级指纹 ──────────────────────────────────────────────────
    lexical = _extract_lexical(text)

    # ── L2: 句级指纹 ──────────────────────────────────────────────────
    syntactic, raw_sentence_lengths = _extract_syntactic(text)

    # ── L3: 篇章指纹 ──────────────────────────────────────────────────
    discourse, raw_paragraph_lengths = _extract_discourse(text)

    # ── L4: 叙事指纹 ──────────────────────────────────────────────────
    narrative = _extract_narrative(text, chapters)

    # 逐章指纹（用于跨章漂移追踪）
    chapter_fps = []
    for i, ch in enumerate(chapters):
        if len(ch["text"]) < 100:
            continue
        ch_fp = _extract_chapter_brief(ch["text"], i + 1, ch.get("title", ""))
        chapter_fps.append(ch_fp)

    result = StyleFingerprint(
        novel_name=novel_name,
        author=author,
        genre=genre,
        total_chars=total_chars,
        chapter_count=len(chapters),
        lexical=lexical,
        syntactic=syntactic,
        discourse=discourse,
        narrative=narrative,
        raw_sentence_lengths=raw_sentence_lengths,
        raw_paragraph_lengths=raw_paragraph_lengths,
        chapter_fingerprints=chapter_fps,
        nlp_quality=get_engine().nlp_quality,
    )

    # v4.0: DL 嵌入向量
    if dl:
        engine = get_dl_engine()
        if engine.is_available():
            try:
                result.dl_embedding = engine.encode_style(text)
            except Exception:
                pass

    return result


# ═══════════════════════════════════════════════════════════════════════════
# L1: Lexical Extraction
# ═══════════════════════════════════════════════════════════════════════════


def _extract_lexical(text: str) -> LexicalFingerprint:
    """提取 L1 词级指纹。"""
    lf = LexicalFingerprint()

    # ── 虚词频率谱 ────────────────────────────────────────────────────
    # 统计每种虚词的出现频率（每千字）
    total_chars = len(text)
    fw_counts = {}
    for fw in FUNCTION_WORDS:
        count = text.count(fw)
        if count > 0:
            fw_counts[fw] = round(count / max(total_chars, 1) * 1000, 4)

    lf.function_word_spectrum = dict(
        sorted(fw_counts.items(), key=lambda x: x[1], reverse=True)
    )
    lf.top_function_words = list(
        sorted(fw_counts.items(), key=lambda x: x[1], reverse=True)
    )[:20]

    # ── POS 比例 (v3.1: jieba.posseg 真正词性标注) ──────────────────
    engine = get_engine()
    pos_dist = engine.get_pos_distribution(text)
    lf.pos_ratio = pos_dist.get("ratios", {})

    # ── v3.1 新增: 名词/动词比 + 虚词占比 ─────────────────────────────
    lf.noun_verb_ratio = engine.get_noun_verb_ratio(text)
    lf.function_word_ratio = engine.get_function_word_ratio(text)

    # ── POS bigram (v3.1: jieba 连续标注转移矩阵) ─────────────────────
    pos_bigram_result = engine.get_pos_bigram_entropy(text)
    lf.pos_bigram_entropy = pos_bigram_result.get("bigram_entropy", 0.0)
    lf.pos_bigram_top = [
        (bg, round(cnt, 4))
        for bg, cnt in pos_bigram_result.get("top_bigrams", [])[:20]
    ]

    # ── 词汇多样性 ────────────────────────────────────────────────────
    # 以字为单位（中文没有天然词边界）
    chars = [c for c in text if '一' <= c <= '鿿' or '㐀' <= c <= '䶿']
    total = len(chars)
    unique = len(set(chars))

    lf.unique_char_ratio = round(unique / max(total, 1), 4)

    # TTR (1000字窗口平均)
    ttr_values = []
    for i in range(0, total, 1000):
        window = chars[i:i + 1000]
        if len(window) < 500:
            continue
        window_unique = len(set(window))
        ttr_values.append(window_unique / len(window))
    lf.ttr = round(mean(ttr_values), 4) if ttr_values else 0

    # Yule's K
    freq_counter = Counter(chars)
    m1 = sum(freq_counter.values())
    if m1 > 0:
        m2 = sum(f * f for f in freq_counter.values())
        lf.yule_k = round(10000 * (m2 - m1) / (m1 * m1), 4) if m1 > 1 else 0

    # Hapax 单现词
    hapax_count = sum(1 for f in freq_counter.values() if f == 1)
    lf.hapax_ratio = round(hapax_count / max(total, 1), 4)

    # MTLD
    lf.mtld = _compute_mtld(chars)

    # ── 高频字偏好 Top-50 ─────────────────────────────────────────────
    lf.top_chars = [
        (ch, round(cnt / max(total, 1) * 1000, 4))
        for ch, cnt in freq_counter.most_common(50)
    ]

    return lf


def _classify_char(ch: str) -> str:
    """对单个字进行近似 POS 分类。"""
    if ch in "的地得了着过被把将以而与和或之所":
        return "AUX"
    if ch in "还就又才都只很更最非常已经正在一直总是终于仍然":
        return "ADV"
    if ch in "然而但却不过虽然如果因为所以于是而且或者只是甚至":
        return "CONJ" if len(ch) > 1 else "AUX"
    if ch in "他她它我你您们自己彼此":
        return "PRON"
    if ch in "一二三四五六七八九十百千万亿":
        return "NUM"
    if '一' <= ch <= '鿿':
        return "WORD"
    return ""


def _compute_mtld(chars: list[str], threshold: float = 0.72) -> float:
    """计算 MTLD (Measure of Textual Lexical Diversity)。"""
    if len(chars) < 100:
        return 0.0

    def _forward(seq, t):
        factors = 0.0
        seen = set()
        factor_len = 0
        for ch in seq:
            factor_len += 1
            seen.add(ch)
            ttr = len(seen) / factor_len
            if ttr < t:
                factors += 1.0
                seen.clear()
                factor_len = 0
        if factor_len > 0:
            factors += (1.0 - (len(seen) / factor_len)) / (1.0 - t)
        return len(seq) / factors if factors else len(seq)

    forward = _forward(chars, threshold)
    backward = _forward(list(reversed(chars)), threshold)
    return round((forward + backward) / 2, 2)


# ═══════════════════════════════════════════════════════════════════════════
# L2: Syntactic Extraction
# ═══════════════════════════════════════════════════════════════════════════


def _extract_syntactic(text: str) -> tuple[SyntacticFingerprint, list[int]]:
    """提取 L2 句级指纹。"""
    sf = SyntacticFingerprint()

    # ── 句长分布 ──────────────────────────────────────────────────────
    # 按句末标点分割
    sentences = re.split(r'[。！？!?\n]', text)
    sentence_lengths = [len(s.strip()) for s in sentences if len(s.strip()) > 1]
    raw_lengths = sentence_lengths[:]

    if sentence_lengths:
        sf.mean_sentence_len = round(mean(sentence_lengths), 1)
        sf.std_sentence_len = round(stdev(sentence_lengths), 1) if len(sentence_lengths) > 1 else 0
        sf.sentence_len_discreteness = round(
            sf.std_sentence_len / max(sf.mean_sentence_len, 1), 4
        )
        if len(sentence_lengths) >= 4:
            sf.sentence_len_quantiles = [
                round(q, 1) for q in quantiles(sentence_lengths, n=4)
            ][:3]  # p25, p50, p75
        else:
            sf.sentence_len_quantiles = [
                round(median(sentence_lengths), 1)
            ]

    # ── 标点密度谱 ────────────────────────────────────────────────────
    total_chars = len(text)
    for punct, name in PUNCTUATION_MAP.items():
        count = text.count(punct)
        if count > 0:
            sf.punctuation_spectrum[name] = round(
                count / max(total_chars, 1) * 1000, 4
            )
    sf.total_punctuation_ratio = round(
        sum(text.count(p) for p in PUNCTUATION_MAP) / max(total_chars, 1), 4
    )

    # ── 句式类型比 ────────────────────────────────────────────────────
    decl_count = text.count("。")
    excla_count = text.count("！") + text.count("!")
    interrog_count = text.count("？") + text.count("?")
    ellipsis_count = text.count("……") + text.count("...")
    total_sentence_ends = decl_count + excla_count + interrog_count + 1

    sf.declarative_ratio = round(decl_count / total_sentence_ends, 4)
    sf.exclamatory_ratio = round(excla_count / total_sentence_ends, 4)
    sf.interrogative_ratio = round(interrog_count / total_sentence_ends, 4)
    sf.ellipsis_density = round(ellipsis_count / max(total_chars, 1) * 1000, 4)

    # ── 从句嵌套 — 启发式 ─────────────────────────────────────────────
    sub_markers = ["因为", "所以", "如果", "虽然", "但是", "然而", "而且",
                   "并且", "不过", "尽管", "除非", "无论", "即使", "只要",
                   "当", "在……时", "……之后", "……之前"]
    sub_count = sum(text.count(m) for m in sub_markers)
    sf.subordination_ratio = round(sub_count / max(total_chars, 1) * 1000, 4)

    # 嵌套深度近似：逗号密度
    comma_count = text.count("，") + text.count(",")
    sf.avg_clause_depth = round(
        comma_count / max(len(sentence_lengths), 1), 2
    )

    return sf, raw_lengths


# ═══════════════════════════════════════════════════════════════════════════
# L3: Discourse Extraction
# ═══════════════════════════════════════════════════════════════════════════


def _extract_discourse(text: str) -> tuple[DiscourseFingerprint, list[int]]:
    """提取 L3 篇章指纹。"""
    df = DiscourseFingerprint()

    # ── 段落呼吸节奏 ──────────────────────────────────────────────────
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    para_lengths = [len(p) for p in paragraphs]
    raw_lengths = para_lengths[:]

    if para_lengths:
        df.mean_paragraph_len = round(mean(para_lengths), 1)
        df.std_paragraph_len = round(stdev(para_lengths), 1) if len(para_lengths) > 1 else 0
        df.paragraph_len_discreteness = round(
            df.std_paragraph_len / max(df.mean_paragraph_len, 1), 4
        )
    df.paragraph_len_distribution = para_lengths

    # ── 对话/叙述比 ───────────────────────────────────────────────────
    total_chars = len(text) + 1
    # 对话：中文引号内的内容
    dialogue_patterns = [
        r'「[^」]*」', r'『[^』]*』',
        r'“[^”]*”', r'‘[^’]*’',
        r'"[^"]*"',
    ]
    dialogue_chars = 0
    for pat in dialogue_patterns:
        for m in re.finditer(pat, text):
            dialogue_chars += len(m.group())

    df.dialogue_ratio = round(dialogue_chars / total_chars, 4)

    # 内心独白：括号内的心理描写
    inner_patterns = [
        r'（[^）]*想[^）]*）', r'\([^)]*想[^)]*\)',
        r'（[^）]*心[^）]*）', r'\([^)]*心[^)]*\)',
    ]
    inner_chars = 0
    for pat in inner_patterns:
        for m in re.finditer(pat, text):
            inner_chars += len(m.group())
    df.inner_monologue_ratio = round(inner_chars / total_chars, 4)

    df.narration_ratio = round(1 - df.dialogue_ratio - df.inner_monologue_ratio, 4)

    # ── 感官描写密度 ──────────────────────────────────────────────────
    for sense, words in SENSORY_WORDS.items():
        count = sum(text.count(w) for w in words)
        density = round(count / max(total_chars, 1) * 1000, 4)
        setattr(df, f"{sense}_density", density)

    df.total_sensory_density = round(
        df.visual_density + df.auditory_density + df.tactile_density +
        df.olfactory_density + df.gustatory_density, 4
    )

    # ── 过渡词偏好 ────────────────────────────────────────────────────
    transition_counts = Counter()
    for tw in TRANSITION_WORDS:
        cnt = text.count(tw)
        if cnt > 0:
            transition_counts[tw] = cnt

    df.transition_density = round(
        sum(transition_counts.values()) / max(total_chars, 1) * 1000, 4
    )
    df.top_transitions = transition_counts.most_common(10)

    return df, raw_lengths


# ═══════════════════════════════════════════════════════════════════════════
# L4: Narrative Extraction
# ═══════════════════════════════════════════════════════════════════════════


def _extract_narrative(text: str, chapters: list[dict]) -> NarrativeFingerprint:
    """提取 L4 叙事指纹。"""
    nf = NarrativeFingerprint()

    total_chars = len(text) + 1

    # ── 因果链密度 ────────────────────────────────────────────────────
    causality_count = sum(text.count(m) for m in CAUSALITY_MARKERS)
    nf.causality_marker_density = round(causality_count / max(total_chars, 1) * 1000, 4)

    # ── 伏笔密度 ──────────────────────────────────────────────────────
    foreshadowing_patterns = [
        "后来才知道", "直到后来", "很久以后", "那时还不",
        "当时并不", "彼时尚且", "多年后回想", "没想到的是",
        "隐隐感到", "莫名觉得", "似乎预示", "仿佛暗示",
    ]
    foreshadow_count = sum(text.count(p) for p in foreshadowing_patterns)
    nf.foreshadowing_density = round(foreshadow_count / max(total_chars, 1) * 1000, 4)

    # ── 视角切换频率 ──────────────────────────────────────────────────
    pov_count = sum(text.count(m) for m in POV_MARKERS)
    nf.pov_switch_frequency = round(pov_count / max(total_chars, 1) * 1000, 4)

    # ── 意象复用 ──────────────────────────────────────────────────────
    # 提取高频意象词（名词性词组）
    image_pattern = re.compile(r'(?:剑|刀|枪|花|树|山|河|海|星|月|日|风|雨|雪|雾|云|火|冰|雷|光|影|血|泪|梦|魂)')
    images = image_pattern.findall(text)
    image_counter = Counter(images)
    nf.top_images = image_counter.most_common(15)

    # 意象复用间隔
    if len(images) > 1:
        positions = {}
        intervals = []
        for i, img in enumerate(images):
            if img in positions:
                intervals.append(i - positions[img])
            positions[img] = i
        nf.image_reuse_interval_mean = round(mean(intervals), 1) if intervals else 0

    # ── 幕结构：逐章紧张度曲线 ────────────────────────────────────────
    for ch in chapters[:50]:  # 最多前50章
        txt = ch.get("text", "")
        if len(txt) < 100:
            continue
        # 紧张度 = 短句比例 + 感叹号密度 + 因果词密度 + 战斗词密度
        short_sent_ratio = sum(1 for s in re.split(r'[。！？!?\n]', txt)
                               if 1 < len(s.strip()) <= 15) / max(len(re.split(r'[。！？!?\n]', txt)), 1)
        excla_density = txt.count("！") / max(len(txt), 1)
        battle_words = sum(txt.count(w) for w in ["攻击", "战斗", "杀", "死", "爆发", "轰", "剑", "斩"])
        battle_density = battle_words / max(len(txt), 1) * 1000
        tension = round(short_sent_ratio * 0.3 + excla_density * 100 * 0.3
                        + min(battle_density / 10, 1) * 0.4, 4)
        nf.chapter_tension_curve.append(tension)

    # ── v3.3：叙事增强 ────────────────────────────────────────────
    try:
        from .narrative_analyzer import get_analyzer as _get_narr_ana
        ana = _get_narr_ana()
        act_result = ana.detect_act_structure(text, num_acts=3)
        nf.act_coherence = act_result.act_coherence
        nf.climax_position = act_result.climax_position

        causal_result = ana.extract_causal_chain(text)
        nf.causal_density = causal_result.causal_density
    except Exception:
        pass

    return nf


def _extract_chapter_brief(text: str, num: int, title: str) -> dict:
    """逐章简要指纹（用于漂移追踪）。"""
    chars = len(text)
    sentences = re.split(r'[。！？!?\n]', text)
    sent_lens = [len(s.strip()) for s in sentences if len(s.strip()) > 1]

    dialogue_chars = sum(
        len(m.group()) for pat in [r'「[^」]*」', r'"[^"]*"']
        for m in re.finditer(pat, text)
    )

    return {
        "chapter": num,
        "title": title,
        "chars": chars,
        "mean_sentence_len": round(mean(sent_lens), 1) if sent_lens else 0,
        "std_sentence_len": round(stdev(sent_lens), 1) if len(sent_lens) > 1 else 0,
        "dialogue_ratio": round(dialogue_chars / max(chars, 1), 4),
        "exclamatory_ratio": round(text.count("！") / max(len(sentences), 1), 4),
        "punctuation_ratio": round(
            sum(text.count(p) for p in PUNCTUATION_MAP) / max(chars, 1), 4
        ),
        "function_word_density": round(
            sum(text.count(fw) for fw in FUNCTION_WORDS[:20]) / max(chars, 1) * 1000, 2
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Style Drift Detection
# ═══════════════════════════════════════════════════════════════════════════


def detect_style_drift(
    chapter_text: str,
    baseline: StyleFingerprint = None,
    chapter_number: int = 1,
    threshold: float = 0.15,
    genre: str = "",
) -> StyleDriftResult:
    """检测单章相对基线的风格漂移。

    Args:
        chapter_text: 待检测章节文本
        baseline: 基线风格指纹（从原作多章提取）。为 None 时可通过 genre 自动加载预置基线。
        chapter_number: 章节编号
        threshold: 单维度漂移阈值（相对偏差超过此值标记）
        genre: 体裁名称（如 "xianxia_modern"、"xuanhuan"）。当 baseline 未提供时自动加载预置基线。

    Returns:
        StyleDriftResult 含三维评分及逐维漂移详情
    """
    # 自动加载预置基线
    if baseline is None and genre:
        from .baselines import load_genre_baseline
        baseline_dict = load_genre_baseline(genre)
        baseline = _dict_to_fingerprint(baseline_dict)

    if baseline is None:
        raise ValueError("必须提供 baseline 或 genre 参数来指定风格基线。")

    ch_fp = extract_style_fingerprint(
        chapter_text,
        novel_name=baseline.novel_name,
        genre=baseline.genre,
    )

    drift_dims = _compare_dimensions(ch_fp, baseline, threshold)

    # 计算四层风格保真度（SI）
    layer_fidelities = []
    for layer_name, dims in _group_dims_by_layer(drift_dims).items():
        if dims:
            layer_fidelity = sum(d["fidelity"] for d in dims) / len(dims)
        else:
            layer_fidelity = 1.0
        layer_fidelities.append(layer_fidelity)

    style_fidelity = round(sum(layer_fidelities) / max(len(layer_fidelities), 1), 4)

    # 内容独立性（SP）：情节不同但风格应保持 → 基于标点/虚词/句长等表面特征
    surface_dims = [d for d in drift_dims
                    if d["dimension"] in {"虚词谱", "标点谱", "句长分布", "句式比", "段落节奏"}]
    content_independence = round(
        sum(d["fidelity"] for d in surface_dims) / max(len(surface_dims), 1), 4
    ) if surface_dims else 1.0

    # 流畅度（FS）：基于对话比/感官密度的自然范围
    fluency_dims = [d for d in drift_dims
                    if d["dimension"] in {"对话比", "感官密度", "过渡词密度"}]
    fluency = round(
        sum(d["fidelity"] for d in fluency_dims) / max(len(fluency_dims), 1), 4
    ) if fluency_dims else 1.0

    # 总体真实度 OA = SI × SP × FS
    overall = round(style_fidelity * content_independence * fluency, 4)

    passed = overall >= (1 - threshold)

    return StyleDriftResult(
        passed=passed,
        overall_authenticity=overall,
        style_fidelity=style_fidelity,
        content_independence=content_independence,
        fluency=fluency,
        drift_dimensions=drift_dims,
        chapter_fingerprint=ch_fp,
    )


def detect_cross_chapter_drift(
    chapters: list[dict],
    baseline: StyleFingerprint = None,
    threshold: float = 0.15,
    genre: str = "",
) -> list[StyleDriftResult]:
    """跨章漂移追踪 — 逐章检测风格偏移，输出趋势。

    Args:
        chapters: [{"chapter_number": 1, "text": "...", "title": "..."}, ...]
        baseline: 基线风格指纹。为 None 时可通过 genre 自动加载预置基线。
        threshold: 漂移阈值
        genre: 体裁名称（如 "xianxia_modern"、"xuanhuan"）。baseline 未提供时自动加载预置基线。

    Returns:
        每章一个 StyleDriftResult，可绘制趋势图
    """
    # 自动加载预置基线
    if baseline is None and genre:
        from .baselines import load_genre_baseline
        baseline_dict = load_genre_baseline(genre)
        baseline = _dict_to_fingerprint(baseline_dict)

    if baseline is None:
        raise ValueError("必须提供 baseline 或 genre 参数来指定风格基线。")

    results = []
    for ch in chapters:
        result = detect_style_drift(
            chapter_text=ch.get("text", ""),
            baseline=baseline,
            chapter_number=ch.get("chapter_number", ch.get("chapter", 0)),
            threshold=threshold,
        )
        results.append(result)
    return results


# ═══════════════════════════════════════════════════════════════════════════
# Style Comparison
# ═══════════════════════════════════════════════════════════════════════════


def compare_style_fingerprints(
    target: StyleFingerprint,
    reference: StyleFingerprint,
    detailed: bool = True,
    dl: bool = False,
) -> dict:
    """对比两个风格指纹，逐维度分析差异。

    支持参数扫描（stylo 思想）：计算多个特征窗口的稳定性。
    dl=True 且 DL 引擎可用时，使用嵌入余弦相似度作为主要评估指标。
    """
    # ── v4.0: DL 增强路径 ─────────────────────────────────────────────
    dl_similarity = None
    if dl:
        engine = get_dl_engine()
        if engine.is_available():
            # 如果指纹已包含 DL 嵌入则直接用，否则不额外编码（指纹提取时才编码）
            if target.dl_embedding and reference.dl_embedding:
                dl_similarity = engine._cosine_similarity(
                    target.dl_embedding, reference.dl_embedding
                )
                dl_similarity = round(dl_similarity, 4)

    dims = _compare_dimensions(target, reference, threshold=0.10)

    # 按层汇总
    by_layer = _group_dims_by_layer(dims)

    layer_scores = {}
    for layer, dim_list in by_layer.items():
        if dim_list:
            layer_scores[layer] = round(
                sum(d["fidelity"] for d in dim_list) / len(dim_list), 4
            )
        else:
            layer_scores[layer] = 1.0

    overall_similarity = round(
        sum(layer_scores.values()) / max(len(layer_scores), 1), 4
    )

    # v4.0: DL 相似度与规则相似度融合
    if dl_similarity is not None:
        # 融合权重：DL 嵌入捕获深层语义，规则捕获表面特征
        overall_similarity = round(overall_similarity * 0.4 + dl_similarity * 0.6, 4)

    result = {
        "target": target.novel_name,
        "reference": reference.novel_name,
        "overall_similarity": overall_similarity,
        "layer_scores": layer_scores,
        "top_deviations": sorted(dims, key=lambda d: d["deviation"])[:10],
    }

    if detailed:
        result["all_dimensions"] = dims

    if dl_similarity is not None:
        result["dl_similarity"] = dl_similarity
        result["dl_enhanced"] = True

    return result


def compare_style_to_reference(
    target_text: str,
    reference_text: str,
    target_name: str = "target",
    reference_name: str = "reference",
    dl: bool = False,
) -> dict:
    """便捷方法：两段文本直接比较风格相似度。

    dl=True 时使用 DL 嵌入余弦相似度增强评估。
    """
    ref_fp = extract_style_fingerprint(reference_text, novel_name=reference_name, dl=dl)
    tgt_fp = extract_style_fingerprint(target_text, novel_name=target_name, dl=dl)
    return compare_style_fingerprints(tgt_fp, ref_fp, dl=dl)


# ═══════════════════════════════════════════════════════════════════════════
# Multi-baseline support
# ═══════════════════════════════════════════════════════════════════════════


def build_baseline_from_chapters(
    chapters: list[dict],
    novel_name: str = "baseline",
    author: str = "",
    genre: str = "xianxia_modern",
    sample_size: int = 10,
    dl_mode: bool = False,
) -> StyleFingerprint:
    """从多个章节构建稳定的风格基线。

    关键设计（吸收 stylo 参数扫描思想）：
    - 选取多章 → 每章独立提取指纹 → 取中位数聚合
    - 排除异常章（句长/对话比离群超过 2σ）
    - dl_mode=True 时同时计算 DL 嵌入向量
    """
    if len(chapters) > sample_size:
        # 均匀采样
        step = max(1, len(chapters) // sample_size)
        sampled = chapters[::step][:sample_size]
    else:
        sampled = chapters

    # 逐章提取
    chapter_fps = []
    for ch in sampled:
        text = ch.get("text", "")
        if len(text) < 200:
            continue
        fp = extract_style_fingerprint(text, novel_name=novel_name, genre=genre)
        chapter_fps.append(fp)

    if not chapter_fps:
        return StyleFingerprint(novel_name=novel_name)

    # 合并（取中位数聚合）
    combined = _merge_fingerprints(chapter_fps, novel_name, author, genre)
    return combined


# ═══════════════════════════════════════════════════════════════════════════
# Style Dashboard
# ═══════════════════════════════════════════════════════════════════════════


def generate_style_dashboard(
    fp: StyleFingerprint,
    reference: StyleFingerprint = None,
) -> dict:
    """生成风格仪表板数据（用于前端雷达图/趋势图/散点图）。

    输出格式适配 ECharts / Chart.js 渲染。
    """
    dashboard = {
        "radar": _build_radar_data(fp, reference),
        "sentence_rhythm_histogram": _build_histogram(fp.raw_sentence_lengths, bins=10),
        "paragraph_rhythm_chart": fp.discourse.paragraph_len_distribution[:80],
        "dialogue_pie": {
            "dialogue": fp.discourse.dialogue_ratio,
            "narration": fp.discourse.narration_ratio,
            "inner_monologue": fp.discourse.inner_monologue_ratio,
        },
        "punctuation_heatmap": fp.syntactic.punctuation_spectrum,
        "chapter_tension_curve": fp.narrative.chapter_tension_curve,
        "sensory_radar": {
            "视觉": fp.discourse.visual_density,
            "听觉": fp.discourse.auditory_density,
            "触觉": fp.discourse.tactile_density,
            "嗅觉": fp.discourse.olfactory_density,
            "味觉": fp.discourse.gustatory_density,
        },
        "top_chars": dict(fp.lexical.top_chars[:20]),
        "top_function_words": dict(fp.lexical.top_function_words),
    }

    if reference:
        comparison = compare_style_fingerprints(fp, reference, detailed=False)
        dashboard["comparison"] = comparison

    return dashboard


# ═══════════════════════════════════════════════════════════════════════════
# ── 向后兼容：保留旧 API ──────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════


# 保留旧 Fingerprint 类定义
class Fingerprint:
    """一本书的旧版风格指纹（向后兼容）。"""

    def __init__(self, data: dict[str, Any]):
        self.data = data

    @property
    def novel_name(self) -> str:
        return self.data.get("novel", "")

    @property
    def genre(self) -> str:
        return self.data.get("genre", "xianxia_modern")

    @property
    def metrics(self) -> dict:
        return self.data.get("profile", {})

    def to_dict(self) -> dict:
        return self.data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.data, ensure_ascii=False, indent=indent)

    def save(self, path: str):
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @staticmethod
    def load(path: str) -> "Fingerprint":
        return Fingerprint(json.loads(Path(path).read_text(encoding="utf-8")))


# 保留旧 extract_fingerprint 签名
def extract_fingerprint(
    text: str,
    novel_name: str = "unknown",
    genre: str = "xianxia_modern",
    author: str = "",
) -> Fingerprint:
    """旧版风格指纹提取（向后兼容）。内部调用新版引擎。"""
    fp = extract_style_fingerprint(
        text, novel_name=novel_name, author=author, genre=genre
    )

    # 转换为旧版 Fingerprint 格式
    d = fp.to_dict()
    profile = {
        "avg_gap_density": 0,
        "avg_touchpoints": 0,
        "avg_emotion_ratio": 0,
        "scene_flip_rate": 0,
        "avg_hook_position": 0,
        "avg_dialogue_density": d["L3_discourse"]["mode_ratio"]["dialogue"],
        "avg_chapter_length": d["meta"]["total_chars"] // max(d["meta"]["chapter_count"], 1),
        "chapter_count": d["meta"]["chapter_count"],
        "total_chars": d["meta"]["total_chars"],
        "avg_sentence_length": d["L2_syntactic"]["sentence_length"]["mean"],
        "vocabulary_diversity": d["L1_lexical"]["diversity"]["unique_char_ratio"],
        "unique_char_count": 0,
    }

    # 从新版数据补充旧版字段
    l1 = d["L1_lexical"]
    l3 = d["L3_discourse"]

    # 使用原有 analyzer 获取鸿沟密度等补充指标
    try:
        ch_result = analyzer.analyze_chapter(text, 0, novel_name)
        profile.update({
            "avg_gap_density": ch_result.get("gap_density", 0),
            "avg_touchpoints": ch_result.get("touchpoints", 0),
            "avg_emotion_ratio": ch_result.get("emotion_to_touchpoint_ratio", 0),
            "scene_flip_rate": 1.0 if ch_result.get("scene_flipped") else 0,
            "avg_hook_position": ch_result.get("first_hook_position", 0),
        })
    except Exception:
        pass

    # 发现模式
    patterns = _discover_patterns_v2(fp)

    return Fingerprint({
        "novel": novel_name,
        "author": author,
        "genre": genre,
        "profile": profile,
        "patterns": patterns,
        "chapter_count": d["meta"]["chapter_count"],
        "_style_fingerprint": d,  # 嵌入新版完整指纹
    })


def save_fingerprint(fp: Fingerprint, path: str):
    fp.save(path)


def load_fingerprint(path: str) -> Fingerprint:
    return Fingerprint.load(path)


def list_available_fingerprints(bench_dir: str = None) -> list[dict]:
    if bench_dir is None:
        bench_dir = str(Path.home() / ".wenjian" / "benchmarks")
    bench_path = Path(bench_dir)
    if not bench_path.exists():
        return []
    fingerprints = []
    for f in bench_path.glob("*.fingerprint"):
        try:
            fp = Fingerprint.load(str(f))
            fingerprints.append({
                "novel": fp.novel_name,
                "author": fp.data.get("author", ""),
                "genre": fp.genre,
                "chapters": fp.data.get("chapter_count", 0),
                "path": str(f),
            })
        except Exception:
            continue
    return fingerprints


# ═══════════════════════════════════════════════════════════════════════════
# ── 内部工具函数 ──────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════


def _split_chapters(text: str) -> list[dict]:
    """分割章节。"""
    # Markdown headers
    headers = list(re.finditer(r'^#{1,3}\s+.+$', text, re.MULTILINE))
    chapters = []
    if len(headers) >= 3:
        for i, m in enumerate(headers):
            start = m.start()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            ch_text = text[start:end].strip()
            if len(ch_text) > 100:
                chapters.append({"title": m.group().strip("# "), "text": ch_text})

    # 中文章节模式
    if len(chapters) < 2:
        chapter_pattern = re.compile(r'(第[一二三四五六七八九十百千万\d]+[章节部回])')
        headers_cn = list(chapter_pattern.finditer(text))
        if len(headers_cn) >= 2:
            chapters = []
            for i, m in enumerate(headers_cn):
                start = m.start()
                end = headers_cn[i + 1].start() if i + 1 < len(headers_cn) else len(text)
                ch_text = text[start:end].strip()
                if len(ch_text) > 100:
                    chapters.append({"title": m.group(1).strip(), "text": ch_text})

    if not chapters and len(text) > 100:
        chapters = [{"title": "全文", "text": text[:20000]}]
    return chapters


def _compare_dimensions(
    target: StyleFingerprint,
    baseline: StyleFingerprint,
    threshold: float = 0.15,
) -> list[dict]:
    """逐维度对比两个指纹。"""
    dims = []

    t = target
    b = baseline

    # L1 词汇
    _add_dim(dims, "L1", "虚词谱", _dict_cosine(t.lexical.function_word_spectrum,
                                                 b.lexical.function_word_spectrum), threshold)
    _add_dim(dims, "L1", "词汇多样性", _ratio_fidelity(t.lexical.ttr, b.lexical.ttr), threshold)
    _add_dim(dims, "L1", "高频字偏好", _list_overlap(t.lexical.top_chars, b.lexical.top_chars), threshold)
    _add_dim(dims, "L1", "词性比例", _dict_cosine(t.lexical.pos_ratio, b.lexical.pos_ratio), threshold)

    # L2 句法
    _add_dim(dims, "L2", "句长分布", _ratio_fidelity(t.syntactic.mean_sentence_len,
                                                       b.syntactic.mean_sentence_len), threshold)
    _add_dim(dims, "L2", "句长离散度", _ratio_fidelity(t.syntactic.sentence_len_discreteness,
                                                          b.syntactic.sentence_len_discreteness), threshold)
    _add_dim(dims, "L2", "标点谱", _dict_cosine(t.syntactic.punctuation_spectrum,
                                                 b.syntactic.punctuation_spectrum), threshold)
    _add_dim(dims, "L2", "句式比", _ratio_fidelity(t.syntactic.declarative_ratio,
                                                    b.syntactic.declarative_ratio), threshold)
    _add_dim(dims, "L2", "感叹密度", _ratio_fidelity(t.syntactic.exclamatory_ratio,
                                                       b.syntactic.exclamatory_ratio), threshold)

    # L3 篇章
    _add_dim(dims, "L3", "段落节奏", _ratio_fidelity(t.discourse.mean_paragraph_len,
                                                       b.discourse.mean_paragraph_len), threshold)
    _add_dim(dims, "L3", "对话比", _ratio_fidelity(t.discourse.dialogue_ratio,
                                                    b.discourse.dialogue_ratio), threshold)
    _add_dim(dims, "L3", "感官密度", _ratio_fidelity(t.discourse.total_sensory_density,
                                                       b.discourse.total_sensory_density), threshold)
    _add_dim(dims, "L3", "过渡词密度", _ratio_fidelity(t.discourse.transition_density,
                                                         b.discourse.transition_density), threshold)

    # L4 叙事
    _add_dim(dims, "L4", "因果链密度", _ratio_fidelity(t.narrative.causality_marker_density,
                                                         b.narrative.causality_marker_density), threshold)
    _add_dim(dims, "L4", "视角切换频率", _ratio_fidelity(t.narrative.pov_switch_frequency,
                                                           b.narrative.pov_switch_frequency), threshold)

    return dims


def _add_dim(dims: list, layer: str, name: str, fidelity: float, threshold: float):
    deviation = 1.0 - fidelity
    dims.append({
        "layer": layer,
        "dimension": name,
        "fidelity": round(fidelity, 4),
        "deviation": round(deviation, 4),
        "drifted": deviation > threshold,
    })


def _ratio_fidelity(a: float, b: float) -> float:
    """两个值的比例保真度。a=0 且 b=0 时返回 1.0。"""
    if a == 0 and b == 0:
        return 1.0
    if a == 0 or b == 0:
        return 0.0
    ratio = min(a, b) / max(a, b)
    return ratio


def _dict_cosine(a: dict, b: dict) -> float:
    """两个字典的余弦相似度。"""
    keys = set(a.keys()) | set(b.keys())
    if not keys:
        return 1.0
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    cos = dot / (norm_a * norm_b)
    return max(0.0, min(1.0, cos))


def _list_overlap(a: list[tuple], b: list[tuple], top_n: int = 20) -> float:
    """两个 Top-N 列表的重叠度。"""
    a_set = set(item[0] for item in a[:top_n])
    b_set = set(item[0] for item in b[:top_n])
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


def _group_dims_by_layer(dims: list[dict]) -> dict:
    """按层分组维度。"""
    groups = {"L1": [], "L2": [], "L3": [], "L4": []}
    for d in dims:
        groups[d["layer"]].append(d)
    return groups


def _merge_fingerprints(
    fps: list[StyleFingerprint],
    novel_name: str,
    author: str,
    genre: str,
) -> StyleFingerprint:
    """合并多个指纹（取中位数聚合，排除异常值）。"""
    if not fps:
        return StyleFingerprint(novel_name=novel_name)

    merged = StyleFingerprint(
        novel_name=novel_name,
        author=author,
        genre=genre,
        total_chars=sum(fp.total_chars for fp in fps),
        chapter_count=sum(fp.chapter_count for fp in fps),
    )

    # L1: 词汇
    for key in merged.lexical.pos_ratio:
        values = [fp.lexical.pos_ratio.get(key, 0) for fp in fps]
        merged.lexical.pos_ratio[key] = _robust_mean(values)

    merged.lexical.ttr = _robust_mean([fp.lexical.ttr for fp in fps])
    merged.lexical.yule_k = _robust_mean([fp.lexical.yule_k for fp in fps])
    merged.lexical.hapax_ratio = _robust_mean([fp.lexical.hapax_ratio for fp in fps])
    merged.lexical.unique_char_ratio = _robust_mean([fp.lexical.unique_char_ratio for fp in fps])

    # 虚词谱合并
    all_fw = set()
    for fp in fps:
        all_fw.update(fp.lexical.function_word_spectrum.keys())
    for fw in all_fw:
        values = [fp.lexical.function_word_spectrum.get(fw, 0) for fp in fps]
        merged.lexical.function_word_spectrum[fw] = _robust_mean(values)
    merged.lexical.top_function_words = sorted(
        merged.lexical.function_word_spectrum.items(), key=lambda x: x[1], reverse=True
    )[:20]

    # L2: 句法
    merged.syntactic.mean_sentence_len = _robust_mean(
        [fp.syntactic.mean_sentence_len for fp in fps]
    )
    merged.syntactic.std_sentence_len = _robust_mean(
        [fp.syntactic.std_sentence_len for fp in fps]
    )
    merged.syntactic.total_punctuation_ratio = _robust_mean(
        [fp.syntactic.total_punctuation_ratio for fp in fps]
    )

    all_punct = set()
    for fp in fps:
        all_punct.update(fp.syntactic.punctuation_spectrum.keys())
    for p in all_punct:
        values = [fp.syntactic.punctuation_spectrum.get(p, 0) for fp in fps]
        merged.syntactic.punctuation_spectrum[p] = _robust_mean(values)

    merged.syntactic.declarative_ratio = _robust_mean(
        [fp.syntactic.declarative_ratio for fp in fps]
    )
    merged.syntactic.exclamatory_ratio = _robust_mean(
        [fp.syntactic.exclamatory_ratio for fp in fps]
    )
    merged.syntactic.interrogative_ratio = _robust_mean(
        [fp.syntactic.interrogative_ratio for fp in fps]
    )

    # L3: 篇章
    merged.discourse.mean_paragraph_len = _robust_mean(
        [fp.discourse.mean_paragraph_len for fp in fps]
    )
    merged.discourse.dialogue_ratio = _robust_mean(
        [fp.discourse.dialogue_ratio for fp in fps]
    )
    merged.discourse.total_sensory_density = _robust_mean(
        [fp.discourse.total_sensory_density for fp in fps]
    )
    merged.discourse.transition_density = _robust_mean(
        [fp.discourse.transition_density for fp in fps]
    )

    # L4: 叙事
    merged.narrative.causality_marker_density = _robust_mean(
        [fp.narrative.causality_marker_density for fp in fps]
    )
    merged.narrative.pov_switch_frequency = _robust_mean(
        [fp.narrative.pov_switch_frequency for fp in fps]
    )

    return merged


def _robust_mean(values: list[float]) -> float:
    """鲁棒均值（排除 2σ 外的异常值）。"""
    if not values:
        return 0.0
    if len(values) <= 2:
        return round(mean(values), 4)
    m = mean(values)
    s = stdev(values) if len(values) > 1 else 0
    if s == 0:
        return round(m, 4)
    filtered = [v for v in values if abs(v - m) <= 2 * s]
    return round(mean(filtered), 4) if filtered else round(m, 4)


def _dict_to_fingerprint(d: dict) -> StyleFingerprint:
    """从字典反序列化 StyleFingerprint。"""
    fp = StyleFingerprint()
    meta = d.get("meta", {})
    fp.novel_name = meta.get("novel", "")
    fp.author = meta.get("author", "")
    fp.genre = meta.get("genre", "")
    fp.total_chars = meta.get("total_chars", 0)
    fp.chapter_count = meta.get("chapter_count", 0)

    l1 = d.get("L1_lexical", {})
    fp.lexical.function_word_spectrum = l1.get("function_word_spectrum", {})
    fp.lexical.top_function_words = l1.get("top_function_words", [])
    fp.lexical.pos_bigram_top = l1.get("pos_bigram_top", [])
    fp.lexical.pos_bigram_entropy = l1.get("pos_bigram_entropy", 0.0)
    fp.lexical.noun_verb_ratio = l1.get("noun_verb_ratio", 0.0)
    fp.lexical.function_word_ratio = l1.get("function_word_ratio", 0.0)
    fp.lexical.pos_ratio = l1.get("pos_ratio", {})
    div = l1.get("diversity", {})
    fp.lexical.ttr = div.get("ttr", 0)
    fp.lexical.mtld = div.get("mtld", 0)
    fp.lexical.yule_k = div.get("yule_k", 0)
    fp.lexical.hapax_ratio = div.get("hapax_ratio", 0)
    fp.lexical.unique_char_ratio = div.get("unique_char_ratio", 0)
    fp.lexical.top_chars = l1.get("top_chars", [])

    l2 = d.get("L2_syntactic", {})
    sl = l2.get("sentence_length", {})
    fp.syntactic.mean_sentence_len = sl.get("mean", 0)
    fp.syntactic.std_sentence_len = sl.get("std", 0)
    fp.syntactic.sentence_len_discreteness = sl.get("discreteness", 0)
    fp.syntactic.punctuation_spectrum = l2.get("punctuation_spectrum", {})
    fp.syntactic.total_punctuation_ratio = l2.get("total_punctuation_ratio", 0)
    st = l2.get("sentence_types", {})
    fp.syntactic.declarative_ratio = st.get("declarative", 0)
    fp.syntactic.interrogative_ratio = st.get("interrogative", 0)
    fp.syntactic.exclamatory_ratio = st.get("exclamatory", 0)

    l3 = d.get("L3_discourse", {})
    pr = l3.get("paragraph_rhythm", {})
    fp.discourse.mean_paragraph_len = pr.get("mean_len", 0)
    mr = l3.get("mode_ratio", {})
    fp.discourse.dialogue_ratio = mr.get("dialogue", 0)
    fp.discourse.narration_ratio = mr.get("narration", 0)
    fp.discourse.inner_monologue_ratio = mr.get("inner_monologue", 0)
    sd = l3.get("sensory_density", {})
    fp.discourse.visual_density = sd.get("visual", 0)
    fp.discourse.auditory_density = sd.get("auditory", 0)
    fp.discourse.tactile_density = sd.get("tactile", 0)
    fp.discourse.olfactory_density = sd.get("olfactory", 0)
    fp.discourse.gustatory_density = sd.get("gustatory", 0)
    fp.discourse.total_sensory_density = sd.get("total", 0)
    tr = l3.get("transitions", {})
    fp.discourse.transition_density = tr.get("density", 0)

    l4 = d.get("L4_narrative", {})
    fp.narrative.causality_marker_density = l4.get("causality_density", 0)
    fp.narrative.foreshadowing_density = l4.get("foreshadowing_density", 0)
    fp.narrative.pov_switch_frequency = l4.get("pov_switch_freq", 0)

    fp.nlp_quality = d.get("nlp_quality", {})

    return fp


def _discover_patterns_v2(fp: StyleFingerprint) -> list[str]:
    """从新版指纹发现叙事模式。"""
    patterns = []

    dd = fp.discourse.dialogue_ratio
    if dd > 0.4:
        patterns.append("对话驱动型：对话占比 > 40%")
    elif dd > 0.2:
        patterns.append("对话描写均衡型")
    else:
        patterns.append("描写为主型：对话占比较低")

    sl = fp.syntactic.mean_sentence_len
    if sl > 40:
        patterns.append(f"长句风格：平均句长 {sl:.0f} 字")
    elif sl < 20:
        patterns.append(f"短句风格：平均句长 {sl:.0f} 字，节奏明快")
    else:
        patterns.append(f"中句风格：平均句长 {sl:.0f} 字")

    sd = fp.syntactic.sentence_len_discreteness
    if sd > 0.8:
        patterns.append("句长变化丰富：节奏感强")
    elif sd < 0.4:
        patterns.append("句长稳定：风格统一")

    ex = fp.syntactic.exclamatory_ratio
    if ex > 0.15:
        patterns.append("高情感密度：感叹句比例偏高")
    elif ex < 0.05:
        patterns.append("内敛风格：感叹句比例偏低")

    sensory = fp.discourse.total_sensory_density
    if sensory > 15:
        patterns.append("感官丰富型：五感描写密度高")
    elif sensory < 5:
        patterns.append("白描风格：感官描写较少")

    return patterns


def _build_radar_data(fp: StyleFingerprint, reference: StyleFingerprint = None) -> dict:
    """构建雷达图数据。"""
    indicators = [
        ("虚词丰富度", fp.lexical.hapax_ratio * 100),
        ("词汇多样性", fp.lexical.ttr * 100),
        ("句长节奏", min(fp.syntactic.sentence_len_discreteness * 100, 100)),
        ("标点密度", fp.syntactic.total_punctuation_ratio * 100),
        ("对话占比", fp.discourse.dialogue_ratio * 100),
        ("感官描写", min(fp.discourse.total_sensory_density / 0.2 * 100, 100)),
    ]
    return {"indicators": [{"name": n, "value": round(v, 1)} for n, v in indicators]}


def _build_histogram(values: list[int], bins: int = 10) -> dict:
    """构建直方图数据。"""
    if not values:
        return {"bins": [], "counts": []}
    min_v, max_v = min(values), max(values)
    if min_v == max_v:
        return {"bins": [min_v], "counts": [len(values)]}

    step = (max_v - min_v) / bins
    hist_bins = []
    hist_counts = []
    for i in range(bins):
        lo = min_v + i * step
        hi = min_v + (i + 1) * step
        count = sum(1 for v in values if lo <= v < hi)
        if count > 0:
            hist_bins.append(round((lo + hi) / 2, 1))
            hist_counts.append(count)

    return {"bins": hist_bins, "counts": hist_counts}