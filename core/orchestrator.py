"""
Æsirian Orchestrator — 核心引擎编排层

将四个引擎（ToM、知识图谱、一致性门禁、读者模型）串联为统一API。
对外提供：
- NSEF导入（从Æsir接收故事种子）
- 初始化长篇项目
- 生成前门禁检查
- 写作推进（场景生成建议）
- 章后全量审计

持久化：SQLite-backed ProjectStore 作为单一数据源。
运行时引擎（ToM/KG/Gates/Reader/Cooldown）在每次请求时从存储重建，
确保无状态（stateless）部署模式。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

# 添加核心模块到路径
sys.path.insert(0, os.path.dirname(__file__))

from consistency_gates import AuditReport, ConsistencyGateSystem, GateLevel

# EntityExtractor 保留兼容性导入
from entity_extractor import EntityExtractor as RegexEntityExtractor
from knowledge_graph import NodeType, TemporalKnowledgeGraph
from reader_model import EventCooldownMatrix, ReaderModelSimulator
from tom_engine import Belief, BeliefSource, Goal, TheoryOfMindEngine

# 新增：Transformers NER 提取器
try:
    from transformers_ner import EntityExtractor as TransformersEntityExtractor
    from transformers_ner import is_transformers_available

    _TRANSFORMERS_NER_AVAILABLE = is_transformers_available()
except ImportError:
    TransformersEntityExtractor = None
    _TRANSFORMERS_NER_AVAILABLE = False

# 桥接层
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bridge"))
from nsef import NarrativeStatePackage

# 观测性
from core.observability import (
    configure_observability,
    trace_chapter_generation,
    trace_context,
    trace_gate_audit,
    trace_kg_operation,
    trace_span,
    trace_tom_query,
)
from core.persistence.models import Foreshadowing

# 持久化层
from core.persistence.store import ProjectStore

# 初始化观测性
configure_observability()

# M1-6：KG NodeType（值为中文枚举标签）→ 数据库英文类型名映射，
# 与 _rebuild_world_elements 的 type_map 互逆，保证回写后重建可还原。
_NODE_TYPE_TO_DB = {
    NodeType.CHARACTER: "character",
    NodeType.EVENT: "event",
    NodeType.ITEM: "item",
    NodeType.LOCATION: "location",
    NodeType.RELATIONSHIP: "relationship",
    NodeType.THEME: "theme",
}


@dataclass
class ChapterInfo:
    """已提交章节的存储记录"""

    chapter_number: int
    title: str
    text: str


@dataclass
class ProjectState:
    """一个叙事项目的完整状态

    运行时对象——从持久化存储重建，不直接持久化。
    """

    project_id: str
    title: str = ""
    premise: str = ""
    current_chapter: int = 0
    total_chapters: int = 0
    genre: str = ""

    # 引擎实例
    tom: TheoryOfMindEngine = field(default_factory=TheoryOfMindEngine)
    kg: TemporalKnowledgeGraph = field(default_factory=TemporalKnowledgeGraph)
    gates: ConsistencyGateSystem = field(default_factory=ConsistencyGateSystem)
    reader: ReaderModelSimulator = field(default_factory=ReaderModelSimulator)
    cooldown: EventCooldownMatrix = field(default_factory=EventCooldownMatrix)

    # 已提交章节（运行时缓存，以DB为准）
    chapters: list[ChapterInfo] = field(default_factory=list)

    # 审计历史（运行时缓存，以DB为准）
    audit_reports: list[AuditReport] = field(default_factory=list)


class Orchestrator:
    """
    Æsirian 核心编排器

    串联四个引擎的工作流，提供"超级智能"所需的核心能力。
    所有项目状态持久化到 SQLite；运行时引擎按需重建。
    """

    def __init__(self, store: ProjectStore | None = None):
        self.store = store or ProjectStore()
        # 运行时缓存：project_id → ProjectState
        self._runtime_cache: dict[str, ProjectState] = {}

    # ═══════════════════════════════════════
    # 运行时引擎重建
    # ═══════════════════════════════════════

    def _load_project_state(self, project_id: str) -> ProjectState | None:
        """从持久化存储完整重建运行时 ProjectState"""
        project = self.store.get_project(project_id)
        if not project:
            return None

        state = ProjectState(
            project_id=project.id,
            title=project.title,
            premise=project.premise,
            genre=project.genre,
        )

        # 重建角色
        self._rebuild_characters(state)

        # 重建章节
        self._rebuild_chapters(state)

        # 重建世界元素
        self._rebuild_world_elements(state)

        # 重建伏笔
        self._rebuild_foreshadowings(state)

        # 设置引擎依赖
        state.gates.set_dependencies(kg=state.kg, tom=state.tom, reader=state.reader)

        # 重建冷却矩阵
        self._rebuild_cooldown(state)

        # 重建审计历史
        self._rebuild_audit_history(state)

        return state

    def _rebuild_characters(self, state: ProjectState):
        """从持久化角色记录重建 ToM 引擎

        注意：与 create_project_from_nsef 保持一致——ToM 的 character_id
        使用角色名（add_character(name, name)），保证 update_belief 等
        按名查询的路径在重启后同样可用。
        """
        characters = self.store.get_characters(state.project_id)
        for record in characters:
            char = state.tom.add_character(record.name, record.name)

            # 恢复信念
            beliefs = json.loads(record.beliefs_json) if record.beliefs_json else {}
            for prop, belief_data in beliefs.items():
                if isinstance(belief_data, dict):
                    char.world_beliefs[prop] = Belief(
                        proposition=prop,
                        value=belief_data.get("value"),
                        confidence=belief_data.get("confidence", 1.0),
                        source=BeliefSource(belief_data.get("source", "目击")),
                        is_erroneous=belief_data.get("is_erroneous", False),
                        updated_at=belief_data.get("updated_at", 0),
                    )
                else:
                    char.world_beliefs[prop] = Belief(
                        proposition=prop,
                        value=belief_data,
                        confidence=1.0,
                        source=BeliefSource.DIRECT_WITNESS,
                    )

            # 恢复目标
            goals = json.loads(record.goals_json) if record.goals_json else []
            for goal_data in goals:
                if isinstance(goal_data, dict):
                    char.active_goals.append(
                        Goal(
                            description=goal_data.get("description", ""),
                            priority=goal_data.get("priority", 1),
                            active=goal_data.get("active", True),
                            since_chapter=goal_data.get("since_chapter", 1),
                        )
                    )
                elif isinstance(goal_data, str):
                    char.active_goals.append(Goal(description=goal_data))

            # 恢复秘密
            secrets = json.loads(record.secrets_json) if record.secrets_json else []
            for secret_data in secrets:
                if isinstance(secret_data, str):
                    state.tom.register_secret(secret_data, known_to=[record.id], hidden_from=[])
                elif isinstance(secret_data, dict):
                    state.tom.register_secret(
                        secret_data.get("description", secret_data.get("secret", "")),
                        known_to=secret_data.get("known_to", [record.id]),
                        hidden_from=secret_data.get("hidden_from", []),
                    )

            # 注册到知识图谱
            traits = json.loads(record.traits_json) if record.traits_json else {}
            state.kg.add_node(
                record.name,
                NodeType.CHARACTER,
                properties={"role": record.role, "character_id": record.id, **traits},
            )

    def _rebuild_chapters(self, state: ProjectState):
        """从持久化章节记录重建章节列表"""
        chapters = self.store.get_chapters(state.project_id)
        state.chapters = []
        for ch in chapters:
            state.chapters.append(
                ChapterInfo(
                    chapter_number=ch.number,
                    title=ch.title,
                    text=ch.text,
                )
            )
            state.current_chapter = max(state.current_chapter, ch.number)
            state.kg.current_chapter = max(state.kg.current_chapter, ch.number)
            state.tom.current_chapter = max(state.tom.current_chapter, ch.number)
            state.reader.model.known_characters = list(
                set(
                    state.reader.model.known_characters
                    + [c.name for c in state.tom.get_all_characters()]
                )
            )

    def _rebuild_world_elements(self, state: ProjectState):
        """从持久化世界元素记录重建知识图谱"""
        elements = self.store.get_world_elements(state.project_id)
        for elem in elements:
            type_map = {
                "location": NodeType.LOCATION,
                "item": NodeType.ITEM,
                "event": NodeType.EVENT,
                "character": NodeType.CHARACTER,
                "relationship": NodeType.RELATIONSHIP,
                "theme": NodeType.THEME,
            }
            kg_type = type_map.get(elem.type, NodeType.ITEM)
            properties = json.loads(elem.properties_json) if elem.properties_json else {}
            state.kg.add_node(elem.name, kg_type, properties=properties)

    def _rebuild_foreshadowings(self, state: ProjectState):
        """从持久化伏笔记录重建知识图谱线索节点"""
        foreshadowings = self.store.get_all_foreshadowings(state.project_id)
        for fo in foreshadowings:
            if fo.status == "open":
                state.kg.add_node(
                    fo.description,
                    NodeType.EVENT,
                    properties={
                        "is_open_thread": True,
                        "foreshadowing_id": fo.id,
                        "expected_resolution": "reveal",
                    },
                )

    def _rebuild_cooldown(self, state: ProjectState):
        """从项目风格档案重建冷却矩阵"""
        fingerprint = self.store.get_latest_style_fingerprint(state.project_id)
        if fingerprint:
            tone_vector = (
                json.loads(fingerprint.tone_vector_json) if fingerprint.tone_vector_json else {}
            )
            for tone, weight in tone_vector.items():
                if weight > 0:
                    state.cooldown.record_usage(tone)

    def _rebuild_audit_history(self, state: ProjectState):
        """从持久化章节重建审计历史"""
        chapters = self.store.get_chapters(state.project_id)
        state.audit_reports = []
        for ch in chapters:
            if ch.audit_report_json:
                try:
                    report_data = json.loads(ch.audit_report_json)
                    report = AuditReport(
                        chapter=report_data.get("chapter", ch.number),
                        timestamp=report_data.get("timestamp", ""),
                        overall_score=report_data.get("overall_score", 100.0),
                    )
                    state.audit_reports.append(report)
                except (json.JSONDecodeError, KeyError):
                    pass

    def _get_or_load_project(self, project_id: str) -> ProjectState | None:
        """获取项目状态——优先使用缓存，否则从DB加载"""
        if project_id in self._runtime_cache:
            return self._runtime_cache[project_id]
        state = self._load_project_state(project_id)
        if state:
            self._runtime_cache[project_id] = state
        return state

    def _invalidate_cache(self, project_id: str):
        """使缓存失效——在突变操作后调用"""
        self._runtime_cache.pop(project_id, None)

    # ═══════════════════════════════════════
    # 项目生命周期
    # ═══════════════════════════════════════

    def create_project_from_nsef(self, nsef_path: str) -> ProjectState:
        """从NSEF文件（Æsir产出）创建叙事项目"""
        with open(nsef_path, encoding="utf-8") as f:
            package = NarrativeStatePackage.from_json(f.read())

        # 验证完整性
        issues = package.validate()
        if issues:
            raise ValueError(f"NSEF包不完整：{'；'.join(issues)}")

        # 创建持久化项目
        pid = package.package_id

        self.store.create_project(
            title=package.premise[:50],
            genre=package.genre_contract.genre.value if package.genre_contract else "",
            premise=package.premise,
            project_id=pid,
        )

        # 创建运行时状态
        project = ProjectState(
            project_id=pid,
            title=package.premise[:50],
            premise=package.premise,
            genre=package.genre_contract.genre.value if package.genre_contract else "",
        )

        # 注入依赖
        project.gates.set_dependencies(kg=project.kg, tom=project.tom, reader=project.reader)

        # 初始化ToM引擎——从角色种子引导
        for char_seed in package.characters:
            char = project.tom.add_character(char_seed.name, char_seed.name)
            for prop, belief_state in char_seed.beliefs.items():
                char.world_beliefs[prop] = Belief(
                    proposition=prop,
                    value=belief_state.value,
                    confidence=1.0,
                    source=BeliefSource.DIRECT_WITNESS,
                )
            for goal in char_seed.goals:
                char.active_goals.append(Goal(description=goal.goal, priority=goal.priority))

        # 初始化知识图谱——注册角色和线索
        for char_seed in package.characters:
            project.kg.add_node(
                char_seed.name, NodeType.CHARACTER, properties={"role": char_seed.role}
            )
        for thread in package.open_threads:
            project.kg.add_node(
                thread.description,
                NodeType.EVENT,
                properties={
                    "is_open_thread": True,
                    "expected_resolution": thread.expected_resolution_type,
                },
            )

        # 注册秘密
        for char_seed in package.characters:
            for secret in char_seed.secrets:
                project.tom.register_secret(
                    secret.secret, known_to=secret.known_to, hidden_from=secret.hidden_from
                )

        # 设置冷却矩阵
        for pattern, cooldown_val in package.event_cooldown.items():
            project.cooldown.matrix[pattern] = cooldown_val

        # 持久化角色
        for char_seed in package.characters:
            beliefs_data = {}
            for prop, bs in char_seed.beliefs.items():
                beliefs_data[prop] = {
                    "value": bs.value,
                    "confidence": bs.confidence,
                    "source": bs.source,
                    "is_erroneous": bs.is_erroneous,
                    "updated_at": bs.updated_at_chapter,
                }
            goals_data = [{"description": g.goal, "priority": g.priority} for g in char_seed.goals]
            secrets_data = [
                {"secret": s.secret, "known_to": s.known_to, "hidden_from": s.hidden_from}
                for s in char_seed.secrets
            ]
            traits_data = dict(char_seed.personality_traits)

            self.store.add_character(
                project_id=pid,
                name=char_seed.name,
                role=char_seed.role,
                traits=traits_data,
                beliefs=beliefs_data,
                goals=goals_data,
                secrets=secrets_data,
            )

        # 持久化世界元素（从知识图谱节点）
        for node in project.kg.nodes.values():
            if node.type == NodeType.CHARACTER:
                continue
            self.store.add_world_element(
                project_id=pid,
                name=node.name,
                element_type=node.type.value,
                description=node.properties.get("description", ""),
                properties=node.properties,
            )

        # 持久化伏笔
        for thread in package.open_threads:
            self.store.add_foreshadowing(
                project_id=pid,
                chapter_id="",
                description=thread.description,
            )

        # 持久化风格指纹
        if package.style_fingerprint:
            self.store.add_style_fingerprint(
                project_id=pid,
                tone_vector=package.style_fingerprint.tone_distribution,
                pace_vector={},
                dialogue_ratio=package.style_fingerprint.dialogue_ratio,
            )

        # 缓存运行时状态
        self._runtime_cache[pid] = project
        return project

    def get_project(self, project_id: str) -> ProjectState | None:
        return self._get_or_load_project(project_id)

    # ═══════════════════════════════════════
    # 写作推演
    # ═══════════════════════════════════════

    @trace_span("orchestrator.generate_chapter", attributes={"operation": "generate_chapter"})
    def generate_chapter(self, project_id: str, prompt: str, word_target: int = 300) -> dict:
        """LLM 生成章节草稿——输入灵感，输出200-500字正文

        Returns: {"text": str, "llm_used": bool}
        LLM 不可用时返回占位失败信号，由 API 层转 400。
        """
        project = self._get_or_load_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        from core.pydantic_ai_engine import get_pydantic_ai_engine

        engine = get_pydantic_ai_engine()

        context = {
            "characters": [c.name for c in project.tom.get_all_characters()],
            "tension_points": [],  # 由 constraints 填充（见下）
            "current_chapter": project.current_chapter + 1,
            "project_id": project_id,
        }
        # 张力点（若项目已有状态）
        try:
            constraints = self.generate_scene_constraints(project_id)
            context["tension_points"] = constraints.get("tension_points", [])
        except Exception:
            pass

        with trace_chapter_generation(project_id, project.current_chapter + 1, prompt) as span:
            text = engine.generate_chapter(prompt, context, word_target)
            if span:
                span.set_attribute("generated_chars", len(text))
                span.set_attribute("llm_used", bool(text))
            return {"text": text, "llm_used": bool(text)}

    @trace_span(
        "orchestrator.generate_scene_constraints",
        attributes={"operation": "generate_scene_constraints"},
    )
    def generate_scene_constraints(self, project_id: str) -> dict:
        """生成场景的"写作约束"——给LLM的结构化输入"""
        project = self._get_or_load_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        with trace_tom_query(project_id, "detect_tension") as span:
            tension = project.tom.detect_tension()
            if span:
                span.set_attribute("tension_count", len(tension))

        with trace_tom_query(project_id, "infer_action_tendencies") as span:
            tendencies = project.tom.infer_action_tendencies()
            if span:
                span.set_attribute("tendency_count", len(tendencies))

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
                    "involved": t.involved_characters,
                }
                for t in hot_tensions
            ],
            "character_tendencies": [
                {"character": t.character_id, "action": t.action, "strength": t.strength}
                for t in tendencies
            ],
            "reader_state": reader_state,
            "recommended_patterns": recommended_patterns,
            "cold_available_patterns": project.cooldown.get_cold_patterns()[:5],
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
                    "involved": t.involved_characters,
                }
                for t in hot_tensions
            ],
            "character_tendencies": [
                {"character": t.character_id, "action": t.action, "strength": t.strength}
                for t in tendencies
            ],
            "reader_state": reader_state,
            "recommended_patterns": recommended_patterns,
            "cold_available_patterns": project.cooldown.get_cold_patterns()[:5],
        }

    def validate_generated_text(self, project_id: str, text: str) -> dict:
        """校验一段AI生成的文本——生成前门禁（G1-G5）"""
        project = self._get_or_load_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        # 执行生成前门禁
        results = project.gates.pre_generation_check(text, context={})

        has_block = any(r.level == GateLevel.BLOCK for r in results)

        return {
            "can_display": not has_block,
            "gate_results": [r.to_dict() for r in results],
            "blocked": has_block,
        }

    @trace_span("orchestrator.audit_draft", attributes={"operation": "audit_draft"})
    def audit_draft(self, project_id: str, text: str) -> dict:
        """P0-2 (2026-09-07): analysis-only 章节审计（dry_run）。

        修复历史副作用：`/audit` 无 BLOCK 时静默调用 submit_chapter 会落库、
        推进章节号、触发 ToM/KG 更新——用户"试算一段建议文本"可能不知不觉写入章节。

        本方法只审计、不落库：G1-G5 预检 + G6-G10 章后审计（在**临时** gates 实例上
        跑，不污染 project.gates._current_chapter/_audit_history）+ 跨章一致性预检。
        project 状态与 DB 均不变。

        Returns:
          {overall_score, gate_results, audit_results, cross_chapter, dry_run: True,
           submitted: False}
        """
        project = self._get_or_load_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        # ── G1-G5 预检（只读） ──
        from core.entity_extractor import EntityExtractor

        context = EntityExtractor.to_gate_context(text)
        ctx = {
            "facts": context["facts"],
            "char_actions": context["char_actions"],
            "identity_changes": context["identity_changes"],
            "events": context["events"],
            "movements": context["movements"],
        }
        gate_results = project.gates.pre_generation_check(text, context=ctx)
        has_block = any(r.level == GateLevel.BLOCK for r in gate_results)

        # ── G6-G10 章后审计：在临时 gates 上跑，避免污染真实实例 ──
        # 真实 submit 的 post_chapter_audit 会推进 self._current_chapter 并 append
        # audit_history；dry_run 必须零副作用。临时实例注入与 project 相同的
        # kg/tom/reader 依赖（审计只读这些依赖），初始章节号对齐 project 当前章节。
        open_threads_data = [
            {"id": n.id, "description": n.name}
            for n in project.kg.nodes.values()
            if n.type == NodeType.EVENT and n.properties.get("is_open_thread")
        ]
        report_results: list[dict] = []
        overall_score = 100.0
        if not has_block:
            temp_gates = ConsistencyGateSystem()
            temp_gates.set_dependencies(
                kg=project.kg, tom=project.tom, reader=project.reader
            )
            temp_gates._current_chapter = max(project.current_chapter, 0)
            # P0-3: 与 submit_chapter 一致，用真实 EntityExtractor 上下文
            _gate_ctx = self._gate_entity_context(text)
            report = temp_gates.post_chapter_audit(
                text,
                plot_state={"open_threads": open_threads_data, **_gate_ctx.get("plot_extra", {})},
                genre_contract=_gate_ctx.get("genre_contract"),
                reader_context=_gate_ctx.get("reader_context"),
                matrix_state={"recent_patterns": project.cooldown.usage_history},
            )
            report_results = [r.to_dict() for r in report.results]
            overall_score = report.overall_score
        else:
            overall_score = max(
                0, 100 - sum(20 if r.level == GateLevel.BLOCK else 10 for r in gate_results)
            )

        # ── 跨章一致性预检（只读，读历史章，不写库） ──
        cross_chapter = self.check_cross_chapter_consistency(project_id, text)

        return {
            "overall_score": overall_score,
            "gate_results": [r.to_dict() for r in gate_results],
            "audit_results": report_results,
            "cross_chapter": cross_chapter,
            "dry_run": True,
            "submitted": False,
        }

    @trace_span("orchestrator.submit_chapter", attributes={"operation": "submit_chapter"})
    def submit_chapter(self, project_id: str, text: str) -> AuditReport:
        """提一章——全量审计 + 知识图谱提交 + 读者模型更新"""
        project = self._get_or_load_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        project.current_chapter += 1
        chapter_num = project.current_chapter

        # 提取章节标题：取第一行非空内容
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        chapter_title = first_line[:60] if first_line else f"第{chapter_num}章"

        project.chapters.append(
            ChapterInfo(
                chapter_number=chapter_num,
                title=chapter_title,
                text=text,
            )
        )

        # 更新读者模型
        with trace_context(
            "reader_model.update", {"project_id": project_id, "chapter": chapter_num}
        ):
            project.reader.update_from_text(text, project.current_chapter)
        with trace_context(
            "reader_model.evaluate", {"project_id": project_id, "chapter": chapter_num}
        ):
            project.reader.evaluate_transportation(text)

        # 知识图谱提交通道
        with trace_kg_operation(project_id, "commit_chapter_snapshot") as span:
            project.kg.commit_chapter_snapshot()
            if span:
                span.set_attribute("snapshot_chapter", chapter_num)

        # 推进ToM引擎
        with trace_tom_query(project_id, "advance_chapter"):
            project.tom.advance_chapter()

        # 冷却矩阵衰减
        project.cooldown.advance_time(1)

        # 全量审计（G6-G10）
        open_threads_data = [
            {
                "id": n.id,
                "description": n.name,
            }
            for n in project.kg.nodes.values()
            if n.type == NodeType.EVENT and n.properties.get("is_open_thread")
        ]

        gate_ids = ["G6", "G7", "G8", "G9", "G10"]
        # P0-3: 用真实 EntityExtractor 上下文替换硬编码空 reader_context/plot_state，
        # 让 G8 认知负荷（新角色/地点/POV 切换）与 G6 因果链拿到真实入参。
        # 此前写死 reader_context={"new_characters":0,...} 使 G8 永远 0 分通过，
        # genre_contract={"required_scenes":[]} 使 G7 永远空契约跳过。
        _gate_entity_ctx = self._gate_entity_context(text)
        with trace_gate_audit(project_id, chapter_num, gate_ids) as span:
            report = project.gates.post_chapter_audit(
                text,
                plot_state={
                    "open_threads": open_threads_data,
                    **_gate_entity_ctx.get("plot_extra", {}),
                },
                genre_contract=_gate_entity_ctx.get("genre_contract"),
                reader_context=_gate_entity_ctx.get("reader_context"),
                matrix_state={"recent_patterns": project.cooldown.usage_history},
            )
            if span:
                span.set_attribute("overall_score", report.overall_score)
                span.set_attribute("gate_results", len(report.results))

        project.audit_reports.append(report)

        # ── #12 跨章一致性检测 ──
        with trace_context(
            "cross_chapter_consistency", {"project_id": project_id, "chapter": chapter_num}
        ):
            cross_chapter = self.check_cross_chapter_consistency(project_id, text)

        # 持久化章节
        audit_report_data = report.to_dict()
        audit_report_data["cross_chapter"] = cross_chapter
        # P2-8: 落盘本章实体摘要——供后续跨章一致性增量比对（消除 O(n²) 全量重提取）
        audit_report_data["_entity_summary"] = self._chapter_entity_summary(text)
        self.store.add_chapter(
            project_id=project_id,
            number=chapter_num,
            text=text,
            audit_report=audit_report_data,
        )

        # ── M1-6 数据洞补齐：章节提交后回写运行时 ToM/KG 状态 ──
        # add_chapter 只落盘章节正文；角色的 world_beliefs/active_goals 演化
        # 与 KG 中新增的世界观节点此前仅存在于 _runtime_cache，重建 orchestrator
        # 后即丢失（演示项目《洛阳星港》beliefs_json/goals_json 全空、world_elements=0）。
        # 此处将二者同步到 DB，保证 reload / 进程重启后角色信念与世界观仍可还原。
        self._persist_character_state(project)
        self._persist_world_elements(project)

        # 使缓存失效（章节提交后状态已变）
        self._invalidate_cache(project_id)

        return report

    # ═══════════════════════════════════════
    # M1-6 数据洞：运行时 ToM/KG 状态持久化
    # ═══════════════════════════════════════

    def _persist_character_state(self, project: ProjectState) -> int:
        """将运行时 ToM 角色信念/目标全量回写 DB。

        角色在 characters 表中以角色名为 id（add_character(name, name) 约定），
        重启后由 _rebuild_characters 从 beliefs_json/goals_json 还原 Belief/Goal。
        返回回写的角色数。
        """
        records = {r.name: r for r in self.store.get_characters(project.project_id)}
        written = 0
        for char in project.tom.get_all_characters():
            record = records.get(char.name) or records.get(getattr(char, "character_id", ""))
            if record is None:
                continue
            beliefs_data = {}
            for prop, belief in char.world_beliefs.items():
                beliefs_data[prop] = {
                    "value": belief.value,
                    "confidence": belief.confidence,
                    "source": belief.source.value
                    if hasattr(belief.source, "value")
                    else str(belief.source),
                    "is_erroneous": belief.is_erroneous,
                    "updated_at": belief.updated_at,
                }
            goals_data = [
                {
                    "description": g.description,
                    "priority": g.priority,
                    "active": g.active,
                    "since_chapter": g.since_chapter,
                }
                for g in char.active_goals
            ]
            self.store.update_character_beliefs(record.id, beliefs_data)
            if goals_data:
                self.store.update_character_goals(record.id, goals_data)
            written += 1
        return written

    def _persist_world_elements(self, project: ProjectState) -> int:
        """将运行时 KG 非角色节点持久化为世界观元素。

        CHARACTER 节点由 characters 表负责（避免双写）；open_thread 事件由
        foreshadowings 表负责，二者都不写入 world_elements。
        按 (name) 幂等 upsert，重复 submit 不会产生重复元素。
        返回本次新建的元素数。
        """
        created = 0
        for node in project.kg.nodes.values():
            if node.type == NodeType.CHARACTER:
                continue
            if node.properties.get("is_open_thread"):
                continue
            db_type = _NODE_TYPE_TO_DB.get(node.type, "item")
            description = node.properties.get("description", node.name)
            _, is_new = self.store.upsert_world_element(
                project.project_id,
                node.name,
                db_type,
                description=str(description),
                properties=dict(node.properties),
            )
            if is_new:
                created += 1
        return created

    def persist_runtime_state(self, project_id: str) -> dict:
        """将当前运行时 ToM/KG 状态立即持久化到 DB（M1-6 对外入口）。

        submit_chapter 已自动调用；此入口供外部在数据修复/种子回填后手动落盘。
        返回 {"characters": n, "world_elements_created": m}。
        """
        project = self._get_or_load_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")
        n_chars = self._persist_character_state(project)
        n_world = self._persist_world_elements(project)
        return {"characters": n_chars, "world_elements_created": n_world}

    def _gate_entity_context(self, text: str) -> dict:
        """P0-3: 构建 G6-G10 审计的真实入参上下文（替换硬编码空值）。

        - reader_context: G8 认知负荷需要 new_characters/new_locations/pov_switches
          （EntityExtractor.to_gate_context 已产出，此前被写死为 0 → G8 永远空转）
        - genre_contract: G7 叙事节奏需要 required_scenes；单章无完整类型契约，
          保留空契约并标注（避免把"无数据"误判为"违规"）
        - plot_extra: G6 因果链需要 facts/events 供伏笔/悬念回收判断
        """
        from core.entity_extractor import EntityExtractor

        ctx = EntityExtractor.to_gate_context(text)
        reader_context = {
            "new_characters": ctx.get("new_characters", 0) or 0,
            "new_locations": ctx.get("new_locations", 0) or 0,
            "pov_switches": ctx.get("pov_switches", 0) or 0,
            "ai_marker_count": ctx.get("ai_marker_count", 0) or 0,
            "hedge_word_count": ctx.get("hedge_word_count", 0) or 0,
            "transition_repeats": ctx.get("transition_repeats", 0) or 0,
        }
        plot_extra = {
            "facts": ctx.get("facts", []),
            "events": ctx.get("events", []),
            "char_actions": ctx.get("char_actions", []),
            "identity_changes": ctx.get("identity_changes", []),
            "movements": ctx.get("movements", []),
        }
        return {
            "reader_context": reader_context,
            "genre_contract": {"required_scenes": [], "_note": "单章审计无完整类型契约"},
            "plot_extra": plot_extra,
        }

    def check_cross_chapter_consistency(self, project_id: str, current_text: str) -> list[dict]:
        """#12: 当前章与历史章的一致性检测

        检测四类矛盾：
        1. 数字事实矛盾——"陈默今年30岁" vs 历史章 "陈默今年40岁"
        2. 信念冲突——当前章断言与角色已有信念相反（无转变解释）
        3. 已亡角色复活/消失角色复现
        4. CSN 数值矛盾——中文数词归一化后的跨章数值比对（P0-3 新增；
           覆盖正则 EntityExtractor 抓不到的"修了十一年→二十一年"）

        Returns: [{type, severity, detail, current_chapter, conflict_chapter}]
        """
        conflicts: list[dict] = []
        chapters = self.store.get_chapters(project_id)
        history = [ch for ch in chapters if ch.text != current_text]
        if not history:
            return conflicts

        current = self._chapter_entity_summary(current_text)
        chapter_num = len(chapters)

        # 1) 数字事实矛盾（subject+predicate 相同、值不同）
        # P2-8: 历史章实体视图优先读落盘摘要（_entity_summary），无则回退全量提取
        current_facts = {(f["subject"], f["predicate"]): f["object"] for f in current["facts"]}
        if current_facts:
            for ch in history:
                past = self._history_entity_view(ch)
                past_facts = {(f["subject"], f["predicate"]): f["object"] for f in past["facts"]}
                for key, cur_val in current_facts.items():
                    if key in past_facts and past_facts[key] != cur_val:
                        conflicts.append(
                            {
                                "type": "fact_contradiction",
                                "severity": "BLOCK",
                                "detail": f"{key[0]}的{key[1]}：第{ch.number}章为 {past_facts[key]}，"
                                f"第{chapter_num}章变为 {cur_val}，且无转变说明",
                                "current_chapter": chapter_num,
                                "conflict_chapter": ch.number,
                            }
                        )

        # 2) 身份变化无解释（当前章 identity_changes 缺解释且角色曾出场）
        for change in current["identity_changes"]:
            if not change.get("has_explanation"):
                char_seen_before = any(
                    change["character"] in self._history_entity_view(ch)["characters"]
                    for ch in history
                )
                if char_seen_before:
                    conflicts.append(
                        {
                            "type": "identity_shift_unexplained",
                            "severity": "WARN",
                            "detail": f"{change['character']}的{change['property']}变为「{change['new_value']}」，"
                            f"历史章节曾出场但本次变化无因果说明",
                            "current_chapter": chapter_num,
                            "conflict_chapter": None,
                        }
                    )

        # 3) 信念冲突——当前章文本断言 X，但某角色 ToM 信念为非 X
        #    （启发式：检查高频角色名的信念命题是否被直接否定）
        project = self._get_or_load_project(project_id)
        if project:
            for char in project.tom.get_all_characters():
                for prop, belief in list(char.world_beliefs.items())[:10]:
                    if belief.value is True and current_text.count("不" + prop[:4]):
                        conflicts.append(
                            {
                                "type": "belief_contradiction",
                                "severity": "WARN",
                                "detail": f"第{chapter_num}章文本疑似否定「{prop}」，"
                                f"与 {char.name} 的既有信念冲突",
                                "current_chapter": chapter_num,
                                "conflict_chapter": belief.updated_at or None,
                            }
                        )

        # 4) CSN 数值矛盾（P0-3）：中文数词归一化跨章比对——正则 EntityExtractor
        #    抓不到"修了十一年→二十一年"，此扫描器补齐时间/年龄/楼层类数值事实。
        from core.csn_consistency import find_cross_chapter_numeric_conflicts

        history_texts = [(ch.number, ch.text) for ch in history]
        csn_conflicts = find_cross_chapter_numeric_conflicts(current_text, history_texts)
        conflicts.extend(csn_conflicts)

        return conflicts

    def _extract_entities(self, text: str):
        """统一实体提取入口：优先 Transformers NER，回退正则"""
        if _TRANSFORMERS_NER_AVAILABLE and TransformersEntityExtractor:
            return TransformersEntityExtractor().extract(text)
        return RegexEntityExtractor.extract(text)

    def _chapter_entity_summary(self, text: str) -> dict:
        """P2-8: 抽取单章实体/事实的紧凑可序列化摘要（供跨章一致性增量比对）。

        历史问题：check_cross_chapter_consistency 对每个历史章每次提交都全量
        `_extract_entities(ch.text)`——O(章节数) 次全文本正则提取/提交 → 全书累计
        O(n²)。修复：提交时把本章摘要落盘（audit_report_json["_entity_summary"]），
        后续跨章检查只读已落盘摘要；仅对无摘要的历史章（老数据）回退全量提取。
        """
        result = self._extract_entities(text)
        return {
            "characters": list(result.characters),
            "facts": [
                {"subject": f.subject, "predicate": f.predicate, "object": f.obj}
                for f in result.facts
            ],
            "identity_changes": list(result.identity_changes),
            "event_names": [e.name for e in result.events if hasattr(e, "name")],
        }

    def _chapter_summary_of(self, chapter) -> dict | None:
        """从章节记录读取已落盘实体摘要（无则 None，调用方回退全量提取）。"""
        try:
            if not getattr(chapter, "audit_report_json", ""):
                return None
            payload = json.loads(chapter.audit_report_json)
            summary = payload.get("_entity_summary")
            return summary if isinstance(summary, dict) else None
        except (json.JSONDecodeError, AttributeError):
            return None

    def _history_entity_view(self, chapter) -> dict:
        """获取历史章实体视图——优先落盘摘要，缺失回退全量提取。"""
        summary = self._chapter_summary_of(chapter)
        if summary is not None:
            return summary
        return self._chapter_entity_summary(chapter.text)

    # ═══════════════════════════════════════
    # 假设推演（#15）
    # ═══════════════════════════════════════

    def simulate_hypothesis(
        self, project_id: str, hypothesis: str, belief_changes: list[dict], branch_count: int = 3
    ) -> dict:
        """#15: "如果…会怎样"推演

        流程：克隆项目状态 → 应用信念变更 → 检测新张力 →
        LLM 生成 N 条情节分支 → 返回预览（不落盘、不改主线）

        Parameters
        ----------
        hypothesis : str
            假设描述，如 "陈默发现曹渊在撒谎"
        belief_changes : list[dict]
            [{character, proposition, value}] —— 推演用的信念变更
        branch_count : int
            分支数（默认3）

        Returns
        -------
        dict: {hypothesis, tensions, branches, applied_beliefs}
        """

        @trace_span(
            "orchestrator.simulate_hypothesis", attributes={"operation": "simulate_hypothesis"}
        )
        def _run_simulation():
            project = self._get_or_load_project(project_id)
            if not project:
                raise ValueError(f"项目 {project_id} 不存在")

            # 深克隆 ToM（快照式推演，不污染主线）
            tom_snapshot = project.tom.to_snapshot()
            sim_tom = TheoryOfMindEngine()
            for cid, cdata in tom_snapshot["characters"].items():
                sim_char = sim_tom.add_character(cdata.get("name", cid), cid)
                from tom_engine import Belief as _B
                from tom_engine import BeliefSource as _S
                from tom_engine import Goal as _G

                for prop, b in (cdata.get("world_beliefs") or {}).items():
                    sim_char.world_beliefs[prop] = _B(
                        proposition=prop,
                        value=b.get("value"),
                        confidence=b.get("confidence", 1.0),
                        source=_S(b.get("source", "目击")),
                    )
                for g in cdata.get("active_goals") or []:
                    sim_char.active_goals.append(
                        _G(description=g if isinstance(g, str) else g.get("description", ""))
                    )

            # 应用假设信念变更
            applied = []
            for change in belief_changes[:8]:
                char = sim_tom.get_character(change.get("character", ""))
                if not char:
                    continue
                prop = change.get("proposition", "")
                if not prop:
                    continue
                from tom_engine import Belief as _B
                from tom_engine import BeliefSource as _S

                char.world_beliefs[prop] = _B(
                    proposition=prop,
                    value=change.get("value", True),
                    confidence=1.0,
                    source=_S.DIRECT_WITNESS,
                )
                applied.append(change)

            # 新张力点
            with trace_tom_query(project_id, "detect_tension_simulation") as span:
                tensions = sim_tom.detect_tension()
                if span:
                    span.set_attribute("tension_count", len(tensions))
            tension_data = [
                {
                    "description": t.description,
                    "intensity": t.intensity,
                    "type": t.type.value,
                    "suggestion": t.suggestion,
                }
                for t in sorted(tensions, key=lambda x: x.intensity, reverse=True)[:5]
            ]

            # LLM 生成分支（使用 Pydantic AI）
            from core.pydantic_ai_engine import get_pydantic_ai_engine

            engine = get_pydantic_ai_engine()
            branches = []
            if engine.available():
                sim_result = engine.simulate_hypothesis(
                    hypothesis,
                    belief_changes,
                    {
                        "project_id": project_id,
                        "tom_snapshot": tom_snapshot,
                    },
                    branch_count,
                )
                branches = sim_result.get("branches", [])

            # 规则降级分支（张力驱动）
            if not branches:
                for i, t in enumerate(tension_data[:branch_count], 1):
                    branches.append(
                        {
                            "title": f"张力路线{i}",
                            "summary": t["suggestion"] or t["description"][:60],
                            "key_event": t["description"][:30],
                        }
                    )
                if not branches:
                    branches = [
                        {
                            "title": "平稳推进",
                            "summary": "信念变更暂未产生新张力，主线可按原节奏推进",
                            "key_event": hypothesis[:30],
                        }
                    ]

            llm_used = False
            try:
                from core.pydantic_ai_engine import get_llm_engine

                llm_used = bool(get_llm_engine().available())
            except Exception:
                llm_used = engine.available() if "engine" in dir() else False
            return {
                "hypothesis": hypothesis,
                "tensions": tension_data,
                "branches": branches[:branch_count],
                "applied_beliefs": applied,
                "llm_used": llm_used,
            }

        return _run_simulation()

    # ═══════════════════════════════════════
    # 碎片发散（#16）
    # ═══════════════════════════════════════

    @trace_span("orchestrator.diverge_fragments", attributes={"operation": "diverge_fragments"})
    def diverge_fragments(self, fragments: list[str], count: int = 5) -> dict:
        """#16: 3-5 个碎片画面 → N 条世界线预览

        每条世界线随机组合 类型×结构×冲突，LLM 织入碎片生成
        5 拍大纲 + 开头段。LLM 不可用时降级为模板拼接。
        """
        fragments = [f.strip() for f in fragments if f.strip()][:8]
        if len(fragments) < 2:
            raise ValueError("至少需要 2 个碎片画面")

        from core.pydantic_ai_engine import get_llm_engine

        llm = get_llm_engine()

        worldlines: list[dict] = []
        llm_wl: list[dict] = []

        if llm.available():
            import json as _json
            import re as _re

            prompt = (
                f"碎片画面：{fragments}\n"
                f"请基于这些碎片，构思一条完整的小说世界线。"
                f"输出 JSON 对象：{{"
                f'"genre": "类型", '
                f'"structure": "叙事结构", '
                f'"conflict_core": "核心冲突(≤20字)", '
                f'"beats": ["节拍1", "节拍2", "节拍3", "节拍4", "节拍5"], '
                f'"opening": "开头段(80-120字，必须是正文的口吻)"'
                f"}}。碎片必须自然融入。只输出 JSON。"
            )
            for i in range(count):
                raw = llm.generate_chapter(prompt, {"characters": []}, word_target=500)
                wl = None
                if raw:
                    m = _re.search(r"\{.*\}", raw, _re.DOTALL)
                    if m:
                        try:
                            wl = _json.loads(m.group(0))
                        except Exception:
                            wl = None
                if wl and wl.get("beats"):
                    wl["id"] = f"wl_{i + 1}"
                    llm_wl.append(wl)

        # 使用 Pydantic AI 进行碎片发散（如果 LLM 不可用或结果不足，回退到模板）
        from core.pydantic_ai_engine import get_pydantic_ai_engine

        engine = get_pydantic_ai_engine()
        if engine.available() and len(llm_wl) < count:
            try:
                div_result = engine.diverge_fragments(fragments, count - len(llm_wl))
                llm_wl.extend(wl for wl in div_result.get("worldlines", []) if wl.get("beats"))
            except Exception:
                pass

        # LLM 不足 count 条 → 规则模板补齐（保证始终返回 count 条）
        template_defs = [
            ("悬疑推理", "三幕结构", "身份冲突"),
            ("科幻末世", "英雄之旅", "生存冲突"),
            ("都市逆袭", "故事圈", "价值观冲突"),
            ("仙侠玄幻", "五幕辩证", "关系冲突"),
            ("言情", "三幕结构", "认知冲突"),
        ]
        i = 0
        while len(worldlines) < count:
            # 先消费 LLM 结果，再模板补位
            if i < len(llm_wl):
                worldlines.append(llm_wl[i])
            else:
                g, s, c = template_defs[len(worldlines) % len(template_defs)]
                beats = [
                    f"开场：{fragments[0][:20]}",
                    f"激化：围绕{c[:4]}，{fragments[1 % len(fragments)][:20]}浮现隐情",
                    f"转折：第三个碎片改写一切——{fragments[2 % len(fragments)][:20]}",
                    f"危机：{c[:4]}到达顶点，抉择时刻",
                    "收束：碎片间的因果链闭合，留一个余韵钩子",
                ]
                worldlines.append(
                    {
                        "id": f"wl_{len(worldlines) + 1}",
                        "genre": g,
                        "structure": s,
                        "conflict_core": c,
                        "beats": beats,
                        "opening": f"{fragments[0]}。这个画面在他脑海里挥之不去，而他还不知道，一切要从这里开始。",
                    }
                )
            i += 1
        return {
            "worldlines": worldlines[:count],
            "llm_used": bool(engine.available()),
            "fragment_count": len(fragments),
        }

    # ═══════════════════════════════════════
    # 心智网格数据
    # ═══════════════════════════════════════

    def get_mind_grid_data(self, project_id: str) -> dict:
        """生成心智网格可视化所需的数据"""
        project = self._get_or_load_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        snapshot = project.tom.to_snapshot()

        # 转换 characters 为 list 格式（兼容前端）
        chars_list = []
        for cid, cdata in snapshot["characters"].items():
            chars_list.append(
                {
                    "id": cid,
                    "name": cdata.get("name", cid),
                    "world_beliefs": cdata.get("world_beliefs", {}),
                    "about_others": cdata.get("about_others", {}),
                    "active_goals": cdata.get("active_goals", []),
                    "secret_count": cdata.get("secret_count", 0),
                }
            )

        # 从知识图谱补充关系
        relationships = []
        for node_name in snapshot["characters"]:
            relations = project.kg.get_relations(node_name)
            for r in relations:
                src = project.kg.nodes.get(r.source)
                tgt = project.kg.nodes.get(r.target)
                if src and tgt:
                    relationships.append(
                        {
                            "source": src.name,
                            "target": tgt.name,
                            "type": r.type.value,
                            "active": r.is_active,
                        }
                    )

        return {
            "characters": chars_list,
            "tension_points": snapshot["tension_points"],
            "relationships": relationships,
            "chapter": project.current_chapter,
            "transportation_trend": project.reader.get_trend(),
            "overall_audit_score": project.gates.get_average_score(),
            "hot_patterns": project.cooldown.get_hot_patterns(0.5),
        }

    def update_belief(self, project_id: str, character: str, proposition: str, value: bool | str):
        """通过心智网格编辑角色的信念状态——作者可以直接操作"""
        project = self._get_or_load_project(project_id)
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
                updated_at=project.current_chapter,
            )

        # 持久化信念变更
        char_record = None
        for record in self.store.get_characters(project_id):
            if record.id == character or record.name == character:
                char_record = record
                break

        if char_record:
            beliefs_data = {}
            for prop, belief in char.world_beliefs.items():
                beliefs_data[prop] = {
                    "value": belief.value,
                    "confidence": belief.confidence,
                    "source": belief.source.value,
                    "is_erroneous": belief.is_erroneous,
                    "updated_at": belief.updated_at,
                }
            self.store.update_character_beliefs(char_record.id, beliefs_data)

        # 重新检测张力
        return project.tom.detect_tension()

    # ═══════════════════════════════════════
    # 伏笔管理
    # ═══════════════════════════════════════

    def add_foreshadowing(self, project_id: str, description: str, chapter_id: str = "") -> str:
        """添加一个新的伏笔"""
        fo = self.store.add_foreshadowing(project_id, chapter_id, description)
        self._invalidate_cache(project_id)
        return fo.id

    def resolve_foreshadowing(
        self, project_id: str, foreshadowing_id: str, resolved_chapter: str
    ) -> Foreshadowing | None:
        """回收一个伏笔"""
        result = self.store.resolve_foreshadowing(foreshadowing_id, resolved_chapter)
        self._invalidate_cache(project_id)
        return result

    def get_open_foreshadowings(self, project_id: str) -> list[dict]:
        """获取所有未回收的伏笔"""
        foreshadowings = self.store.get_open_foreshadowings(project_id)
        return [
            {
                "id": fo.id,
                "description": fo.description,
                "status": fo.status,
                "created_at": fo.created_at.isoformat() if fo.created_at else None,
            }
            for fo in foreshadowings
        ]

    # ═══════════════════════════════════════
    # 项目管理（新增）
    # ═══════════════════════════════════════

    def list_projects(self) -> list[dict]:
        """列出所有项目"""
        projects = self.store.list_projects()
        return [
            {
                "id": p.id,
                "title": p.title,
                "genre": p.genre,
                "premise": p.premise[:100],
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in projects
        ]

    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        result = self.store.delete_project(project_id)
        self._invalidate_cache(project_id)
        return result

    def add_character(
        self,
        project_id: str,
        name: str,
        role: str,
        traits: dict | None = None,
        beliefs: dict | None = None,
        goals: list | None = None,
        secrets: list | None = None,
    ) -> str:
        """添加角色到项目"""
        character = self.store.add_character(
            project_id=project_id,
            name=name,
            role=role,
            traits=traits,
            beliefs=beliefs,
            goals=goals,
            secrets=secrets,
        )
        self._invalidate_cache(project_id)
        return character.id

    def get_characters(self, project_id: str) -> list[dict]:
        """获取项目所有角色"""
        characters = self.store.get_characters(project_id)
        return [
            {
                "id": c.id,
                "name": c.name,
                "role": c.role,
                "traits": json.loads(c.traits_json) if c.traits_json else {},
                "beliefs": json.loads(c.beliefs_json) if c.beliefs_json else {},
                "goals": json.loads(c.goals_json) if c.goals_json else [],
                "secrets": json.loads(c.secrets_json) if c.secrets_json else [],
            }
            for c in characters
        ]
