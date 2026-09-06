"""
递归 Theory of Mind 引擎 (ToM Engine v1)

核心能力：
1. 维护每个角色的"信念状态图"——角色相信什么、知道什么、以为别人知道什么
2. 递归推理：支持 3 层嵌套（A认为B以为C知道D的秘密）
3. 信念更新规则：目击直接更新 / 二手信息带权重 / 欺骗创建错误信念分支
4. 戏剧张力点检测：信念冲突自动标记
5. 行动倾向推理：给定信念状态，角色最合理的行动是什么

学术基础：
- Embedded Mental States (oli, 2024): 叙事深度与 ToM 嵌套层数正相关
- Zunshine (2006): 读者使用相同机制理解虚构角色和真实人类
- 角色可预测但可理解的平衡——Too predictable = boring, too unpredictable = OOC
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json
import uuid


# ═══════════════════════════════════════════
# 核心数据类型
# ═══════════════════════════════════════════

class BeliefSource(Enum):
    """信念信息来源"""
    DIRECT_WITNESS = "目击"       # 角色亲眼看到 → 高可信度
    SECOND_HAND = "二手信息"      # 听说的 → 中等可信度，可被推翻
    INFERENCE = "推理"            # 逻辑推演 → 中等可信度
    DECEPTION = "欺骗"            # 被故意误导 → 错误信念
    MISUNDERSTANDING = "误解"     # 误解信息 → 错误信念


class TensionType(Enum):
    """戏剧张力类型"""
    BELIEF_CONFLICT = "信念冲突"          # 角色A的信念 ≠ 角色B的信念
    DRAMATIC_IRONY = "戏剧反讽"           # 读者知道 > 角色知道
    RECURSIVE_MISMATCH = "递归错位"        # A以为B知道 ≠ B实际知道
    SECRET_AT_RISK = "秘密暴露风险"        # 秘密即将被揭穿
    GOAL_CONFLICT = "目标冲突"             # 两个角色的目标不可调和


@dataclass
class Belief:
    """角色的单一信念——ToM引擎的基本单元"""
    proposition: str                    # 命题描述，如 "张三就是凶手"
    value: bool | str | None            # 信念内容
    confidence: float                   # 可信度 0.0-1.0
    source: BeliefSource = BeliefSource.DIRECT_WITNESS
    updated_at: int = 0                 # 更新的章节编号
    is_erroneous: bool = False          # 是否为错误信念

    def __repr__(self):
        status = "❌" if self.is_erroneous else "✓"
        return f"[{status}] {self.proposition}={self.value} (conf:{self.confidence:.1f}, src:{self.source.value})"


@dataclass
class CharacterBeliefState:
    """一个角色的完整信念状态"""
    character_id: str
    name: str

    # 对世界的信念：{"命题": Belief}
    world_beliefs: dict[str, Belief] = field(default_factory=dict)

    # 对他人的信念：{"其他角色ID": {"关于这个角色相信什么": Belief}}
    # 这是 ToM 第一层——"角色A对角色B的了解"
    about_others: dict[str, dict[str, Belief]] = field(default_factory=dict)

    # 递归信念：{"其他角色ID": {"关于...的信念": Belief}}
    # 这是 ToM 第二层——"角色A认为角色B相信什么"
    # 这是 ToM 第三层——"角色A认为角色B认为角色C知道什么"
    # 键格式：层2用 "beliefs_about_<target_id>"，层3用 "beliefs_about_<target_id>_about_<target2_id>"
    recursive_beliefs: dict[str, dict[str, Belief]] = field(default_factory=dict)

    # 角色知道的秘密
    known_secrets: list[Secret] = field(default_factory=list)
    # 当前活跃目标
    active_goals: list[Goal] = field(default_factory=list)

    def get_dramatic_irony(self, reader_knowledge: dict[str, bool]) -> list[str]:
        """计算当前角色的"戏剧反讽"——读者知道但角色不知道的事"""
        ironies = []
        for prop, truth in reader_knowledge.items():
            if prop in self.world_beliefs and self.world_beliefs[prop].value != truth:
                ironies.append(f"读者知道「{prop}={truth}」，但{self.name}以为{self.world_beliefs[prop].value}")
        return ironies


@dataclass
class Secret:
    """秘密——核心叙事张力的来源"""
    description: str
    known_to: list[str] = field(default_factory=list)  # 知道秘密的角色ID列表
    hidden_from: list[str] = field(default_factory=list)  # 不知道的角色ID列表
    is_revealed: bool = False
    reveal_chapter: Optional[int] = None


@dataclass
class Goal:
    """角色目标"""
    description: str
    priority: int = 1
    active: bool = True
    since_chapter: int = 1


@dataclass
class TensionPoint:
    """戏剧张力点——ToM引擎检测到的可叙事冲突"""
    type: TensionType
    description: str
    intensity: float  # 0.0-1.0
    involved_characters: list[str]
    suggestion: str = ""  # 系统建议怎么写


@dataclass
class ActionTendency:
    """角色行动倾向——ToM 推理的输出"""
    character_id: str
    action: str
    rationale: str  # 推理依据
    strength: float  # 强度 0.0-1.0
    conflicts_with: list[str] = field(default_factory=list)  # 与其他角色行动倾向冲突


# ═══════════════════════════════════════════
# ToM 引擎主类
# ═══════════════════════════════════════════

class TheoryOfMindEngine:
    """
    递归 Theory of Mind 引擎

    维护所有角色的信念状态，支持：
    - 信念更新（目击/二手/欺骗/误解）
    - 递归嵌套推理（A认为B以为C知道D）
    - 戏剧张力点检测
    - 角色行动倾向推理
    """

    def __init__(self):
        self.characters: dict[str, CharacterBeliefState] = {}
        self.reader_knowledge: dict[str, bool | str] = {}  # 读者知道的"客观真相"
        self.current_chapter: int = 0
        self.tension_points: list[TensionPoint] = []

    # ═══════════════════════════════════════
    # 角色管理
    # ═══════════════════════════════════════

    def add_character(self, char_id: str, name: str) -> CharacterBeliefState:
        """添加角色到ToM引擎"""
        state = CharacterBeliefState(character_id=char_id, name=name)
        self.characters[char_id] = state
        return state

    def get_character(self, char_id: str) -> Optional[CharacterBeliefState]:
        return self.characters.get(char_id)

    def get_all_characters(self) -> list[CharacterBeliefState]:
        return list(self.characters.values())

    # ═══════════════════════════════════════
    # 信念更新
    # ═══════════════════════════════════════

    def update_belief(
        self,
        char_id: str,
        proposition: str,
        value: bool | str,
        confidence: float,
        source: BeliefSource = BeliefSource.DIRECT_WITNESS
    ):
        """更新角色对世界的信念"""
        char = self.characters.get(char_id)
        if not char:
            raise ValueError(f"角色 {char_id} 不存在")

        is_erroneous = source in (BeliefSource.DECEPTION, BeliefSource.MISUNDERSTANDING)
        char.world_beliefs[proposition] = Belief(
            proposition=proposition,
            value=value,
            confidence=confidence,
            source=source,
            updated_at=self.current_chapter,
            is_erroneous=is_erroneous
        )

    def update_belief_about_other(
        self,
        char_id: str,
        target_id: str,
        proposition: str,
        value: bool | str,
        confidence: float,
        source: BeliefSource = BeliefSource.DIRECT_WITNESS
    ):
        """更新角色A对角色B的信念（ToM第一层）"""
        char = self.characters.get(char_id)
        if not char:
            raise ValueError(f"角色 {char_id} 不存在")

        if target_id not in char.about_others:
            char.about_others[target_id] = {}

        is_erroneous = source in (BeliefSource.DECEPTION, BeliefSource.MISUNDERSTANDING)
        char.about_others[target_id][proposition] = Belief(
            proposition=proposition,
            value=value,
            confidence=confidence,
            source=source,
            updated_at=self.current_chapter,
            is_erroneous=is_erroneous
        )

    def update_recursive_belief(
        self,
        char_id: str,
        about_char_id: str,
        about_proposition: str,
        value: bool | str,
        confidence: float,
        depth: int = 2,
        source: BeliefSource = BeliefSource.INFERENCE
    ):
        """更新角色的递归信念

        depth=2: 角色A认为角色B相信「命题」
        depth=3: 角色A认为角色B认为角色C「命题」

        学术界指出，3层嵌套是"深度叙事"的典型复杂度
        """
        char = self.characters.get(char_id)
        if not char:
            raise ValueError(f"角色 {char_id} 不存在")

        key = f"beliefs_about_{about_char_id}"
        if depth >= 3:
            key += f"_about_{about_proposition.split('_')[0] if '_' in about_proposition else about_proposition}"

        if key not in char.recursive_beliefs:
            char.recursive_beliefs[key] = {}

        char.recursive_beliefs[key][about_proposition] = Belief(
            proposition=f"level_{depth}: {char_id} thinks {about_char_id} believes '{about_proposition}'",
            value=value,
            confidence=confidence,
            source=source,
            updated_at=self.current_chapter
        )

    # ═══════════════════════════════════════
    # 秘密管理
    # ═══════════════════════════════════════

    def register_secret(
        self,
        description: str,
        known_to: list[str],
        hidden_from: list[str]
    ):
        """注册一个秘密——自动更新相关角色的known_secrets"""
        secret = Secret(
            description=description,
            known_to=known_to,
            hidden_from=hidden_from
        )
        for cid in known_to:
            if cid in self.characters:
                self.characters[cid].known_secrets.append(secret)

    def reveal_secret(self, description: str, chapter: int):
        """揭示一个秘密——更新全局knowledge"""
        for char in self.characters.values():
            for s in char.known_secrets:
                if s.description == description:
                    s.is_revealed = True
                    s.reveal_chapter = chapter

    # ═══════════════════════════════════════
    # 戏剧张力点检测
    # ═══════════════════════════════════════

    def detect_tension(self) -> list[TensionPoint]:
        """运行全量张力检测——在每章完成后执行"""
        self.tension_points = []
        char_ids = list(self.characters.keys())

        # 检测信念冲突
        for i, cid1 in enumerate(char_ids):
            for cid2 in char_ids[i + 1:]:
                c1 = self.characters[cid1]
                c2 = self.characters[cid2]

                # 比较两人对同一命题的信念
                shared_props = set(c1.world_beliefs.keys()) & set(c2.world_beliefs.keys())
                for prop in shared_props:
                    b1, b2 = c1.world_beliefs[prop], c2.world_beliefs[prop]
                    if b1.value != b2.value and not (b1.is_erroneous and b2.is_erroneous):
                        self.tension_points.append(TensionPoint(
                            type=TensionType.BELIEF_CONFLICT,
                            description=f"{c1.name}相信「{prop}={b1.value}」，但{c2.name}相信「{prop}={b2.value}」",
                            intensity=min(1.0, (b1.confidence + b2.confidence) / 2),
                            involved_characters=[cid1, cid2],
                            suggestion=f"制造一场{c1.name}和{c2.name}争论{prop}的场景"
                        ))

        # 检测戏剧反讽
        for cid in char_ids:
            char = self.characters[cid]
            ironies = char.get_dramatic_irony(self.reader_knowledge)
            for irony in ironies:
                self.tension_points.append(TensionPoint(
                    type=TensionType.DRAMATIC_IRONY,
                    description=irony,
                    intensity=0.8,
                    involved_characters=[cid],
                    suggestion=f"利用读者知道但{char.name}不知道的信息差制造紧张感"
                ))

        # 检测递归错位
        for cid in char_ids:
            char = self.characters[cid]
            for tid in char_ids:
                if tid == cid:
                    continue
                other = self.characters[tid]
                rec_key = f"beliefs_about_{tid}"
                if rec_key in char.recursive_beliefs:
                    for prop, belief in char.recursive_beliefs[rec_key].items():
                        # A以为B知道某事
                        if prop in other.world_beliefs:
                            actual = other.world_beliefs[prop]
                            if belief.value != actual.value:
                                self.tension_points.append(TensionPoint(
                                    type=TensionType.RECURSIVE_MISMATCH,
                                    description=f"{char.name}以为{other.name}知道「{prop}={belief.value}」，但实际{other.name}知道的是「{prop}={actual.value}」",
                                    intensity=0.9,  # 递归错位的张力最高
                                    involved_characters=[cid, tid],
                                    suggestion=f"让{char.name}基于错误的认知做出行动——读者会替ta着急"
                                ))

        # 按强度排序
        self.tension_points.sort(key=lambda t: t.intensity, reverse=True)
        return self.tension_points

    # ═══════════════════════════════════════
    # 行动倾向推理
    # ═══════════════════════════════════════

    def infer_action_tendencies(self, scene_context: str = "") -> list[ActionTendency]:
        """推理当前场景下每个角色最合理的行动倾向

        这是 LLM 回调的输入——ToM 引擎输出结构化的推理约束，
        LLM 在约束内生成具体文本。
        """
        tendencies = []

        for cid, char in self.characters.items():
            if not char.active_goals:
                continue

            # 按优先级排序目标
            sorted_goals = sorted(char.active_goals, key=lambda g: g.priority, reverse=True)
            top_goal = sorted_goals[0] if sorted_goals else None

            if top_goal:
                # 检查目标是否受信念变化影响
                affected = []
                for prop, belief in char.world_beliefs.items():
                    if top_goal.description in prop or prop in top_goal.description:
                        affected.append(belief)

                if affected:
                    action = f"{char.name}正在追求目标「{top_goal.description}」（优先级{top_goal.priority}）"
                    rationale = f"基于最近更新的信念：{affected[-1].proposition}={affected[-1].value}"
                    tendencies.append(ActionTendency(
                        character_id=cid,
                        action=action,
                        rationale=rationale,
                        strength=top_goal.priority / 5.0
                    ))

        # 检测行动冲突
        for i, t1 in enumerate(tendencies):
            for t2 in tendencies[i + 1:]:
                t1.conflicts_with.append(t2.character_id)
                t2.conflicts_with.append(t1.character_id)

        return tendencies

    # ═══════════════════════════════════════
    # 叙事状态序列化
    # ═══════════════════════════════════════

    def to_snapshot(self) -> dict:
        """导出完整的 ToM 状态快照——用于持久化和心智网格可视化"""
        snapshot = {
            "characters": {},
            "tension_points": [
                {
                    "type": tp.type.value,
                    "description": tp.description,
                    "intensity": tp.intensity,
                    "involved": tp.involved_characters,
                    "suggestion": tp.suggestion
                }
                for tp in self.tension_points
            ],
            "current_chapter": self.current_chapter
        }
        for cid, char in self.characters.items():
            snapshot["characters"][cid] = {
                "name": char.name,
                "world_beliefs": {
                    k: {
                        "value": v.value,
                        "confidence": v.confidence,
                        "source": v.source.value,
                        "is_erroneous": v.is_erroneous
                    }
                    for k, v in char.world_beliefs.items()
                },
                "about_others": {
                    target: {
                        k: {
                            "value": v.value,
                            "confidence": v.confidence
                        }
                        for k, v in beliefs.items()
                    }
                    for target, beliefs in char.about_others.items()
                },
                "active_goals": [
                    {"description": g.description, "priority": g.priority}
                    for g in char.active_goals
                ],
                "secret_count": len(char.known_secrets)
            }
        return snapshot

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "TheoryOfMindEngine":
        """从快照恢复 ToM 引擎"""
        engine = cls()
        engine.current_chapter = snapshot.get("current_chapter", 0)
        for cid, data in snapshot["characters"].items():
            char = engine.add_character(cid, data["name"])
            for prop, b in data["world_beliefs"].items():
                char.world_beliefs[prop] = Belief(
                    proposition=prop,
                    value=b["value"],
                    confidence=b.get("confidence", 1.0),
                    source=BeliefSource(b.get("source", "目击")),
                    is_erroneous=b.get("is_erroneous", False)
                )
        # 重新检测张力点
        engine.detect_tension()
        return engine

    def advance_chapter(self):
        """推进一章——增量更新"""
        self.current_chapter += 1
        # 衰减旧的信念置信度（角色会遗忘）
        for char in self.characters.values():
            for belief in char.world_beliefs.values():
                if self.current_chapter - belief.updated_at > 50:
                    belief.confidence = max(0.3, belief.confidence * 0.95)
        # 重新检测张力
        self.detect_tension()

    def validate_action(self, char_id: str, action_description: str) -> Optional[str]:
        """校验一个行动是否与角色的信念状态一致

        返回 None 表示一致，返回字符串描述不一致的原因
        这是 G2 信念一致性门禁的核心逻辑
        """
        char = self.characters.get(char_id)
        if not char:
            return f"角色 {char_id} 不存在"

        # 简单规则：如果角色的信念包含文本中的实体，
        # 且行动中包含否定/敌对/背叛词，而信念是肯定的 → 异常
        negations = ["举报", "背叛", "出卖", "伤害", "攻击", "杀死", "陷害",
                     "不", "没", "否认", "反对", "拒绝"]
        friend_signals = ["朋友", "信任", "伙伴", "战友", "盟友", "同志"]

        for prop, belief in char.world_beliefs.items():
            if belief.is_erroneous:
                continue
            # 检查文本中是否提到了该命题相关的实体
            prop_keywords = prop.replace("是", " ").replace("的", " ").split()
            has_entity = any(kw in action_description for kw in prop_keywords if len(kw) > 1)
            if not has_entity:
                continue

            # 如果信念是肯定的（比如"B是朋友"=True）
            # 但行动包含否定词 → 冲突
            if belief.value is True:
                has_negation = any(n in action_description for n in negations)
                if has_negation:
                    return (
                        f"{char.name}相信「{prop}」，"
                        f"但行动却与这一信念矛盾：{action_description[:50]}"
                    )

            # 如果信念的具体值出现在行动中，且与否定关联 → 冲突
            if isinstance(belief.value, str) and belief.value:
                if belief.value in action_description:
                    has_negation = any(n in action_description for n in negations)
                    if has_negation:
                        return (
                            f"{char.name}相信「{prop}={belief.value}」，"
                            f"但行动与之一致却包含否定词：{action_description[:50]}"
                        )
        return None
