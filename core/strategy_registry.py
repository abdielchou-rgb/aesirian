"""
方法论注册表 — Æsirian 元策略层核心

将知识底座中30+方法论体系翻译为可执行的策略节点。
每个方法论有一组触发条件、输入/输出类型、评估维度。

设计原则：
1. 每个方法论节点独立可测试
2. 支持链式组合（多个方法论串联）
3. 每个策略输出带有来源标注（"这个建议来自Campbell英雄之旅"）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable
from datetime import datetime


class MethodologyFamily(Enum):
    NARRATIVE_STRUCTURE = "narrative_structure"  # 叙事结构族
    NARRATIVE_ATOM = "narrative_atom"            # 叙事原子族
    CREATIVE_COGNITION = "creative_cognition"     # 创意认知族
    GENRE_CONTRACT = "genre_contract"             # 类型契约族
    CHARACTER_SYSTEM = "character_system"         # 角色系统族
    COGNITIVE_SCIENCE = "cognitive_science"        # 认知科学族
    QUALITY_GATE = "quality_gate"                  # 质量标准族
    ENGINEERING = "engineering"                    # 工程实践族


class TriggerEvent(Enum):
    FRAGMENT_INPUT = "fragment_input"              # 用户输入碎片
    CHAPTER_SUBMIT = "chapter_submit"              # 章节提交时
    ARC_PLANNING = "arc_planning"                  # 弧线规划
    CHARACTER_CREATE = "character_create"          # 角色创建
    DIVERGENCE = "divergence"                      # 发散
    CONVERGENCE = "convergence"                    # 收敛
    AUDIT = "audit"                                # 审计
    POST_CHAPTER = "post_chapter"                  # 章后
    STYLE_EXTRACT = "style_extract"                # 风格提取


class OutputType(Enum):
    DIRECTION = "direction"          # 方向（用于发散）
    CONSTRAINT = "constraint"        # 约束（用于生成）
    ASSESSMENT = "assessment"        # 评估（用于审计）
    INSIGHT = "insight"              # 洞察（用于建议）
    TRANSFORMATION = "transformation" # 变换操作


@dataclass
class StrategyResult:
    """一个方法论策略的执行结果"""
    source_method: str        # 方法论名称
    source_family: str        # 族名称
    output_type: OutputType
    content: str
    confidence: float = 0.8
    applicable_to: list[str] = field(default_factory=list)  # 适用于

@dataclass
class MethodologyNode:
    """一个可执行的方法论策略节点"""
    id: str
    name: str
    family: MethodologyFamily
    source: str
    description: str = ""

    # 触发条件
    trigger_events: list[TriggerEvent] = field(default_factory=list)
    required_context: list[str] = field(default_factory=list)  # 需要的上下文字段

    # 输入输出
    input_type: str = ""
    output_type: OutputType = OutputType.INSIGHT

    # 权重和状态
    weight: float = 1.0
    enabled: bool = True

    # 关联方法（可以组合使用的方法ID）
    related_methods: list[str] = field(default_factory=list)
    incompatible_with: list[str] = field(default_factory=list)  # 不兼容

    # 执行钩子
    execute_fn: Optional[Callable] = field(default=None, repr=False, compare=False)

    def execute(self, context: dict) -> Optional[StrategyResult]:
        if not self.enabled or not self.execute_fn:
            return None
        return self.execute_fn(context, self)


class MethodologyRegistry:
    """方法论注册表 — 注册/查询/链式执行"""

    def __init__(self):
        self._nodes: dict[str, MethodologyNode] = {}
        self._families: dict[MethodologyFamily, list[str]] = {f: [] for f in MethodologyFamily}
        self._trigger_index: dict[TriggerEvent, list[str]] = {t: [] for t in TriggerEvent}

    def register(self, node: MethodologyNode):
        """注册一个方法论节点"""
        self._nodes[node.id] = node
        self._families[node.family].append(node.id)
        for event in node.trigger_events:
            self._trigger_index[event].append(node.id)

    def get(self, method_id: str) -> Optional[MethodologyNode]:
        return self._nodes.get(method_id)

    def get_by_family(self, family: MethodologyFamily) -> list[MethodologyNode]:
        return [self._nodes[nid] for nid in self._families.get(family, []) if nid in self._nodes]

    def get_by_trigger(self, event: TriggerEvent) -> list[MethodologyNode]:
        return [self._nodes[nid] for nid in self._trigger_index.get(event, []) if nid in self._nodes]

    def execute(self, method_id: str, context: dict) -> Optional[StrategyResult]:
        node = self._nodes.get(method_id)
        if not node:
            return None
        return node.execute(context)

    def execute_all(self, event: TriggerEvent, context: dict) -> list[StrategyResult]:
        results = []
        for node in self.get_by_trigger(event):
            result = node.execute(context)
            if result:
                results.append(result)
        return results

    def chain(self, method_ids: list[str], context: dict) -> list[StrategyResult]:
        """链式执行——将一个策略的输出作为下一个策略的输入补充"""
        results = []
        chain_context = dict(context)
        for mid in method_ids:
            result = self.execute(mid, chain_context)
            if result:
                results.append(result)
                chain_context['_last_result'] = result.content
        return results

    def all_nodes(self) -> list[MethodologyNode]:
        return list(self._nodes.values())

    def summary(self) -> dict:
        return {
            "total": len(self._nodes),
            "families": {f.value: len(nids) for f, nids in self._families.items()},
            "triggers": {t.value: len(nids) for t, nids in self._trigger_index.items()},
        }
