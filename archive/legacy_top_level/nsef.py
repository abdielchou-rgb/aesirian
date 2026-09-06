# Æsirian 叙事状态交换格式 (NSEF) v1.0
# 这是Æsir（灵感层）和Æsirian Core（深度生产层）之间的标准数据契约
# 每个NSEF包代表一个"故事种子"——从Æsir的故事单元转译后的最小深度推演起点

"""
NSEF (Narrative State Exchange Format)

一个NSEF包包含从一个Æsir故事单元中提取的所有可推演信息：
- 角色初始信念状态（用于ToM引擎的种子）
- 结构标记（SG5/三幕等节点位置）
- 未闭合线索（注册到知识图谱的待回收伏笔）
- 类型契约（约束生成器的风格和结构要求）
- 风格档案快照（蒸馏管道输出的偏好向量）
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum
from datetime import datetime
import json
import uuid


# ═══════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════

class Tone(Enum):
    COLD_REALISTIC = "冷峻写实"
    WARM_HEALING = "温暖治愈"
    DARK_HUMOR = "黑色幽默"
    SUSPENSE = "悬疑暗流"
    POETIC = "诗意思辨"
    FIERCE = "激烈狂暴"


class ConflictType(Enum):
    IDENTITY = "身份冲突"
    RESOURCE = "资源冲突"
    VALUE = "价值观冲突"
    RELATIONSHIP = "关系冲突"
    SURVIVAL = "生存冲突"
    COGNITION = "认知冲突"


class Genre(Enum):
    MYSTERY = "悬疑推理"
    XIANXIA = "仙侠玄幻"
    URBAN_REVENGE = "都市逆袭"
    ROMANCE = "言情"
    HISTORICAL = "历史权谋"
    GROWTH = "成长逆袭"
    SCIFI = "科幻末世"


class NarrativeArc(Enum):
    HERO_JOURNEY = "英雄之旅"
    THREE_ACT = "三幕结构"
    FIVE_ACT_DIALECTIC = "五幕辩证"
    WEB_NOVEL_UPGRADE = "升级流"
    STORY_CIRCLE = "故事圈"


class GateResult(Enum):
    BLOCK = "block"  # 不通过，不显示
    WARN = "warn"    # 通过但标注
    PASS = "pass"    # 完全通过


# ═══════════════════════════════════════════
# 核心数据结构
# ═══════════════════════════════════════════

@dataclass
class BeliefState:
    """角色对某个命题的信念状态

    这是整个NSEF中最关键的数据结构——它是ToM引擎的种子。
    每条信念记录了角色对世界、对他人的认知，以及认知的可信度。
    """
    proposition: str           # 信念命题，如 "谁是凶手"
    value: bool | str | None  # 信念内容，如 "张伟"
    confidence: float          # 可信度 0.0-1.0
    updated_at_chapter: int    # 在哪个章节更新的
    source: str = ""           # 信息来源（目击/二手信息/推理/欺骗）
    is_erroneous: bool = False # 是否为错误信念（被欺骗或误解）


@dataclass
class SecretState:
    """秘密——读者知道但部分角色不知道的信息

    秘密是叙事张力的核心来源。
    可配置秘密的知情范围（哪些角色知道、读者是否知道、作者保留）。
    """
    secret: str
    known_to: list[str] = field(default_factory=lambda: ["reader"])  # 知道秘密的角色列表
    hidden_from: list[str] = field(default_factory=list)  # 不知道的角色列表
    reveal_at_chapter: Optional[int] = None  # 计划揭示章节（可选）
    is_revealed: bool = False


@dataclass
class GoalState:
    """角色的当前活跃目标"""
    goal: str
    priority: int = 1
    active: bool = True
    since_chapter: int = 1


@dataclass
class CharacterSeed:
    """角色的初始状态——从故事单元文本中提取

    这是ToM引擎的输入。Æsir的故事单元经过NLP提取后，
    填充到这里作为角色的"信念初始值"。
    """
    name: str
    role: str = ""  # 在故事中的角色描述
    beliefs: dict[str, BeliefState] = field(default_factory=dict)
    goals: list[GoalState] = field(default_factory=list)
    secrets: list[SecretState] = field(default_factory=list)
    personality_traits: dict[str, float] = field(default_factory=dict)  # 大五人格得分


@dataclass
class SG5Structure:
    """SG5 五诫命结构标记"""
    inciting_event: str = ""
    turning_point: str = ""
    crisis: str = ""
    climax: str = ""
    resolution: str = ""


@dataclass
class OpenThread:
    """未闭合线索——随故事单元一同产出

    每个线索是"一个等待回收的问题"。
    """
    thread_id: str = ""
    description: str = ""
    created_at_chapter: int = 0
    expected_resolution_type: str = ""  # reveal / converge / sacrifice / etc
    is_resolved: bool = False
    resolved_at_chapter: Optional[int] = None


@dataclass
class StyleFingerprint:
    """风格指纹——Æsir蒸馏管道的输出快照

    记录了用户在当前时间点的风格偏好。
    深度层会根据这个指纹调整生成器的输出风格。
    """
    tone_distribution: dict[str, float] = field(default_factory=dict)
    conflict_preference: list[str] = field(default_factory=list)
    sentence_length_avg: float = 0.0
    dialogue_ratio: float = 0.0
    sensory_channel_bias: dict[str, float] = field(default_factory=dict)
    pov_preference: str = ""


@dataclass
class GenreContract:
    """类型契约——用户选择类型时对应的结构约束

    每种类型有一套"读者期待"的约束条件。
    这个契约会传递给生成器和一致性门禁，作为检查标准。
    """
    genre: Genre = Genre.GROWTH
    reader_expectations: list[str] = field(default_factory=list)
    core_rhythm: str = ""
    required_scenes: list[str] = field(default_factory=list)
    must_avoid: list[str] = field(default_factory=list)
    compatible_genres: list[str] = field(default_factory=list)


@dataclass
class NarrativeStatePackage:
    """NSEF 核心包——Æsir 产出 → 深度层处理的完整状态

    这是整个Æsirian生态系统中数据交换的基本单元。
    """
    # 元数据
    package_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "aesir"  # 来源标识

    # 故事种子核心
    premise: str = ""  # 前提句
    unit_text: str = ""  # 故事单元原始文本

    # 结构信息
    structure: SG5Structure = field(default_factory=SG5Structure)
    arc_type: NarrativeArc = NarrativeArc.THREE_ACT
    genre_contract: Optional[GenreContract] = None

    # 角色种子（ToM引擎的输入）
    characters: list[CharacterSeed] = field(default_factory=list)

    # 未闭合线索
    open_threads: list[OpenThread] = field(default_factory=list)

    # 风格与偏好
    tone: Tone = Tone.WARM_HEALING
    conflict: ConflictType = ConflictType.RELATIONSHIP
    style_fingerprint: StyleFingerprint = field(default_factory=StyleFingerprint)

    # 冷却状态（从Æsir传递过来，防止重复模式）
    event_cooldown: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, default=str)

    @classmethod
    def from_json(cls, data: str) -> "NarrativeStatePackage":
        raw = json.loads(data)
        # 重建嵌套对象
        if raw.get("genre_contract") and isinstance(raw["genre_contract"], dict):
            raw["genre_contract"] = GenreContract(**raw["genre_contract"])
        # 重建角色
        chars = []
        for c in raw.get("characters", []):
            char_seed = CharacterSeed(name=c["name"], role=c.get("role", ""))
            for k, v in c.get("beliefs", {}).items():
                char_seed.beliefs[k] = BeliefState(**v)
            for g in c.get("goals", []):
                char_seed.goals.append(GoalState(**g))
            for s in c.get("secrets", []):
                char_seed.secrets.append(SecretState(**s))
            if "personality_traits" in c and c["personality_traits"]:
                char_seed.personality_traits = c["personality_traits"]
            chars.append(char_seed)
        raw["characters"] = chars
        # 重建线索
        raw["open_threads"] = [OpenThread(**t) for t in raw.get("open_threads", [])]
        # 重建风格指纹
        if raw.get("style_fingerprint") and isinstance(raw["style_fingerprint"], dict):
            raw["style_fingerprint"] = StyleFingerprint(**raw["style_fingerprint"])
        # 重建结构
        if raw.get("structure") and isinstance(raw["structure"], dict):
            raw["structure"] = SG5Structure(**raw["structure"])
        return cls(**raw)

    def validate(self) -> list[str]:
        """对NSEF包进行完整性检查，返回缺失列表"""
        issues = []
        if not self.premise:
            issues.append("缺少前提句")
        if not self.unit_text:
            issues.append("缺少故事单元文本")
        if not self.characters:
            issues.append("没有角色种子——ToM引擎无法初始化")
        if not self.open_threads:
            issues.append("没有未闭合线索——延展引擎缺少锚点")
        return issues
