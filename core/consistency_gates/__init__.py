"""
一致性门禁系统 G1-G10 v1

理论来源：
- Tianming 6-gate 设计模式（代码级强制，非 prompt 规则）
- DOME 时序冲突分析器（Temporal Conflict Analyzer）
- Planning Beyond Text (arXiv:2604.21253)：全局连贯性、上下文逻辑一致性

架构说明：
门禁分两层——生成前门禁（G1-G5，在推送到画布前执行）和生成后审计（G6-G10，每章完成后全量执行）。
每道门禁独立可配置（开启/关闭/调节阈值），便于消融实验。

门禁结果：
- BLOCK：该段落不进入建议流
- WARN：进入建议流但带红色标注
- PASS：正常显示
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable
from datetime import datetime


# ═══════════════════════════════════════════
# 门禁核心类型
# ═══════════════════════════════════════════

class GateLevel(Enum):
    BLOCK = 0   # 阻断：不显示
    WARN = 1    # 警告：显示但标注
    PASS = 2    # 通过


class GatePhase(Enum):
    PRE_GENERATION = "生成前"  # G1-G5：在文本推送到建议流之前
    POST_CHAPTER = "章后审计"  # G6-G10：每章完成后


@dataclass
class GateResult:
    """一道门禁的检查结果"""
    gate_id: str
    gate_name: str
    level: GateLevel
    message: str = ""
    detail: str = ""                    # 详细描述
    source_location: Optional[str] = None  # 矛盾点的位置（章节+段落号）
    suggestion: str = ""                # 修改建议

    def to_dict(self) -> dict:
        return {
            "gate_id": self.gate_id,
            "gate_name": self.gate_name,
            "level": self.level.name,
            "message": self.message,
            "detail": self.detail,
            "source": self.source_location,
            "suggestion": self.suggestion
        }


@dataclass
class AuditReport:
    """一章的审计报告——由 G6-G10 全量审计生成"""
    chapter: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    results: list[GateResult] = field(default_factory=list)
    overall_score: float = 100.0  # 100分制

    def add(self, result: GateResult):
        self.results.append(result)
        penalty = 20 if result.level == GateLevel.BLOCK else 10
        self.overall_score = max(0, self.overall_score - penalty)

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "timestamp": self.timestamp,
            "overall_score": self.overall_score,
            "results": [r.to_dict() for r in self.results]
        }


# ═══════════════════════════════════════════
# 一致性门禁系统
# ═══════════════════════════════════════════

class ConsistencyGateSystem:
    """
    一致性门禁系统 G1-G10

    生成前门禁（G1-G5）：
      G1 事实一致性：所有事实陈述必须与知识图谱匹配
      G2 信念一致性：角色行为必须与其当前信念状态一致
      G3 身份连续性：角色人格/能力/关系不能突变而无解释
      G4 时间线一致性：时序冲突检测
      G5 空间一致性：地理位置/距离/可达性

    生成后审计（G6-G10）：
      G6 因果链完整性：所有伏笔/线索须有闭合或显式保留
      G7 叙事节奏审计：对比类型契约检查结构完整性
      G8 认知负荷审计：读者模型预测"更新成本"不超过阈值
      G9 去AI化检测：句式多样性/词汇密度/对话自然度统计
      G10 冷却矩阵：爽点/冲突分布是否过于密集或稀疏

    所有门禁默认开启（active=True）。可通过 gate_config 关闭指定门禁用于实验。
    """

    def __init__(self, gate_config: Optional[dict[str, bool]] = None):
        self.gate_config = gate_config or {}

        # 依赖注入——这些由外部设置
        self.knowledge_graph = None   # TemporalKnowledgeGraph 实例
        self.tom_engine = None        # TheoryOfMindEngine 实例
        self.reader_model = None      # ReaderModel 实例

        self._current_chapter = 0
        self._audit_history: list[AuditReport] = []

    def set_dependencies(self, kg=None, tom=None, reader=None):
        """注入依赖"""
        self.knowledge_graph = kg
        self.tom_engine = tom
        self.reader_model = reader

    def _is_active(self, gate_id: str) -> bool:
        """检查门禁是否开启"""
        return self.gate_config.get(gate_id, True)

    # ═══════════════════════════════════════
    # 生成前门禁 G1-G5
    # ═══════════════════════════════════════

    def check_g1_fact_consistency(self, text: str, facts: list[dict] = None) -> Optional[GateResult]:
        """
        G1 事实一致性

        从文本中提取事实陈述，与知识图谱比对。
        如果文本说"他父亲在他10岁时教他剑法"，
        但已提交的图谱显示"他父亲在他5岁时去世"→ BLOCK。
        """
        if not self._is_active("G1") or not self.knowledge_graph:
            return None

        if not facts:
            # 如果没有预提取的事实列表，返回 PASS
            return None

        for fact in facts:
            subject = fact.get("subject", "")
            predicate = fact.get("predicate", "")
            obj = fact.get("object", "")

            if not subject:
                continue

            conflicts = self.knowledge_graph.detect_conflicts(
                f"{predicate}{obj}", subject
            )
            if conflicts:
                detail = "; ".join(conflicts)
                return GateResult(
                    gate_id="G1",
                    gate_name="事实一致性",
                    level=GateLevel.BLOCK,
                    message=f"事实矛盾：{detail}",
                    detail=f"文本声称「{subject}{predicate}{obj}」，但已有图谱显示 {detail}",
                    source_location=self._find_location_in_text(text, subject)
                )
        return None

    def check_g2_belief_consistency(self, text: str, char_actions: list[dict] = None) -> Optional[GateResult]:
        """
        G2 信念一致性

        检查角色行为是否与其当前信念状态一致。
        如果角色A相信角色B是朋友，但突然举报B → WARN/BLOCK。

        利用 ToM 引擎的 validate_action 方法。
        """
        if not self._is_active("G2") or not self.tom_engine:
            return None

        if not char_actions:
            return None

        for action in char_actions:
            char_id = action.get("character_id", "")
            action_desc = action.get("description", "")

            if not char_id or not action_desc:
                continue

            conflict = self.tom_engine.validate_action(char_id, action_desc)
            if conflict:
                # 检查是否有"新发现"来解释这个行为
                char = self.tom_engine.get_character(char_id)
                if char:
                    world_beliefs_count = len(char.world_beliefs)
                    if world_beliefs_count > 3:
                        # 如果有足够多的信念，说明角色有深层动机，降低为 WARN
                        return GateResult(
                            gate_id="G2",
                            gate_name="信念一致性",
                            level=GateLevel.WARN,
                            message=f"角色行为与信念不一致：{conflict}",
                            detail=f"需要添加合理解释（角色&apos;发现了新证据&apos;或&apos;被迫伪装&apos;）",
                            suggestion="给角色一个改变行为的内在动机"
                        )

                return GateResult(
                    gate_id="G2",
                    gate_name="信念一致性",
                    level=GateLevel.BLOCK,
                    message=f"角色行为严重违背信念：{conflict}",
                    detail="没有任何信念层面的解释"
                )
        return None

    def check_g3_identity_continuity(self, text: str, changes: list[dict] = None) -> Optional[GateResult]:
        """
        G3 身份连续性

        角色的人格特征、能力、关键关系不能突变而无解释。
        参考 Tianming 的"未知实体检测"和"描述一致性检查"。
        """
        if not self._is_active("G3"):
            return None

        if not changes:
            return None

        for change in changes:
            char_name = change.get("character", "")
            property_name = change.get("property", "")
            old_val = change.get("from", "")
            new_val = change.get("to", "")

            if not all([char_name, property_name, old_val, new_val]):
                continue

            # 检查是否有合理解释
            has_explanation = change.get("explanation", False)
            if not has_explanation:
                return GateResult(
                    gate_id="G3",
                    gate_name="身份连续性",
                    level=GateLevel.WARN,
                    message=f"{char_name}的{property_name}从「{old_val}」突变为「{new_val}」",
                    detail="没有提供合理解释",
                    suggestion=f"在之前的章节中铺垫{char_name}{property_name}的变化动机"
                )
        return None

    def check_g4_timeline_consistency(self, text: str, events: list[dict] = None) -> Optional[GateResult]:
        """
        G4 时间线一致性

        事件顺序、角色年龄、季节等时序冲突检测。
        利用知识图谱的 check_temporal_consistency 方法。
        """
        if not self._is_active("G4") or not self.knowledge_graph:
            return None

        if not events:
            return None

        for event in events:
            event_name = event.get("event", "")
            reference_chapter = event.get("reference_chapter", self._current_chapter)

            if not event_name:
                continue

            conflict = self.knowledge_graph.check_temporal_consistency(
                event_name, reference_chapter
            )
            if conflict:
                return GateResult(
                    gate_id="G4",
                    gate_name="时间线一致性",
                    level=GateLevel.BLOCK,
                    message=conflict,
                    detail=f"事件「{event_name}」的时序不合理"
                )
        return None

    def check_g5_spatial_consistency(self, text: str, movements: list[dict] = None) -> Optional[GateResult]:
        """
        G5 空间一致性

        角色位置、地点距离、可达性检查。
        """
        if not self._is_active("G5"):
            return None

        if not movements:
            return None

        for move in movements:
            char = move.get("character", "")
            from_place = move.get("from", "")
            to_place = move.get("to", "")
            travel_time = move.get("travel_time_hours", 0)

            if not all([char, from_place, to_place]):
                continue

            # 检查距离合理性
            known_distance = move.get("known_distance_km", 0)
            if known_distance > 0:
                reasonable_time = known_distance / 5  # 假设步行 5km/h
                if travel_time < reasonable_time * 0.3:  # 太快了
                    return GateResult(
                        gate_id="G5",
                        gate_name="空间一致性",
                        level=GateLevel.WARN,
                        message=f"{char}从{from_place}到{to_place}（约{known_distance}km）",
                        detail=f"在{travel_time}小时内到达不太合理",
                        suggestion="提供交通工具的解释"
                    )
        return None

    # ═══════════════════════════════════════
    # 生成前全量检查
    # ═══════════════════════════════════════

    def pre_generation_check(self, text: str, context: dict = None) -> list[GateResult]:
        """生成前全量门禁检查——G1 到 G5

        这是 AI 生成文本推送到建议流之前的"网关"。
        任一 G1 返回 BLOCK → 文本不显示。

        context 中应该包含：
          - facts: 从文本中提取的事实陈述列表
          - char_actions: 文本中涉及的角色行动
          - identity_changes: 文本中涉及的角色身份变化
          - events: 文本中提到的事件
          - movements: 文本中涉及的空间移动
        """
        results = []
        context = context or {}

        checks = [
            ("G1", self.check_g1_fact_consistency(text, context.get("facts"))),
            ("G2", self.check_g2_belief_consistency(text, context.get("char_actions"))),
            ("G3", self.check_g3_identity_continuity(text, context.get("identity_changes"))),
            ("G4", self.check_g4_timeline_consistency(text, context.get("events"))),
            ("G5", self.check_g5_spatial_consistency(text, context.get("movements"))),
        ]

        for gid, result in checks:
            if result:
                results.append(result)

        # 如果有 BLOCK 级别门禁触发，不在建议流中显示
        has_block = any(r.level == GateLevel.BLOCK for r in results)

        return results

    # ═══════════════════════════════════════
    # 生成后审计 G6-G10
    # ═══════════════════════════════════════

    def audit_g6_causal_chain(self, chapter_text: str, plot_state: dict = None) -> Optional[GateResult]:
        """
        G6 因果链完整性

        检查新章节中是否引入了伏笔/线索但没有回收预期。
        如果之前注册的未闭合线索在新章节中既未推进也未闭合 → WARN。
        """
        if not self._is_active("G6"):
            return None

        if not plot_state:
            return None

        open_threads = plot_state.get("open_threads", [])
        resolved_this_chapter = plot_state.get("resolved_this_chapter", [])

        for thread in open_threads:
            tid = thread.get("id", "")
            expected_chapter = thread.get("expected_resolve_chapter", 0)

            if tid not in resolved_this_chapter:
                if expected_chapter and expected_chapter <= self._current_chapter:
                    return GateResult(
                        gate_id="G6",
                        gate_name="因果链完整性",
                        level=GateLevel.WARN,
                        message=f"线索「{thread.get('description', '')}」超过预期回收章节({expected_chapter})",
                        detail="建议在新章节中推进或回收"
                    )
        return None

    def audit_g7_narrative_rhythm(self, chapter_text: str, genre_contract: dict = None) -> Optional[GateResult]:
        """
        G7 叙事节奏审计

        对比类型契约检查关键节点是否在正确的章节位置。
        例如悬疑推理的前3章必须有"异常建立"。
        """
        if not self._is_active("G7") or not genre_contract:
            return None

        required_scenes = genre_contract.get("required_scenes", [])
        if not required_scenes:
            return None

        if self._current_chapter <= 3:
            # 黄金三章检查
            if "异常开场" in required_scenes or "冲突开场" in required_scenes:
                if "conflict" not in chapter_text.lower() and "异常" not in chapter_text:
                    return GateResult(
                        gate_id="G7",
                        gate_name="叙事节奏",
                        level=GateLevel.WARN,
                        message="前3章未建立冲突/异常信号",
                        detail=f"类型契约要求：{', '.join(required_scenes[:3])}",
                        suggestion="确保前300字内出现冲突/威胁/秘密/异常之一"
                    )
        return None

    def audit_g8_cognitive_load(self, chapter_text: str, reader_context: dict = None) -> Optional[GateResult]:
        """
        G8 认知负荷审计

        检查新章节中引入的新元素（角色/地点/设定）数量是否超过阈值。
        参考学术界"事件模型更新成本"理论。
        """
        if not self._is_active("G8"):
            return None

        if not reader_context:
            return None

        new_characters = reader_context.get("new_characters", 0)
        new_locations = reader_context.get("new_locations", 0)
        pov_switches = reader_context.get("pov_switches", 0)

        load_score = (new_characters * 3 + new_locations * 2 + pov_switches * 4)

        if load_score > 15:
            return GateResult(
                gate_id="G8",
                gate_name="认知负荷",
                level=GateLevel.WARN,
                message=f"本章认知更新成本过高（得分{load_score}）",
                detail=f"新角色{new_characters}个 + 新地点{new_locations}个 + POV切换{pov_switches}次",
                suggestion="减少新角色引入或保持POV一致性"
            )
        return None

    def audit_g9_deai_detection(self, chapter_text: str) -> Optional[GateResult]:
        """
        G9 去AI化检测

        统计文本的句式多样性、词汇密度、对话自然度。
        参考 InkOS 的"去AI味"检测和 Novel-Creator-Skill 的7类打磨。
        """
        if not self._is_active("G9"):
            return None

        import re

        sentences = re.split(r'[。！？\n.!?]', chapter_text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) < 5:
            return None

        # 检查AI标志词
        ai_markers = ["然而", "值得注意的是", "不可否认", "不出所料", "愈发",
                      "毫无疑问", "显而易见", "值得一提的是", "令人惊讶的是"]
        marker_count = sum(1 for s in sentences
                           for m in ai_markers if m in s)

        # 检查句式重复（连续3句以同样的方式开头）
        openings = []
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
            return GateResult(
                gate_id="G9",
                gate_name="去AI化检测",
                level=GateLevel.WARN,
                message="; ".join(warnings),
                detail="建议使用口语化表达、打断对话、非典型词汇",
                suggestion="每段留1-2处非标准表达，打破'完美文本'模式"
            )
        return None

    def audit_g10_cooldown_matrix(self, chapter_text: str, matrix_state: dict = None) -> Optional[GateResult]:
        """
        G10 冷却矩阵

        检查爽点/冲突分布是否过于密集或稀疏。
        参考 Novel-Creator-Skill 的事件冷却矩阵。
        """
        if not self._is_active("G10") or not matrix_state:
            return None

        recent_patterns = matrix_state.get("recent_patterns", [])
        if not recent_patterns:
            return None

        # 检查重复模式
        from collections import Counter
        pattern_counts = Counter(recent_patterns[-5:])
        most_common = pattern_counts.most_common(1)

        if most_common and most_common[0][1] >= 3:
            pattern, count = most_common[0]
            return GateResult(
                gate_id="G10",
                gate_name="事件冷却矩阵",
                level=GateLevel.WARN,
                message=f"叙事模式「{pattern}」在最近5章中出现{count}次",
                detail="相同模式过于密集会导致读者审美疲劳",
                suggestion=f"尝试用不同的冲突类型替代{pattern}"
            )
        return None

    # ═══════════════════════════════════════
    # 章后全量审计
    # ═══════════════════════════════════════

    def post_chapter_audit(self, chapter_text: str,
                          plot_state: dict = None,
                          genre_contract: dict = None,
                          reader_context: dict = None,
                          matrix_state: dict = None) -> AuditReport:
        """每章完成后的全量审计（G6-G10）"""
        self._current_chapter += 1
        report = AuditReport(chapter=self._current_chapter)

        for result in [
            self.audit_g6_causal_chain(chapter_text, plot_state),
            self.audit_g7_narrative_rhythm(chapter_text, genre_contract),
            self.audit_g8_cognitive_load(chapter_text, reader_context),
            self.audit_g9_deai_detection(chapter_text),
            self.audit_g10_cooldown_matrix(chapter_text, matrix_state),
        ]:
            if result:
                report.add(result)

        self._audit_history.append(report)
        return report

    # ═══════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════

    def _find_location_in_text(self, text: str, keyword: str) -> str:
        """在文本中定位关键词出现的位置"""
        if keyword in text:
            paragraphs = text.split("\n")
            for i, para in enumerate(paragraphs):
                if keyword in para:
                    return f"第{self._current_chapter}章第{i + 1}段附近"
        return f"第{self._current_chapter}章"

    def get_audit_history(self) -> list[AuditReport]:
        return self._audit_history

    def get_average_score(self) -> float:
        if not self._audit_history:
            return 100.0
        return sum(r.overall_score for r in self._audit_history) / len(self._audit_history)
