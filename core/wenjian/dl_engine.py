"""文鉴 DLEngine — 深度学习风格嵌入增强层 (v4.0)

核心理念：
  深度学习是增强层（可选），纯规则模式始终可用。
  安装 sentence-transformers 后自动激活 DL 模式，否则优雅降级到 TF-IDF 特征向量。

可选安装：
  pip install sentence-transformers

  推荐的模型（按优先级）：
  1. paraphrase-multilingual-MiniLM-L12-v2  — 384 维，轻量级，支持中文，首选
  2. paraphrase-multilingual-mpnet-base-v2  — 768 维，更准确但更重
  3. distiluse-base-multilingual-cased-v2    — 512 维，备选

架构：
  - 懒加载：首次调用 encode_style() 时才 import torch/transformers
  - 回退链：sentence-transformers → TF-IDF 特征向量
  - 单例模式：get_dl_engine() 全局复用

参考：
  - Reimers & Gurevych (2019) "Sentence-BERT"
  - 中文风格嵌入：BERT 中文风格分类微调
  - stylo 参数扫描：多窗口嵌入稳定性

Author: WenJian v4.0
"""

from __future__ import annotations
import math
import logging
from typing import Optional, Any
from collections import Counter

logger = logging.getLogger("wenjian.dl_engine")

# ═══════════════════════════════════════════════════════════════════════════
# 品类基线文本 — 用于 genre_classify 的对比嵌入
# ═══════════════════════════════════════════════════════════════════════════

