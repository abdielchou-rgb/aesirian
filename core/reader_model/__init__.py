"""
读者认知模型模拟器 v1 + 事件冷却矩阵

理论来源：
- Event Model (Magliano et al., 2024): 读者阅读时实时构建多维事件模型
- Narrative Transportation (Green & Brock, 2000): 故事沉浸感的认知机制
- Neural Narrative (Maass): 神经叙事学的节奏和张力理论
- Novel-Creator-Skill: 事件冷却矩阵的设计模式
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

# ═══════════════════════════════════════════
# 读者模型
# ═══════════════════════════════════════════


@dataclass
class ReaderEventModel:
    """读者当前建构的事件模型

    模拟"理想读者"在当前叙事进度下的心智模型。
    """

    # 因果链——读者当前理解的"因为...所以..."
    causal_chain: list[str] = field(default_factory=list)
    # 时空坐标——读者认为"当前场景在哪里、什么时间"
    current_location: str = ""
    current_time: str = ""
    # 角色索引——读者已见过并记住的角色
    known_characters: list[str] = field(default_factory=list)
    # 读者当前认为"还有哪些未解答的问题"
    open_questions: list[str] = field(default_factory=list)


@dataclass
class TransportationScore:
    """叙事传输度评分"""

    overall: float = 0.0  # 总体沉浸度 0-100
    sensory_detail: float = 0.0  # 感官细节密度
    dialogue_ratio: float = 0.0  # 对话比例
    sentence_variety: float = 0.0  # 句长变异系数
    pov_consistency: float = 0.0  # 视角一致性
    unexplained_density: float = 0.0  # 未解释事件密度
    interruption_rate: float = 0.0  # 打断/省略/沉默频率


class ReaderModelSimulator:
    """
    读者认知模型模拟器

    预测"理想读者"在当前叙事进度下的心智模型状态。
    用于：
    1. 预测每次叙事操作的认知更新成本
    2. 评估当前文本的叙事传输度
    3. 为生成引擎提供"读者此刻最关心什么"的反馈
    """

    def __init__(self):
        self.model = ReaderEventModel()
        self.transportation_history: list[TransportationScore] = []
        self._last_location = ""
        self._last_pov = ""
        self._known_characters_cache = set()

    # ═══════════════════════════════════════
    # 事件模型更新
    # ═══════════════════════════════════════

    def update_from_text(self, text: str, chapter: int):
        """根据新文本更新读者模型"""
        # 更新时空坐标
        location_markers = re.findall(r"在([^，。]{1,10})[，。]", text)
        if location_markers:
            self.model.current_location = location_markers[-1]

        # 更新因果链
        causal_markers = re.findall(r"因为(.*?)(?:，|所以)", text)
        if causal_markers:
            self.model.causal_chain.extend(causal_markers)

        # 更新角色索引
        # 简单实现：提取"角色名说/想/做"模式
        char_mentions = re.findall(r"([一-鿿]{2,3})(?:说|想|看|走|笑|哭|站)", text)
        for cm in char_mentions:
            self._known_characters_cache.add(cm)
        self.model.known_characters = list(self._known_characters_cache)

        # 更新开放问题
        question_markers = re.findall(r"[？?]", text)
        if len(question_markers) > len(self.model.open_questions):
            self.model.open_questions.append(f"第{chapter}章出现的新问题")

    def estimate_update_cost(self, operation: dict) -> float:
        """估计一次叙事操作的认知更新成本

        operation 可以是：
          {"type": "pov_switch", "from": "A", "to": "B"}
          {"type": "time_jump", "magnitude": "3年"}
          {"type": "new_character", "name": "C"}
          {"type": "location_change", "from": "A", "to": "B"}

        参考学术发现（Magliano et al., 2024）：
        POV切换 ×4 / 时间跳变 ×2 / 空间移动 ×2 / 新角色 ×3
        """
        base_costs = {
            "pov_switch": 4,
            "time_jump": 2,
            "new_character": 3,
            "location_change": 2,
            "flashback": 3,
        }

        op_type = operation.get("type", "")
        base = base_costs.get(op_type, 1)

        # 加权
        if op_type == "time_jump":
            magnitude = operation.get("magnitude", 1)
            if isinstance(magnitude, str):
                if "年" in magnitude:
                    magnitude = 10
                elif "月" in magnitude:
                    magnitude = 3
                else:
                    magnitude = 1
            base *= min(3, magnitude / 30 + 1)

        if op_type == "new_character":
            name = operation.get("name", "")
            if name in self._known_characters_cache:
                base *= 0.5  # 已出现的角色成本减半

        return base

    def predict_confusion(self, operations: list[dict]) -> str | None:
        """预测一组叙事操作是否会导致读者困惑"""
        total_cost = sum(self.estimate_update_cost(op) for op in operations)
        if total_cost > 12:
            return f"连续叙事操作的累计认知成本为{total_cost}（阈值12），可能让读者感到困惑"
        return None

    # ═══════════════════════════════════════
    # 叙事传输度评估
    # ═══════════════════════════════════════

    def evaluate_transportation(self, text: str) -> TransportationScore:
        """评估一段文本的叙事传输度

        学术加权公式：
          传输度 = 0.3 × 感官细节密度 + 0.2 × 对话比例 + 0.15 × 句长变异
                + 0.15 × 视角一致性 + 0.1 × 未解释密度 + 0.1 × 打断率
        """
        import statistics

        score = TransportationScore()

        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if not paragraphs:
            return score

        # 感官细节密度
        sensory_words = [
            "手",
            "指",
            "眼",
            "脚",
            "脸",
            "唇",
            "皮肤",
            "汗",
            "冷",
            "热",
            "痛",
            "香",
            "臭",
            "甜",
            "苦",
            "声音",
            "光",
            "暗",
            "形状",
            "颜色",
        ]
        total_words = len(text)
        sensory_count = sum(text.count(w) for w in sensory_words)
        score.sensory_detail = min(100, sensory_count / max(1, total_words) * 500)

        # 对话比例
        dialogue_chars = sum(
            len(line)
            for line in text.split("\n")
            if "说" in line or "道" in line or "问" in line or "答" in line
        )
        score.dialogue_ratio = min(100, dialogue_chars / max(1, total_words) * 100)

        # 句长变异系数
        sentences = re.split(r"[。！？\n.!?]", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 3]
        if len(sentences) >= 3:
            lengths = [len(s) for s in sentences]
            mean = statistics.mean(lengths)
            stdev = statistics.stdev(lengths)
            cv = stdev / mean if mean > 0 else 0
            # 变异系数在 0.5-1.0 之间表示"自然变化"
            score.sentence_variety = min(100, max(0, 100 - abs(cv - 0.7) * 100))

        # 视角一致性
        first_person = re.findall(r"我[^们]", text)
        third_person = re.findall(r"他[^们]|她[^们]", text)
        if first_person and third_person:
            score.pov_consistency = 30  # 混合视角 = 低一致性
        elif first_person or third_person:
            score.pov_consistency = 80  # 单一视角 = 高一致性
        else:
            score.pov_consistency = 50

        # 未解释事件的密度
        unexplained_markers = re.findall(r"突然|竟然|为什么|怎么回事", text)
        unexplained_count = len(unexplained_markers)
        if unexplained_count > 0 and unexplained_count < 4:
            score.unexplained_density = 70  # 少量未解释 = 恰好
        elif unexplained_count >= 4:
            score.unexplained_density = 40  # 太多未解释 = 混乱
        else:
            score.unexplained_density = 30  # 完全没未解释 = too clean

        # 打断率
        interruptions = re.findall(r"——|……|\?|？|！|!", text)
        interruption_rate = len(interruptions) / max(1, len(sentences))
        # 每句 0.3-0.8 次打断 = 自然
        score.interruption_rate = min(100, max(0, 100 - abs(interruption_rate - 0.5) * 150))

        # 总体得分
        score.overall = (
            0.3 * score.sensory_detail
            + 0.2 * score.dialogue_ratio
            + 0.15 * score.sentence_variety
            + 0.15 * score.pov_consistency
            + 0.1 * score.unexplained_density
            + 0.1 * score.interruption_rate
        )

        self.transportation_history.append(score)
        return score

    def get_trend(self) -> str:
        """最近N章的传输度趋势（N>=2即可评估）"""
        if len(self.transportation_history) < 2:
            return "数据不足"

        recent = (
            self.transportation_history[-3:]
            if len(self.transportation_history) >= 3
            else self.transportation_history
        )
        scores = [t.overall for t in recent]

        if len(scores) >= 2:
            if scores[-1] > scores[0] * 1.05:
                return "↑ 上升"
            if scores[-1] < scores[0] * 0.95:
                return "↓ 下降"
            return "→ 平稳"
        return "数据不足"


# ═══════════════════════════════════════════
# 事件冷却矩阵
# ═══════════════════════════════════════════


class EventCooldownMatrix:
    """
    事件冷却矩阵

    防止系统在短周期内重复使用同一种叙事模式。
    每使用一次 → 对应单元格获得冷却值（指数衰减）。
    生成器查询冷却矩阵 → 冷却值高的模式降权 → 强制多样性。

    矩阵维度：爽点类型 / 冲突类型 / 情感弧线 / 情节结构
    """

    def __init__(self, decay_rate: float = 0.7):
        # "模式名": 当前冷却值
        self.matrix: dict[str, float] = defaultdict(float)
        self.decay_rate = decay_rate
        self.usage_history: list[str] = []
        self.max_history = 50

    # 预定义模式类别
    PLEASURE_TYPES = [
        "打脸",
        "碾压",
        "降维打击",
        "逆袭",
        "身份揭晓",
        "突破",
        "觉醒",
        "反击",
        "揭穿",
        "震惊",
        "甜",
        "虐",
        "感人",
        "帅",
    ]

    CONFLICT_TYPES = ["身份冲突", "资源冲突", "价值观冲突", "关系冲突", "生存冲突", "认知冲突"]

    EMOTIONAL_ARC_TYPES = [
        "从绝望到希望",
        "从仇恨到和解",
        "从迷茫到坚定",
        "从恐惧到勇气",
        "从自私到牺牲",
    ]

    def record_usage(self, pattern_name: str):
        """记录一次模式的使用"""
        self.matrix[pattern_name] += 1.0
        self.usage_history.append(pattern_name)
        if len(self.usage_history) > self.max_history:
            self.usage_history.pop(0)

    def advance_time(self, steps: int = 1):
        """推进时间步（每步=1章），衰减冷却值"""
        for key in self.matrix:
            self.matrix[key] *= self.decay_rate**steps
        # 清理接近零的值
        self.matrix = defaultdict(float, {k: v for k, v in self.matrix.items() if v > 0.01})

    def get_cooldown(self, pattern_name: str) -> float:
        """查询一个模式的当前冷却值"""
        return self.matrix.get(pattern_name, 0.0)

    def get_hot_patterns(self, threshold: float = 0.5) -> list[tuple[str, float]]:
        """获取当前过热的模式（冷却值超过阈值）"""
        return [
            (k, v) for k, v in sorted(self.matrix.items(), key=lambda x: -x[1]) if v >= threshold
        ]

    def get_cold_patterns(self, threshold: float = 1.0) -> list[str]:
        """获取空闲可用的模式"""
        all_patterns = set(self.PLEASURE_TYPES + self.CONFLICT_TYPES + self.EMOTIONAL_ARC_TYPES)
        used = set(self.matrix.keys())
        return [p for p in all_patterns - used if self.matrix.get(p, 0.0) < threshold]

    def get_recommendations(self, count: int = 3) -> list[str]:
        """推荐当前应该使用的叙事模式（冷却值最低的）"""
        cold_patterns = self.get_cold_patterns()
        if not cold_patterns:
            return sorted(self.matrix.items(), key=lambda x: x[1])[:count]
        return cold_patterns[:count]

    def recent_pattern_distribution(self, window: int = 10) -> dict[str, float]:
        """最近若干章的模式分布——用于G10门禁"""
        recent = self.usage_history[-window:] if self.usage_history else []
        if not recent:
            return {}

        counter = Counter(recent)
        total = len(recent)
        return {k: v / total for k, v in counter.most_common()}

    def check_saturation(self, window: int = 5, threshold: float = 0.6) -> str | None:
        """检查是否存在模式饱和（重复率过高）"""
        recent = self.usage_history[-window:] if self.usage_history else []
        if len(recent) < window:
            return None

        counter = Counter(recent)
        most_common = counter.most_common(1)
        if most_common and (most_common[0][1] / window) >= threshold:
            return (
                f"叙事模式「{most_common[0][0]}」在过去{window}章中出现"
                f"{most_common[0][1]}次（占比{most_common[0][1] / window:.0%}）"
            )
        return None
