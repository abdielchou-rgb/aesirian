"""
Æsirian Orchestrator — 核心引擎编排层

将四个引擎（ToM、知识图谱、一致性门禁、读者模型）串联为统一API。
对外提供：
- NSEF导入（从Æsir接收故事种子）
- 初始化长篇项目
- 生成前门禁检查
- 写作推进（场景生成建议）
- 章后全量审计
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import json
import os
import sys

# 添加核心模块到路径
sys.path.insert(0, os.path.dirname(__file__))

from tom_engine import TheoryOfMindEngine, BeliefSource, Belief, Goal
from knowledge_graph import TemporalKnowledgeGraph, NodeType, EdgeType
from consistency_gates import ConsistencyGateSystem, GateLevel, AuditReport
from reader_model import ReaderModelSimulator, EventCooldownMatrix

# 桥接层
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bridge"))
from nsef import NarrativeStatePackage, CharacterSeed, BeliefState, OpenThread, SecretState

# 从桥接层导入NSEF
from nsef import NarrativeStatePackage, CharacterSeed, BeliefState, OpenThread, SecretState


@dataclass
class ProjectState:
    """一个叙事项目的完整状态"""
    project_id: str
    title: str = ""
    current_chapter: int = 0
    total_chapters: int = 0
    genre: str = ""

    # 引擎实例
    tom: TheoryOfMindEngine = field(default_factory=TheoryOfMindEngine)
    kg: TemporalKnowledgeGraph = field(default_factory=TemporalKnowledgeGraph)
    gates: ConsistencyGateSystem = field(default_factory=ConsistencyGateSystem)
    reader: ReaderModelSimulator = field(default_factory=ReaderModelSimulator)
    cooldown: EventCooldownMatrix = field(default_factory=EventCooldownMatrix)

    # 审计历史
    audit_reports: list[AuditReport] = field(default_factory=list)


class Orchestrator:
    """
    Æsirian 核心编排器

    串联四个引擎的工作流，提供"超级智能"所需的核心能力。
    """

    def __init__(self):
        self.projects: dict[str, ProjectState] = {}

    # ═══════════════════════════════════════
    # 项目生命周期
    # ═══════════════════════════════════════

    def create_project_from_nsef(self, nsef_path: str) -> ProjectState:
        """从NSEF文件（Æsir产出）创建叙事项目"""
        with open(nsef_path, "r", encoding="utf-8") as f:
            package = NarrativeStatePackage.from_json(f.read())

        # 验证完整性
        issues = package.validate()
        if issues:
            raise ValueError(f"NSEF包不完整：{'；'.join(issues)}")

        # 创建项目
        pid = package.package_id
        project = ProjectState(
            project_id=pid,
            title=package.premise[:50],  # 前提句作为初始标题
            genre=package.genre_contract.genre.value if package.genre_contract else "",
        )

        # 注入依赖
        project.gates.set_dependencies(
            kg=project.kg,
            tom=project.tom,
            reader=project.reader
        )

        # 初始化ToM引擎——从角色种子引导
        for char_seed in package.characters:
            char = project.tom.add_character(char_seed.name, char_seed.name)
            for prop, belief_state in char_seed.beliefs.items():
                char.world_beliefs[prop] = Belief(
                    proposition=prop,
                    value=belief_state.value,
                    confidence=1.0,
                    source=BeliefSource.DIRECT_WITNESS
                )
            for goal in char_seed.goals:
                char.active_goals.append(Goal(
                    description=goal.goal,
                    priority=goal.priority
                ))

        # 初始化知识图谱——注册角色和线索
        for char_seed in package.characters:
            project.kg.add_node(
                char_seed.name, NodeType.CHARACTER,
                properties={"role": char_seed.role}
            )
        for thread in package.open_threads:
            event_node = project.kg.add_node(
                thread.description, NodeType.EVENT,
                properties={"is_open_thread": True, "expected_resolution": thread.expected_resolution_type}
            )

        # 注册秘密
        for char_seed in package.characters:
            for secret in char_seed.secrets:
                project.tom.register_secret(
                    secret.secret,
                    known_to=secret.known_to,
                    hidden_from=secret.hidden_from
                )

        # 设置冷却矩阵
        for pattern, cooldown_val in package.event_cooldown.items():
            project.cooldown.matrix[pattern] = cooldown_val

        self.projects[pid] = project
        return project

    def get_project(self, project_id: str) -> Optional[ProjectState]:
        return self.projects.get(project_id)

    # ═══════════════════════════════════════
    # 写作推演
    # ═══════════════════════════════════════

    def generate_scene_constraints(self, project_id: str) -> dict:
        """生成场景的"写作约束"——给LLM的结构化输入

        ToM引擎、读者模型、冷却矩阵共同产出"应该怎么写"的约束。
        """
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        # ToM引擎：当前张力点 + 角色行动倾向
        tension = project.tom.detect_tension()
        tendencies = project.tom.infer_action_tendencies()

        # 读者模型：当前的认知状态
        reader_state = {
            "location": project.reader.model.current_location,
            "known_chars": project.reader.model.known_characters,
            "transportation_trend": project.reader.get_trend(),
            "open_questions": project.reader.model.open_questions[:3],
        }

        # 冷却矩阵：推荐使用的叙事模式
        recommended_patterns = project.cooldown.get_recommendations(3)

        # 高张力点（取前3）
        hot_tensions = sorted(tension, key=lambda t: t.intensity, reverse=True)[:3]

        return {
            "tension_points": [
                {
                    "description": t.description,
                    "intensity": t.intensity,
                    "type": t.type.value,
                    "suggestion": t.suggestion,
                    "involved": t.involved_characters
                }
                for t in hot_tensions
            ],
            "character_tendencies": [
                {
                    "character": t.character_id,
                    "action": t.action,
                    "strength": t.strength
                }
                for t in tendencies
            ],
            "reader_state": reader_state,
            "recommended_patterns": recommended_patterns,
            "cold_available_patterns": project.cooldown.get_cold_patterns()[:5],
        }

    def validate_generated_text(self, project_id: str, text: str) -> dict:
        """校验一段AI生成的文本——生成前门禁（G1-G5）"""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        # 执行生成前门禁
        results = project.gates.pre_generation_check(
            text,
            context={}  # 后续添加NLP提取
        )

        has_block = any(r.level == GateLevel.BLOCK for r in results)

        return {
            "can_display": not has_block,
            "gate_results": [r.to_dict() for r in results],
            "blocked": has_block
        }

    def submit_chapter(self, project_id: str, text: str) -> AuditReport:
        """提一章——全量审计 + 知识图谱提交 + 读者模型更新"""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        project.current_chapter += 1

        # 更新读者模型
        project.reader.update_from_text(text, project.current_chapter)
        transport_score = project.reader.evaluate_transportation(text)

        # 知识图谱提交通道
        snapshot = project.kg.commit_chapter_snapshot()

        # 推进ToM引擎
        project.tom.advance_chapter()

        # 冷却矩阵衰减
        project.cooldown.advance_time(1)

        # 全量审计（G6-G10）
        open_threads_data = []
        for n in project.kg.nodes.values():
            if n.type == NodeType.EVENT and n.properties.get("is_open_thread"):
                open_threads_data.append({
                    "id": n.id,
                    "description": n.name,
                })
        report = project.gates.post_chapter_audit(
            text,
            plot_state={
                "open_threads": open_threads_data,
            },
            genre_contract={"required_scenes": []},
            reader_context={
                "new_characters": 0,
                "new_locations": 0,
                "pov_switches": 0
            },
            matrix_state={"recent_patterns": project.cooldown.usage_history}
        )

        project.audit_reports.append(report)
        return report

    # ═══════════════════════════════════════
    # 心智网格数据
    # ═══════════════════════════════════════

    def get_mind_grid_data(self, project_id: str) -> dict:
        """生成心智网格可视化所需的数据

        心智网格是作者在分析模式下看到的角色信念状态图。
        """
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        snapshot = project.tom.to_snapshot()

        # 从知识图谱补充关系
        relationships = []
        for node_name in snapshot["characters"]:
            relations = project.kg.get_relations(node_name)
            for r in relations:
                src = project.kg.nodes.get(r.source)
                tgt = project.kg.nodes.get(r.target)
                if src and tgt:
                    relationships.append({
                        "source": src.name,
                        "target": tgt.name,
                        "type": r.type.value,
                        "active": r.is_active
                    })

        return {
            "characters": snapshot["characters"],
            "tension_points": snapshot["tension_points"],
            "relationships": relationships,
            "chapter": project.current_chapter,
            "transportation_trend": project.reader.get_trend(),
            "overall_audit_score": project.gates.get_average_score(),
            "hot_patterns": project.cooldown.get_hot_patterns(0.5),
        }

    def update_belief(self, project_id: str, character: str,
                      proposition: str, value: bool | str):
        """通过心智网格编辑角色的信念状态——作者可以直接操作"""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        char = project.tom.get_character(character)
        if not char:
            raise ValueError(f"角色 {character} 不存在")

        if proposition in char.world_beliefs:
            old = char.world_beliefs[proposition]
            old.value = value
            old.source = BeliefSource.DIRECT_WITNESS
            old.updated_at = project.current_chapter
            old.is_erroneous = False
        else:
            from tom_engine import Belief
            char.world_beliefs[proposition] = Belief(
                proposition=proposition,
                value=value,
                confidence=1.0,
                source=BeliefSource.DIRECT_WITNESS,
                updated_at=project.current_chapter
            )

        # 重新检测张力
        return project.tom.detect_tension()