GENRE_BASELINE_TEXTS = {
    "xianxia_modern": (
        "修炼之道，逆天而行。灵气如潮水般涌入丹田，经脉之中传来撕裂般的剧痛。"
        "他咬紧牙关，运转功法，周身金光大盛。筑基成功！周围的修士纷纷倒吸一口凉气。"
        "剑光如虹，斩破苍穹。这一剑，蕴含着他对天道的全部感悟。"
    ),
    "xuanhuan": (
        "魔法阵在脚下旋转，古老的符文从虚空中浮现。精灵族的弓箭手拉满长弓，"
        "箭尖凝聚着月华之力。龙骑士驾驭着银翼巨龙掠过城堡上空，龙息将黑暗军团化为灰烬。"
        "这是诸神的黄昏，也是新纪元的黎明。"
    ),
    "lishi": (
        "建安十三年冬，曹操率八十万大军南下，旌旗蔽日，战船千里。"
        "诸葛亮立于江畔，羽扇轻摇，笑看江风。赤壁之上，周瑜抚琴而歌，豪气干云。"
        "历史的洪流中，每个人都不过是沧海一粟。"
    ),
    "dushi": (
        "电梯门缓缓打开，林总监踩着高跟鞋走进办公室，玻璃幕墙外的 CBD 灯火通明。"
        "她打开笔记本，屏幕上跳动着最新的股价曲线。凌晨三点的会议室里，"
        "只剩下她和那杯早已凉透的美式咖啡。这个项目，只许成功，不许失败。"
    ),
    "yanqing": (
        "那年樱花树下，他轻轻拂去她发间的花瓣。四目相对的一瞬间，"
        "整个世界都安静了下来。心跳声在胸膛里回荡，像是春天的第一声雷鸣。"
        "她低下头，脸烧得发烫，却忍不住偷偷抬眼，从睫毛的缝隙里望向他。"
    ),
    "xuanyi": (
        "深夜的档案室，手电筒的光柱扫过落满灰尘的卷宗。她翻开那本泛黄的日记，"
        "一股寒意从脊柱窜上后脑。三十年前失踪的女孩，字迹竟然和自己的如此相似。"
        "身后传来门轴转动的声响，她缓缓转过身——门已经打开了一条缝。"
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# DLEngine
# ═══════════════════════════════════════════════════════════════════════════


class DLEngine:
    """深度学习风格嵌入引擎。

    懒加载设计：仅在首次使用时才导入 torch / transformers，避免启动延迟。
    回退策略：sentence-transformers 不可用时自动降级到 TF-IDF 特征向量。

    Attributes:
        _model: sentence-transformers 模型实例（懒加载）
        _model_name: 已加载的模型名称
        _embedding_dim: 嵌入向量维度
        _available: DL 是否完全可用
        _tried_import: 是否已尝试导入 DL 依赖
        _tfidf_vectorizer: TF-IDF 回退向量化器
        _tfidf_idf: IDF 权重字典（用于回退模式）
    """

    # 按优先级排序的候选模型列表
    CANDIDATE_MODELS = [
        "paraphrase-multilingual-MiniLM-L12-v2",   # 384d, 轻量首选
        "paraphrase-multilingual-mpnet-base-v2",    # 768d
        "distiluse-base-multilingual-cased-v2",     # 512d
    ]

    def __init__(self):
        self._model: Any = None
        self._model_name: str = ""
        self._embedding_dim: int = 0
        self._available: bool = False
        self._tried_import: bool = False
        self._import_error: Optional[str] = None

        # TF-IDF 回退
        self._tfidf_vectorizer = None
        self._tfidf_idf: dict[str, float] = {}
        self._tfidf_corpus_vocab: set[str] = set()

    # ── 公开接口 ────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """检查深度学习是否可用。

        首次调用会尝试导入依赖并加载模型。后续调用直接返回缓存状态。

        Returns:
            True 如果 sentence-transformers 已成功加载并可用。
        """
        if self._tried_import:
            return self._available
        self._tried_import = True
        return self._try_load()

    @property
    def model_name(self) -> str:
        """已加载的模型名称（仅 DL 可用时有值）。"""
        return self._model_name

    @property
    def embedding_dim(self) -> int:
        """当前嵌入向量维度。DL 模式为 384/768，回退模式为 0。"""
        return self._embedding_dim

    def encode_style(self, text: str) -> list[float]:
        """将文本编码为风格嵌入向量。

        优先使用 sentence-transformers 模型，不可用时回退到 TF-IDF 特征向量。

        Args:
            text: 待编码的文本（建议至少 200 字以获得稳定嵌入）

        Returns:
            风格嵌入向量（DL: 384 或 768 维; 回退: 基于 IDF 权重维度的稀疏向量）
        """
        if not self.is_available():
            return self._encode_tfidf(text)
        return self._encode_dl(text)

    def style_similarity(self, text_a: str, text_b: str) -> float:
        """两段文本的风格相似度（余弦相似度）。

        与纯规则模式相比：
        - DL 模式：使用嵌入向量的余弦相似度，捕获深层语义风格
        - 回退模式：使用 TF-IDF 向量的余弦相似度

        Args:
            text_a: 第一段文本
            text_b: 第二段文本

        Returns:
            余弦相似度 (0.0 ~ 1.0)，越高越相似
        """
        emb_a = self.encode_style(text_a)
        emb_b = self.encode_style(text_b)
        return self._cosine_similarity(emb_a, emb_b)

    def author_classify(
        self,
        text: str,
        candidates: dict[str, str],
    ) -> dict:
        """作者分类：将文本与候选作者风格对比，返回最接近的作者。

        方法：
        1. 对每个候选作者的参考文本计算嵌入（缓存）
        2. 计算目标文本嵌入
        3. 余弦相似度排名

        Args:
            text: 待分类文本
            candidates: {作者名: 该作者的代表性文本} 字典

        Returns:
            {
                "best_match": "作者名",
                "confidence": 0.85,          # 最高相似度
                "all_scores": {              # 所有候选的相似度
                    "作者A": 0.85,
                    "作者B": 0.72,
                    "作者C": 0.34,
                },
                "margin": 0.13,              # 第一名与第二名的差距
            }
        """
        if not candidates:
            return {
                "best_match": "",
                "confidence": 0.0,
                "all_scores": {},
                "margin": 0.0,
            }

        target_emb = self.encode_style(text)

        scores = {}
        for author_name, ref_text in candidates.items():
            ref_emb = self.encode_style(ref_text)
            scores[author_name] = round(self._cosine_similarity(target_emb, ref_emb), 4)

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_author, best_score = sorted_scores[0]

        margin = 0.0
        if len(sorted_scores) > 1:
            margin = round(best_score - sorted_scores[1][1], 4)

        return {
            "best_match": best_author,
            "confidence": best_score,
            "all_scores": dict(sorted_scores),
            "margin": margin,
        }

    def genre_classify(self, text: str) -> dict:
        """品类分类：将文本嵌入与 6 个品类基线对比。

        Args:
            text: 待分类文本

        Returns:
            {
                "best_genre": "xianxia_modern",
                "confidence": 0.78,
                "rankings": [
                    ("xianxia_modern", 0.78),
                    ("xuanhuan", 0.65),
                    ...
                ],
                "all_scores": {...},
            }
        """
        target_emb = self.encode_style(text)

        scores = {}
        for genre_name, baseline_text in GENRE_BASELINE_TEXTS.items():
            baseline_emb = self.encode_style(baseline_text)
            scores[genre_name] = round(self._cosine_similarity(target_emb, baseline_emb), 4)

        rankings = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return {
            "best_genre": rankings[0][0],
            "confidence": rankings[0][1],
            "rankings": rankings,
            "all_scores": scores,
        }

    def get_status(self) -> dict:
        """获取 DL 引擎状态摘要。

        Returns:
            {
                "dl_available": True/False,
                "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
                "embedding_dim": 384,
                "mode": "deep_learning" | "tfidf_fallback",
                "import_error": None | "错误信息",
            }
        """
        return {
            "dl_available": self.is_available(),
            "model_name": self._model_name,
            "embedding_dim": self._embedding_dim,
            "mode": "deep_learning" if self._available else "tfidf_fallback",
            "import_error": self._import_error,
        }

    # ── 内部方法 ────────────────────────────────────────────────────────

    def _try_load(self) -> bool:
        """尝试加载 sentence-transformers 模型。

        按 CANDIDATE_MODELS 优先级逐一尝试，首个成功即停止。
        """
        try:
            from sentence_transformers import SentenceTransformer

            for model_name in self.CANDIDATE_MODELS:
                try:
                    logger.info(f"尝试加载模型: {model_name}")
                    self._model = SentenceTransformer(model_name)
                    self._model_name = model_name

                    # 获取嵌入维度（通过一次试运行）
                    test_emb = self._model.encode(["测试"], show_progress_bar=False)
                    self._embedding_dim = test_emb.shape[1]

                    self._available = True
                    logger.info(
                        f"DL 引擎已激活: {model_name} ({self._embedding_dim}d)"
                    )
                    return True

                except Exception as e:
                    logger.warning(f"模型 {model_name} 加载失败: {e}")
                    continue

            # 所有候选模型都失败
            self._import_error = "所有候选模型加载失败"
            logger.warning("所有 sentence-transformers 模型加载失败，将使用 TF-IDF 回退")
            return False

        except ImportError as e:
            self._import_error = f"sentence-transformers 未安装: {e}"
            logger.info(
                "sentence-transformers 未安装，使用 TF-IDF 回退模式。"
                "可选安装: pip install sentence-transformers"
            )
            return False

        except Exception as e:
            self._import_error = f"未知错误: {e}"
            logger.error(f"DL 引擎初始化失败: {e}")
            return False

    def _encode_dl(self, text: str) -> list[float]:
        """使用 DL 模型编码文本。

        Args:
            text: 输入文本

        Returns:
            嵌入向量 (list[float])，维度由模型决定
        """
        if self._model is None:
            return self._encode_tfidf(text)

        try:
            embedding = self._model.encode(
                [text],
                show_progress_bar=False,
                normalize_embeddings=True,  # L2 归一化，便于余弦相似度
            )
            return embedding[0].tolist()
        except Exception as e:
            logger.warning(f"DL 编码失败，回退到 TF-IDF: {e}")
            return self._encode_tfidf(text)

    # ── TF-IDF 回退 ─────────────────────────────────────────────────────

    def _encode_tfidf(self, text: str) -> list[float]:
        """TF-IDF 特征向量编码（回退方案）。

        使用字符级 bigram 作为特征，计算 TF-IDF 权重。

        设计参考：
        - stylo 的 MFW (Most Frequent Words) 思想 → 字符级 bigram
        - 中文文本无天然词边界 → 字符 n-gram 更稳健

        Args:
            text: 输入文本

        Returns:
            TF-IDF 特征向量（高频 bigram 的加权频率）
        """
        # 提取中文 bigram
        chars = [c for c in text if '一' <= c <= '鿿']
        if len(chars) < 2:
            return [0.0] * 100

        bigrams = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
        bigram_counts = Counter(bigrams)

        # 使用全局 IDF（如果已构建）或局部 TF
        total_bigrams = sum(bigram_counts.values()) or 1
        top_bigrams = bigram_counts.most_common(100)

        # 构建 100 维特征向量
        vec = [0.0] * 100
        for i, (bg, count) in enumerate(top_bigrams):
            tf = count / total_bigrams
            idf = self._tfidf_idf.get(bg, 1.0)  # 默认 IDF=1（无全局语料时）
            vec[i] = round(tf * idf, 6)

        # L2 归一化
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    def update_idf(self, corpus: list[str]):
        """用语料库更新 IDF 权重（可选，用于提升 TF-IDF 回退质量）。

        Args:
            corpus: 文本列表，用于计算全局 IDF
        """
        doc_count = len(corpus)
        if doc_count == 0:
            return

        # 统计每个 bigram 出现在多少篇文档中
        bigram_doc_count: dict[str, int] = {}
        for doc in corpus:
            chars = [c for c in doc if '一' <= c <= '鿿']
            seen = set()
            for i in range(len(chars) - 1):
                bg = chars[i] + chars[i + 1]
                if bg not in seen:
                    seen.add(bg)
                    bigram_doc_count[bg] = bigram_doc_count.get(bg, 0) + 1

        # 计算 IDF
        self._tfidf_idf = {}
        for bg, count in bigram_doc_count.items():
            self._tfidf_idf[bg] = round(math.log((doc_count + 1) / (count + 1)) + 1, 4)

        logger.info(f"IDF 权重已更新: {len(self._tfidf_idf)} 个 bigram，语料规模 {doc_count} 篇")

    # ── 工具函数 ────────────────────────────────────────────────────────

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """计算两个向量的余弦相似度。

        假设向量已 L2 归一化，则直接计算点积。
        为安全起见仍然做显式归一化。
        """
        if len(a) != len(b):
            # 维度不同时截断到较小维度
            min_len = min(len(a), len(b))
            a = a[:min_len]
            b = b[:min_len]

        dot = sum(ai * bi for ai, bi in zip(a, b))
        norm_a = math.sqrt(sum(ai * ai for ai in a))
        norm_b = math.sqrt(sum(bi * bi for bi in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)


# ═══════════════════════════════════════════════════════════════════════════
# 单例工厂
# ═══════════════════════════════════════════════════════════════════════════

_dl_engine_instance: Optional[DLEngine] = None


def get_dl_engine() -> DLEngine:
    """获取 DLEngine 单例实例。

    全局唯一，懒加载。线程不安全但 CPython GIL 下可接受。

    Returns:
        DLEngine 单例
    """
    global _dl_engine_instance
    if _dl_engine_instance is None:
        _dl_engine_instance = DLEngine()
    return _dl_engine_instance