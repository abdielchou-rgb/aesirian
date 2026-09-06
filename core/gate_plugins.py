"""
Gate Plugin Architecture — Replaces 350-line if/elif chain with plugin system

Each gate = independent plugin class with typed input/output.
Supports hot-reload, isolation, priority ordering, and dependency injection.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Type
import inspect
import logging

logger = logging.getLogger(__name__)


class GateLevel(Enum):
    BLOCK = 0
    WARN = 1
    PASS = 2


class GatePhase(Enum):
    PRE_GENERATION = "pre_generation"   # G1-G5
    POST_CHAPTER = "post_chapter"       # G6-G10


@dataclass
class GateContext:
    """统一的门禁上下文 - 所有门禁共享的输入"""
    # 文本内容
    text: str = ""
    chapter_number: int = 0
    project_id: str = ""

    # 实体提取结果
    facts: list[dict] = field(default_factory=list)
    char_actions: list[dict] = field(default_factory=list)
    identity_changes: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    movements: list[dict] = field(default_factory=list)

    # NER 详细结果
    ner_entities: list[dict] = field(default_factory=list)

    # 统计指标
    char_count: int = 0
    touchpoints: int = 0
    direct_emotions: int = 0
    gap_densities: list[float] = field(default_factory=list)
    gap_count: int = 0
    dialogue_lines: int = 0
    line_count: int = 0
    paragraph_count: int = 0
    first_hook_position: int = 99999
    character_count: int = 0
    words_since_last_gap: int = 0

    # 结构字段（跨章上下文）
    entry_value: str = ""
    exit_value: str = ""
    recent_scene_flips: list = field(default_factory=list)
    value_pair_counts: dict = field(default_factory=dict)
    has_irreversible_turn: bool = False
    act_number: int = 1
    has_conscious_desire: bool = False
    has_unconscious_desire: bool = False
    is_reversible: bool = True
    character: dict = field(default_factory=dict)
    active_layers: list = field(default_factory=list)
    has_crossover: bool = False
    external_intensity: float = 0
    internal_intensity: float = 0
    chapters_since_new_gap: int = 0
    chapters_since_resolution: int = 0
    total_open_gaps: int = 0
    net_gap_rate: float = 0
    max_open_gaps: int = 15
    scene_id: str = ""
    touchpoint_emotion: str = ""
    context_emotion: str = ""
    declared_platform: str = ""
    active_template: str = ""
    platform: str = "webnovel"
    hook_position_limit: int = 150
    chapters_between_mini_climax: int = 5
    first_conflict_position: int = 99999
    protagonist_in_ch1: bool = True
    why_questions: int = 1
    has_cliffhanger: bool = False
    has_unresolved: bool = False
    position_pct: float = 0
    inciting_position: float = 0
    act_pct: float = 0
    act_sentiment: float = 0
    chapter_sentiment: float = 0
    webnovel_rhythm_score: float = 0
    webnovel_rhythm_verdict: str = ""
    readability: float = 0
    pos_distribution: dict = field(default_factory=dict)
    difficult_word_ratio: float = 0
    avg_sentence_len: float = 0
    previous_exit: str = ""
    current_entry: str = ""
    chain_strength: float = 1
    pov_beliefs: dict = field(default_factory=dict)
    recap_interval: int = 4
    goal_restatement_interval: int = 3
    foreshadow_mentions: int = 0
    anchor_context: str = ""
    misunderstanding_cycles: int = 0
    broken_chains: int = 0
    abrupt_transitions: int = 0
    projected_chapters: int = 30
    relationship_map: dict = field(default_factory=dict)
    active_template: str = ""
    domain_tags: list = field(default_factory=list)
    problem_stated: bool = False
    solution_applied: bool = False

    # 内部状态
    _skip_flags: dict = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def set(self, key: str, value: Any):
        setattr(self, key, value)


@dataclass
class GateResult:
    """门禁检查结果"""
    gate_id: str
    gate_name: str
    level: GateLevel
    passed: bool
    message: str = ""
    detail: str = ""
    suggestion: str = ""
    skipped: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "gate_id": self.gate_id,
            "gate_name": self.gate_name,
            "level": self.level.name,
            "passed": self.passed,
            "message": self.message,
            "detail": self.detail,
            "suggestion": self.suggestion,
            "skipped": self.skipped,
            "metadata": self.metadata,
        }


class GatePlugin(ABC):
    """门禁插件基类 - 每个门禁实现这个接口"""

    # 类属性：门禁元数据
    gate_id: str = ""
    gate_name: str = ""
    phase: GatePhase = GatePhase.PRE_GENERATION
    severity: GateLevel = GateLevel.WARN
    priority: int = 100  # 执行优先级，数值越小越先执行
    requires_context: list[str] = field(default_factory=list)  # 需要的上下文字段
    skip_conditions: list[str] = field(default_factory=list)  # 跳过条件

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._dependencies: dict = {}

    def set_dependencies(self, **deps):
        """注入依赖"""
        self._dependencies.update(deps)

    @abstractmethod
    def evaluate(self, ctx: GateContext) -> GateResult:
        """执行门禁检查"""
        pass

    def should_skip(self, ctx: GateContext) -> tuple[bool, str]:
        """检查是否应该跳过"""
        for cond in self.skip_conditions:
            if cond == "structural" and any(
                ctx.get(f) in (None, "", [], {}) for f in self.requires_context
            ):
                return True, f"结构门禁需跨章数据（缺: {', '.join(self.requires_context[:3])}）"
            if cond == "progression" and ctx.chapter_number < self.config.get("min_chapter", 0):
                return True, f"该门禁需至少第{self.config.get('min_chapter', 0)+1}章上下文"
        return False, ""

    def pass_result(self, message: str = "", detail: str = "", suggestion: str = "") -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            level=self.severity,
            passed=True,
            message=message,
            detail=detail,
            suggestion=suggestion,
        )

    def warn_result(self, message: str, detail: str = "", suggestion: str = "") -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            level=GateLevel.WARN,
            passed=False,
            message=message,
            detail=detail,
            suggestion=suggestion,
        )

    def block_result(self, message: str, detail: str = "", suggestion: str = "") -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            level=GateLevel.BLOCK,
            passed=False,
            message=message,
            detail=detail,
            suggestion=suggestion,
        )

    def skip_result(self, reason: str) -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            level=self.severity,
            passed=True,
            message=f"SKIPPED — {reason}",
            skipped=True,
        )


# ─── Plugin Registry ───

class GateRegistry:
    """门禁注册表 - 管理所有门禁插件"""

    def __init__(self):
        self._plugins: dict[str, GatePlugin] = {}
        self._plugin_classes: dict[str, Type[GatePlugin]] = {}
        self._initialized = False

    def register(self, plugin_class: Type[GatePlugin], config: dict = None) -> GatePlugin:
        """注册门禁插件类"""
        instance = plugin_class(config)
        instance.set_dependencies(**self._dependencies)
        self._plugins[instance.gate_id] = instance
        self._plugin_classes[instance.gate_id] = plugin_class
        logger.debug(f"Registered gate: {instance.gate_id} ({instance.gate_name})")
        return instance

    def register_instance(self, instance: GatePlugin):
        """注册已实例化的门禁"""
        self._plugins[instance.gate_id] = instance
        logger.debug(f"Registered gate instance: {instance.gate_id}")

    def get(self, gate_id: str) -> Optional[GatePlugin]:
        return self._plugins.get(gate_id)

    def get_all(self) -> list[GatePlugin]:
        """获取所有门禁，按优先级排序"""
        return sorted(self._plugins.values(), key=lambda p: p.priority)

    def get_by_phase(self, phase: GatePhase) -> list[GatePlugin]:
        return [p for p in self.get_all() if p.phase == phase]

    def set_dependencies(self, **deps):
        self._dependencies = deps
        for plugin in self._plugins.values():
            plugin.set_dependencies(**deps)

    def unregister(self, gate_id: str):
        self._plugins.pop(gate_id, None)
        self._plugin_classes.pop(gate_id, None)


# 全局注册表
gate_registry = GateRegistry()


# ─── Decorator for Easy Registration ───

def gate_plugin(
    gate_id: str,
    gate_name: str,
    phase: GatePhase = GatePhase.PRE_GENERATION,
    severity: GateLevel = GateLevel.WARN,
    priority: int = 100,
    requires_context: list[str] = None,
    skip_conditions: list[str] = None,
):
    """装饰器：将函数注册为门禁插件"""
    def decorator(func):
        class _FunctionGate(GatePlugin):
            gate_id = gate_id
            gate_name = gate_name
            phase = phase
            severity = severity
            priority = priority
            requires_context = requires_context or []
            skip_conditions = skip_conditions or []

            def evaluate(self, ctx: GateContext) -> GateResult:
                return func(ctx, self)

        # 使用函数名作为默认 gate_name
        gate_name = getattr(func, "__name__", gate_id).replace("_", " ").title()

        # 实例化并注册
        plugin = _FunctionGate()
        gate_registry.register_instance(plugin)
        return plugin

    return decorator


# ─── Built-in Gate Implementations ───

class G1FactConsistency(GatePlugin):
    """G1 事实一致性"""
    gate_id = "G1"
    gate_name = "事实一致性"
    phase = GatePhase.PRE_GENERATION
    severity = GateLevel.BLOCK
    priority = 10
    requires_context = ["facts"]
    skip_conditions = ["structural"]

    def evaluate(self, ctx: GateContext) -> GateResult:
        kg = self._dependencies.get("knowledge_graph")
        if not kg:
            return self.skip_result("知识图谱不可用")

        for fact in ctx.facts:
            subject = fact.get("subject", "")
            predicate = fact.get("predicate", "")
            obj = fact.get("object", "")
            if not subject:
                continue

            conflicts = kg.detect_conflicts(f"{predicate}{obj}", subject)
            if conflicts:
                return self.block_result(
                    f"事实矛盾：{'; '.join(conflicts)}",
                    detail=f"文本声称「{subject}{predicate}{obj}」，但已有图谱显示矛盾",
                    suggestion="修正事实陈述或提供转变解释",
                )
        return self.pass_result()


class G2BeliefConsistency(GatePlugin):
    """G2 信念一致性"""
    gate_id = "G2"
    gate_name = "信念一致性"
    phase = GatePhase.PRE_GENERATION
    severity = GateLevel.WARN
    priority = 20
    requires_context = ["char_actions"]
    skip_conditions = ["structural"]

    def evaluate(self, ctx: GateContext) -> GateResult:
        tom = self._dependencies.get("tom_engine")
        if not tom:
            return self.skip_result("ToM引擎不可用")

        for action in ctx.char_actions:
            char_id = action.get("character_id", "")
            action_desc = action.get("description", "")
            if not char_id or not action_desc:
                continue

            conflict = tom.validate_action(char_id, action_desc)
            if conflict:
                char = tom.get_character(char_id)
                if char and len(char.world_beliefs) > 3:
                    return self.warn_result(
                        f"角色行为与信念不一致：{conflict}",
                        detail="需要添加合理解释（角色'发现了新证据'或'被迫伪装'）",
                        suggestion="给角色一个改变行为的内在动机",
                    )
                return self.block_result(
                    f"角色行为严重违背信念：{conflict}",
                    detail="没有任何信念层面的解释",
                )
        return self.pass_result()


class G9DeAIDetection(GatePlugin):
    """G9 去AI化检测"""
    gate_id = "G9"
    gate_name = "去AI化检测"
    phase = GatePhase.POST_CHAPTER
    severity = GateLevel.WARN
    priority = 90
    requires_context = ["text"]

    AI_MARKERS = ["然而", "值得注意的是", "不可否认", "不出所料", "愈发",
                  "毫无疑问", "显而易见", "值得一提的是", "令人惊讶的是"]
    HEDGE_WORDS = ["似乎", "可能", "或许", "大概", "某种程度上", "一定程度上", "在某种意义上"]
    TRANSITION_WORDS = ["然而", "不过", "与此同时", "突然", "随即", "接着", "然后", "可是", "但是", "却"]

    def evaluate(self, ctx: GateContext) -> GateResult:
        text = ctx.text
        if not text or len(text) < 50:
            return self.pass_result()

        sentences = [s.strip() for s in text.split("。") if s.strip()]
        if len(sentences) < 5:
            return self.pass_result()

        # AI标志词
        marker_count = sum(text.count(m) for m in self.AI_MARKERS)

        # 句式重复
        openings = []
        import re
        for s in sentences[:min(10, len(sentences))]:
            match = re.match(r'^[一-鿿]{2,3}[着了的]', s)
            if match:
                openings.append(match.group(0))

        repeated_patterns = len(openings) > 3 and len(set(openings)) < len(openings) * 0.5

        warnings = []
        if marker_count >= 3:
            warnings.append(f"AI标志词出现{marker_count}次（阈值3）")
        if repeated_patterns:
            warnings.append("句子开头模式重复")

        if warnings:
            return self.warn_result(
                "; ".join(warnings),
                detail="建议使用口语化表达、打断对话、非典型词汇",
                suggestion="每段留1-2处非标准表达，打破'完美文本'模式",
            )
        return self.pass_result()


# ─── Convenience Functions ───

def create_gate_registry(kg=None, tom=None, reader=None) -> GateRegistry:
    """创建并配置门禁注册表"""
    registry = GateRegistry()
    registry.set_dependencies(
        knowledge_graph=kg,
        tom_engine=tom,
        reader_model=reader,
    )

    # 注册内置门禁（按优先级）
    builtins = [
        G1FactConsistency,
        G2BeliefConsistency,
        # 更多门禁...
        G9DeAIDetection,
    ]

    for cls in builtins:
        registry.register(cls)

    return registry


def run_gates(ctx: GateContext, phase: GatePhase, registry: GateRegistry = None) -> list[GateResult]:
    """运行指定阶段的所有门禁"""
    registry = registry or gate_registry
    results = []

    for plugin in registry.get_by_phase(phase):
        # 检查跳过条件
        should_skip, reason = plugin.should_skip(ctx)
        if should_skip:
            results.append(plugin.skip_result(reason))
            continue

        try:
            result = plugin.evaluate(ctx)
            results.append(result)
        except Exception as e:
            logger.error(f"Gate {plugin.gate_id} evaluation failed: {e}")
            results.append(GateResult(
                gate_id=plugin.gate_id,
                gate_name=plugin.gate_name,
                level=plugin.severity,
                passed=False,
                message=f"evaluation error: {e}",
            ))

    return results


def create_audit_report(chapter: int, results: list[GateResult]) -> dict:
    """创建审计报告"""
    passed = sum(1 for r in results if r.passed and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    blocked = sum(1 for r in results if not r.passed and not r.skipped and r.level == GateLevel.BLOCK)
    warned = sum(1 for r in results if not r.passed and not r.skipped and r.level == GateLevel.WARN)

    overall_score = 100
    for r in results:
        if not r.passed and not r.skipped:
            penalty = 20 if r.level == GateLevel.BLOCK else 10
            overall_score = max(0, overall_score - penalty)

    return {
        "chapter": chapter,
        "overall_score": overall_score,
        "summary": {"passed": passed, "blocked": blocked, "warned": warned, "skipped": skipped},
        "results": [r.to_dict() for r in results],
    }