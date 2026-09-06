"""
时序知识图谱 (Temporal Knowledge Graph) v1

核心能力：
1. 节点类型：角色、事件、物品、地点、关系——全部带时间戳
2. 章节提交通道：每章完成后自动更新所有受影响节点
3. 15+维度状态快照：每次提交后生成事实状态核查快照
4. 时序查询："第300章时，主角知道自己的身世吗？"
5. 冲突检测：新事件写入前自动扫描对所有节点的影响
6. 因果图追踪：事件A → 导致事件B → 导致状态C

学术基础：
- DOME (arXiv:2412.13575): 时序知识图谱用于长篇故事记忆增强
- Event Model (Magliano, 2024): 读者阅读时实时构建事件模型
- A Character-Centric Creative Story Generation (2024): 以角色为中心的叙事状态追踪
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ═══════════════════════════════════════════
# 节点与边定义
# ═══════════════════════════════════════════


class NodeType(Enum):
    CHARACTER = "角色"
    EVENT = "事件"
    ITEM = "物品"
    LOCATION = "地点"
    RELATIONSHIP = "关系"
    THEME = "主题"


class EdgeType(Enum):
    CAUSES = "导致"
    PARTICIPATES = "参与"
    OWNS = "拥有"
    LOCATED_AT = "位于"
    KNOWS = "知道"
    RELATES_TO = "关联"
    LEADS_TO = "导致事件"
    REVEALS = "揭示"


@dataclass
class Node:
    """知识图谱节点"""

    id: str
    name: str
    type: NodeType
    properties: dict = field(default_factory=dict)
    created_at_chapter: int = 0
    updated_at_chapter: int = 0

    # 临时节点生命周期（SAGA模式）
    is_provisional: bool = False  # 是否为临时节点
    provisional_confidence: float = 0.0  # 置信度 0.0-1.0
    is_enriched: bool = False  # 是否已被LLM丰富属性
    graduated_at: int | None = None  # 毕业章节
    enriched_traits: list[str] = field(default_factory=list)  # 被推断的特质

    @property
    def ready_to_graduate(self) -> bool:
        """是否满足毕业条件：置信度>=0.75且存在>=1章"""
        return self.is_provisional and self.provisional_confidence >= 0.75 and self.age >= 1

    @property
    def age(self) -> int:
        """节点存在时间（以章节计）"""
        return max(0, self.updated_at_chapter - self.created_at_chapter)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "properties": self.properties,
            "created_at": self.created_at_chapter,
            "updated_at": self.updated_at_chapter,
            "is_provisional": self.is_provisional,
            "confidence": self.provisional_confidence,
            "is_enriched": self.is_enriched,
            "graduated_at": self.graduated_at,
        }


@dataclass
class Edge:
    """知识图谱边——带条件的时间戳"""

    source: str  # 源节点ID
    target: str  # 目标节点ID
    type: EdgeType
    properties: dict = field(default_factory=dict)
    valid_from_chapter: int = 0
    valid_to_chapter: int | None = None  # None = 至今有效
    is_active: bool = True

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type.value,
            "properties": self.properties,
            "valid_from": self.valid_from_chapter,
            "valid_to": self.valid_to_chapter,
            "active": self.is_active,
        }


@dataclass
class FactSnapshot:
    """事实状态快照——每章提交后生成

    15+ 维度的状态核查：
    - 角色存活状况
    - 角色关系状态
    - 关键物品持有者
    - 未解秘密数量
    - 已揭示真相
    - 势力平衡状态
    """

    chapter: int
    character_status: dict[str, str] = field(default_factory=dict)
    relationship_map: dict[str, str] = field(default_factory=dict)
    key_items_holders: dict[str, str] = field(default_factory=dict)
    unresolved_secrets: int = 0
    open_thread_count: int = 0
    faction_balance: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "character_status": self.character_status,
            "relationship_map": self.relationship_map,
            "key_items": self.key_items_holders,
            "unresolved_secrets": self.unresolved_secrets,
            "open_threads": self.open_thread_count,
            "faction_balance": self.faction_balance,
        }


# ═══════════════════════════════════════════
# 时序知识图谱主类
# ═══════════════════════════════════════════


class TemporalKnowledgeGraph:
    """
    时序知识图谱——整个系统的"长期记忆"

    不是传统的关系数据库，它存储的是随时间演变的故事状态。
    每个节点和边都有时间范围（valid_from / valid_to），
    支持"快照"和"时序回溯"查询。
    """

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.snapshots: list[FactSnapshot] = []
        self.current_chapter: int = 0

        # 索引加速查询
        self._node_by_name: dict[str, str] = {}  # name → id
        self._edges_from: dict[str, list[Edge]] = defaultdict(list)
        self._edges_to: dict[str, list[Edge]] = defaultdict(list)

    # ═══════════════════════════════════════
    # 节点操作
    # ═══════════════════════════════════════

    def add_node(
        self,
        name: str,
        type: NodeType,
        properties: dict = None,
        provisional: bool = False,
        confidence: float = 0.0,
    ) -> Node:
        """添加一个节点

        Args:
            name: 节点名称
            type: 节点类型
            properties: 属性
            provisional: 是否为临时节点（SAGA模式：由文本涌现创建，待丰富后毕业）
            confidence: 临时节点的初始置信度
        """
        if name in self._node_by_name:
            return self.nodes[self._node_by_name[name]]

        nid = uuid.uuid4().hex[:12]
        node = Node(
            id=nid,
            name=name,
            type=type,
            properties=properties or {},
            created_at_chapter=self.current_chapter,
            updated_at_chapter=self.current_chapter,
            is_provisional=provisional,
            provisional_confidence=confidence,
        )
        self.nodes[nid] = node
        self._node_by_name[name] = nid
        return node

    def enrich_node(
        self,
        node_id: str,
        traits: list[str] = None,
        description: str = "",
        confidence_boost: float = 0.0,
    ) -> Node | None:
        """丰富临时节点的属性（SAGA enrich阶段）"""
        node = self.nodes.get(node_id)
        if not node or not node.is_provisional:
            return node
        if traits:
            node.enriched_traits = list(set(node.enriched_traits + traits))
            node.properties["traits"] = node.enriched_traits
        if description:
            node.properties["description"] = description
        node.is_enriched = True
        node.provisional_confidence = min(1.0, node.provisional_confidence + confidence_boost)
        node.updated_at_chapter = self.current_chapter
        return node

    def graduate_node(self, node_id: str) -> Node | None:
        """将临时节点毕业为正式节点（SAGA graduate阶段）"""
        node = self.nodes.get(node_id)
        if not node or not node.ready_to_graduate:
            return node
        node.is_provisional = False
        node.graduated_at = self.current_chapter
        node.updated_at_chapter = self.current_chapter
        return node

    def get_provisional_nodes(self) -> list[Node]:
        """获取所有未毕业的临时节点"""
        return [n for n in self.nodes.values() if n.is_provisional]

    def calculate_node_confidence(self, node: Node) -> float:
        """计算节点的综合置信度（SAGA算法）

        加权公式：连接度40% + 完整性30% + 持续时长30%
        """
        # 连接度：相邻边数量/3
        degree = len(self._edges_from.get(node.id, [])) + len(self._edges_to.get(node.id, []))
        connectivity = min(degree / 3, 1.0) * 0.4

        # 完整性：描述长度>20 +0.2，有特质+0.1，状态非Unknown+0.1
        desc = node.properties.get("description", "")
        completeness = 0.0
        if len(desc) > 20:
            completeness += (0.2 / 0.4) * 0.3
        if node.properties.get("traits"):
            completeness += (0.1 / 0.4) * 0.3
        if node.properties.get("status", "") not in ("", "unknown"):
            completeness += (0.1 / 0.4) * 0.3

        # 持续时长
        longevity = 0.0
        if node.age >= 4:
            longevity = 0.2
        elif node.age >= 2:
            longevity = 0.1

        confidence = connectivity + completeness + longevity
        node.provisional_confidence = min(1.0, confidence)
        return node.provisional_confidence

    def heal_provisional_nodes(self, enrich_fn=None) -> dict:
        """执行全量临时节点修复

        Args:
            enrich_fn: LLM丰富回调函数（可选）。签名：f(node) -> (traits, description, confidence_boost)
                       不提供时只做统计计算不作为
        Returns:
            统计数据：{total, enriched, graduated, cleanup}
        """
        stats = {
            "total": len(self.get_provisional_nodes()),
            "enriched": 0,
            "graduated": 0,
            "cleanup": 0,
        }

        for node in list(self.get_provisional_nodes()):
            # 计算置信度
            self.calculate_node_confidence(node)

            # 清理孤立节点（超过3章且无关系）
            has_relations = bool(self._edges_from.get(node.id) or self._edges_to.get(node.id))
            if node.age > 3 and not has_relations:
                del self.nodes[node.id]
                if node.name in self._node_by_name and self._node_by_name[node.name] == node.id:
                    del self._node_by_name[node.name]
                stats["cleanup"] += 1
                continue

            # 丰富（如果有回调）
            if enrich_fn and not node.is_enriched:
                try:
                    traits, desc, boost = enrich_fn(node)
                    self.enrich_node(
                        node.id, traits=traits, description=desc, confidence_boost=boost
                    )
                    stats["enriched"] += 1
                except Exception:
                    pass

            # 毕业（满足条件）
            if node.ready_to_graduate:
                self.graduate_node(node.id)
                stats["graduated"] += 1

        return stats

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def get_node_by_name(self, name: str) -> Node | None:
        nid = self._node_by_name.get(name)
        return self.nodes.get(nid) if nid else None

    def update_node_property(self, node_id: str, key: str, value):
        """更新节点属性"""
        node = self.nodes.get(node_id)
        if node:
            node.properties[key] = value
            node.updated_at_chapter = self.current_chapter

    # ═══════════════════════════════════════
    # 边操作
    # ═══════════════════════════════════════

    def add_edge(
        self, source_name: str, target_name: str, edge_type: EdgeType, properties: dict = None
    ) -> Edge | None:
        """在两个节点之间添加关系边

        如果节点不存在，自动创建。
        """
        src = self.get_node_by_name(source_name)
        if not src:
            src = self.add_node(source_name, NodeType.CHARACTER, {"auto_created": True})
        tgt = self.get_node_by_name(target_name)
        if not tgt:
            # 根据边类型推断目标节点类型
            inferred_type = {
                EdgeType.LOCATED_AT: NodeType.LOCATION,
                EdgeType.OWNS: NodeType.ITEM,
                EdgeType.PARTICIPATES: NodeType.EVENT,
                EdgeType.LEADS_TO: NodeType.EVENT,
            }.get(edge_type, NodeType.CHARACTER)
            tgt = self.add_node(target_name, inferred_type, {"auto_created": True})

        edge = Edge(
            source=src.id,
            target=tgt.id,
            type=edge_type,
            properties=properties or {},
            valid_from_chapter=self.current_chapter,
        )
        self.edges.append(edge)
        self._edges_from[src.id].append(edge)
        self._edges_to[tgt.id].append(edge)
        return edge

    def get_relations(self, node_name: str, edge_type: EdgeType | None = None) -> list[Edge]:
        """获取一个节点的所有关系"""
        node = self.get_node_by_name(node_name)
        if not node:
            return []

        results = self._edges_from.get(node.id, []) + self._edges_to.get(node.id, [])
        if edge_type:
            results = [e for e in results if e.type == edge_type]
        return [e for e in results if e.is_active]

    def deactivate_edge(self, source_name: str, target_name: str, edge_type: EdgeType):
        """标记关系为失效（关系破裂/死亡/物品易主）"""
        src = self.get_node_by_name(source_name)
        tgt = self.get_node_by_name(target_name)
        if not src or not tgt:
            return

        for edge in self.edges:
            if (
                edge.source == src.id
                and edge.target == tgt.id
                and edge.type == edge_type
                and edge.is_active
            ):
                edge.is_active = False
                edge.valid_to_chapter = self.current_chapter

    # ═══════════════════════════════════════
    # 时序查询
    # ═══════════════════════════════════════

    def query_at_chapter(self, chapter: int) -> dict:
        """查询指定章节时的故事状态快照"""
        result: dict[str, list[str]] = {
            "character_relationships": [],
            "active_events": [],
        }
        for edge in self.edges:
            if (
                edge.valid_from_chapter <= chapter
                and (edge.valid_to_chapter is None or edge.valid_to_chapter >= chapter)
            ):
                src = self.nodes.get(edge.source)
                tgt = self.nodes.get(edge.target)
                if src and tgt:
                        result["character_relationships"].append(
                            f"{src.name} --[{edge.type.value}]--> {tgt.name}"
                        )
        return result

    def when_did(self, fact: str) -> int | None:
        """查询某个事实在哪个章节成立的——"主角什么时候知道自己是被收养的？" """
        for edge in self.edges:
            if edge.properties.get("fact") == fact or fact in str(edge.properties):
                return edge.valid_from_chapter
        return None

    # ═══════════════════════════════════════
    # 冲突检测
    # ═══════════════════════════════════════

    def detect_conflicts(self, fact_statement: str, source_name: str) -> list[str]:
        """检测新写入的事实是否与已有知识冲突

        输入一句话事实描述，输出所有冲突的知识条目。
        这是 G1 事实一致性门禁的核心逻辑。
        """
        conflicts = []
        node = self.get_node_by_name(source_name)
        if not node:
            return []

        # 检查节点属性冲突
        import re

        for prop, val in node.properties.items():
            # 如果属性名出现在事实陈述中，或属性值可以被比较
            prop_in_fact = prop.lower() in fact_statement.lower()

            for truth_val in [val] if not isinstance(val, list) else val:
                str_truth = str(truth_val)

                # 数字属性特殊处理
                if isinstance(truth_val, (int, float)):
                    numbers = re.findall(r"\d+", fact_statement)
                    if numbers and str_truth not in numbers:
                        conflicts.append(
                            f"与{node.name}的属性「{prop}={truth_val}」矛盾（事实中提到{numbers[0]}）"
                        )
                elif prop_in_fact and str_truth not in fact_statement:
                    negations = ["不", "没", "没有", "否认"]
                    if not any(n in fact_statement for n in negations):
                        conflicts.append(f"与{node.name}的属性「{prop}={truth_val}」矛盾")

        return conflicts

    def check_temporal_consistency(self, event_name: str, expected_chapter: int) -> str | None:
        """检查一个事件在给定章节是否合理

        例如：角色在第三章不认识某人，但不应该在第一章就提到其名字
        """
        event_node = self.get_node_by_name(event_name)
        if not event_node:
            return None

        if event_node.created_at_chapter > expected_chapter:
            return (
                f"事件「{event_name}」在第{event_node.created_at_chapter}章才发生，"
                f"但试图在第{expected_chapter}章引用"
            )

        # 检查参与该事件的角色在事件发生时是否存在
        for edge in self._edges_to.get(event_node.id, []):
            src = self.nodes.get(edge.source)
            if src and edge.type == EdgeType.PARTICIPATES and src.created_at_chapter > expected_chapter:
                return (
                    f"角色「{src.name}」第{src.created_at_chapter}章才出现，"
                    f"但参与的事件「{event_name}」在第{expected_chapter}章"
                )
        return None

    # ═══════════════════════════════════════
    # 章节提交
    # ═══════════════════════════════════════

    def commit_chapter_snapshot(self) -> FactSnapshot:
        """每章完成后：生成全量事实状态快照"""
        snapshot = FactSnapshot(chapter=self.current_chapter)

        # 角色存活状态
        for node in self.nodes.values():
            if node.type == NodeType.CHARACTER:
                status = node.properties.get("status", "unknown")
                snapshot.character_status[node.name] = status

        # 关系摘要（只取活跃关系）
        for edge in self.edges:
            src = self.nodes.get(edge.source)
            tgt = self.nodes.get(edge.target)
            if src and tgt and edge.is_active:
                key = f"{src.name}↔{tgt.name}"
                if key not in snapshot.relationship_map:
                    snapshot.relationship_map[key] = edge.type.value

        # 关键物品持有者
        for edge in self.edges:
            if edge.type == EdgeType.OWNS and edge.is_active:
                src = self.nodes.get(edge.source)
                tgt = self.nodes.get(edge.target)
                if src and tgt:
                    snapshot.key_items_holders[tgt.name] = src.name

        # 统计
        secrets_count = sum(
            1
            for n in self.nodes.values()
            if n.type == NodeType.CHARACTER and n.properties.get("has_secret")
        )
        snapshot.unresolved_secrets = secrets_count
        snapshot.open_thread_count = len(
            [
                n
                for n in self.nodes.values()
                if n.type == NodeType.EVENT and n.properties.get("is_open_thread", False)
            ]
        )

        self.snapshots.append(snapshot)
        self.current_chapter += 1
        return snapshot

    # ═══════════════════════════════════════
    # 因果图
    # ═══════════════════════════════════════

    def get_causality_chain(self, start_event: str) -> list[str]:
        """从起始事件追踪因果链

        返回：["事件A", "导致→事件B", "导致→事件C", ...]
        """
        chain = [start_event]
        node = self.get_node_by_name(start_event)
        if not node:
            return chain

        visited = {node.id}
        current = node

        while True:
            next_edges = [
                e
                for e in self._edges_from.get(current.id, [])
                if e.type == EdgeType.LEADS_TO and e.target not in visited
            ]
            if not next_edges:
                break

            next_edge = next_edges[0]
            next_node = self.nodes.get(next_edge.target)
            if not next_node:
                break

            chain.append(f" 导致→ {next_node.name}")
            visited.add(next_node.id)
            current = next_node

        return chain

    # ═══════════════════════════════════════
    # 序列化
    # ═══════════════════════════════════════

    def to_dict(self) -> dict:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "current_chapter": self.current_chapter,
            "snapshot_count": len(self.snapshots),
        }

    @classmethod
    def from_dict(cls, data: dict) -> TemporalKnowledgeGraph:
        kg = cls()
        kg.current_chapter = data.get("current_chapter", 0)
        for nid, ndata in data.get("nodes", {}).items():
            node = Node(
                id=nid,
                name=ndata["name"],
                type=NodeType(ndata["type"]),
                properties=ndata.get("properties", {}),
                created_at_chapter=ndata.get("created_at", 0),
                updated_at_chapter=ndata.get("updated_at", 0),
            )
            kg.nodes[nid] = node
            kg._node_by_name[node.name] = nid
        for edata in data.get("edges", []):
            edge = Edge(
                source=edata["source"],
                target=edata["target"],
                type=EdgeType(edata["type"]),
                properties=edata.get("properties", {}),
                valid_from_chapter=edata.get("valid_from", 0),
                valid_to_chapter=edata.get("valid_to"),
                is_active=edata.get("active", True),
            )
            kg.edges.append(edge)
            kg._edges_from[edge.source].append(edge)
            kg._edges_to[edge.target].append(edge)
        return kg
