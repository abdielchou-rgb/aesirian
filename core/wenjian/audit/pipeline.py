"""文鉴 Audit Pipeline V3 — 三层面审计 + 新分析层桥接。

v4.1 升级:
- _apply_profile → _enrich_context: 自动桥接 narrative_analyzer / webnovel_analyzer / sentiment_lexicon 输出
- _eval: 新增 28 个上下文感知调度 (act_pct / arc_type / rhythm_score / sentiment_curve ...)
- run_full: 支持全稿批量 enrichment
"""

from __future__ import annotations

from wenjian.audit.gates import ALL_GATES, get_gate
from wenjian.genres import GenreProfile, get_profile
from wenjian.models import AuditReport, GateResult

HOOK_KEYWORDS = [
    "突然",
    "但是",
    "然而",
    "没想到",
    "却发现",
    "竟",
    "原来",
    "为什么",
    "怎么回事",
    "来不及",
    "有件事",
    "你知",
]

# ─── 结构门禁适用性（#C 误报治理） ──────────────────────────
# 这些门禁设计为跨章/全稿分析：单章提交时其必需的上下文字段天然缺失，
# 强行评估会把"无数据"判为"违规"。字段缺失时跳过并标注 SKIPPED。
# 当调用方（全稿分析/多章批量）提供字段后，门禁自动恢复生效。
STRUCTURAL_GATE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "SVT-01": ("entry_value", "exit_value"),  # 场景价值观翻转
    "SVT-02": ("recent_scene_flips",),  # 近期翻转序列
    "SVT-04": ("has_irreversible_turn",),  # 幕级翻转
    "IIT-02": ("has_conscious_desire",),  # 双重欲望声明
    "IIT-03": ("is_reversible",),  # 不可逆性
    "DDT-01": ("character",),  # 角色欲望档案
    "DDT-02": ("character",),
    "DDT-03": ("character",),
    "DDT-04": ("character",),
    "CLM-01": ("active_layers",),  # 冲突层级
    "CLM-02": ("has_crossover",),
    "CLM-03": ("external_intensity",),
    "RVI-03": ("gap_id",),  # 缺口暗示追踪
    "RVI-04": ("total_open_gaps",),  # 全稿缺口账本
    "RVI-05": ("gap_id",),
    "TPE-02": ("scene_id",),  # 触点场景档案
    "TPE-03": ("scene_id",),
    "SPN-01": ("gap_id",),  # 悬念追踪需 gap 档案
    "SPN-03": ("gap_id",),
    "SCQ-01": ("scene_type",),  # 场景类型标注
    "BRK-04": ("hook_type",),  # 钩子类型需已检出钩子
    "NFR-03": ("foreshadow_mentions",),  # 伏笔提及计数
    "NFR-04": ("anchor_context",),  # 跳读锚点
    "RSM-01": ("pov_beliefs",),  # 罗生门视角系统
    "RSM-02": ("pov_beliefs",),
    "RSM-03": ("pov_beliefs",),
    "ARC-01": ("position_pct",),  # 长篇弧线定位
    "ARC-04": ("has_climax_change",),
    "ARC-05": ("chapters_since_arc_reset",),
    "ARC-06": ("projected_chapters",),
    "CRN-01": ("relationship_map",),  # 关系网档案
    "CRN-02": ("relationship_map",),
    "CRN-03": ("relationship_map",),
    "CRN-04": ("relationship_map",),
    "CRN-05": ("relationship_map",),
    "CRN-06": ("relationship_map",),
    "SCQ-02": ("previous_exit",),  # 场景-续章链
    "ROE-04": ("misunderstanding_cycles",),  # 误会循环史
    "CTB-02": ("broken_chains",),  # 因果链断裂史
    "MCO-02": ("abrupt_transitions",),  # 转场突兀记录

    # ── P1-5 (2026-09-07): 跨章专用门禁族 ──
    # 此前 STC-01..22（风格一致性漂移）与 RVI-06（邪恶力量揭示节奏）虽注册在
    # GATE_CATALOG 且被 run_full 遍历，但 safe_eval 无对应分支 → 静默落到
    # `return gate.pass_result()`（假通过）。这些门禁本质上需要跨章数据
    # （风格基线 / 伏笔揭示历史），单章路径给不出真实入参。
    # 修复：声明为"缺跨章上下文即 SKIPPED"，杜绝 registry 有而 dispatcher 无
    # 的静默漂移；未来跨章/全稿路径提供 style_baseline 等字段后自动恢复生效。
    "STC-01": ("style_baseline",),  # 副词密度漂移
    "STC-02": ("style_baseline",),  # 被动语态漂移
    "STC-03": ("style_baseline",),  # 填充词/副词比
    "STC-04": ("style_baseline",),  # 词汇多样性下降
    "STC-05": ("style_baseline",),  # 难词突增
    "STC-06": ("style_baseline",),  # 情绪词漂移
    "STC-07": ("style_baseline",),  # 句长方差
    "STC-08": ("style_baseline",),  # 句长漂移
    "STC-09": ("style_baseline",),  # 最长句占比
    "STC-10": ("style_baseline",),  # 对话密度漂移
    "STC-11": ("style_baseline",),  # 段长漂移
    "STC-12": ("style_baseline",),  # 章末收束力
    "STC-13": ("style_baseline",),  # 钩子密度漂移
    "STC-14": ("style_baseline",),  # 鸿沟密度漂移
    "STC-15": ("style_baseline",),  # 类型契合下降
    "STC-16": ("style_baseline",),  # 情绪连贯性
    "STC-17": ("style_baseline",),  # 幕结构转换
    "STC-18": ("style_baseline",),  # 节奏评分下降
    "STC-19": ("style_baseline",),  # 情感熵变化
    "STC-20": ("style_baseline",),  # 情绪-张力错配
    "STC-21": ("style_baseline",),  # 综合漂移分
    "STC-22": ("style_baseline",),  # 连续漂移章节
    "RVI-06": ("evil_force_history",),  # 邪恶力量揭示节奏
}


def _missing_structural_fields(gid: str, ctx: dict) -> list[str]:
    """结构门禁必需字段缺失检测。

    约定：ctx 中存在键但值为空列表/None/"" 视为缺失（调用方未提供）；
    布尔 False 是合法值（如 has_irreversible_turn=False），不算缺失。
    """
    required = STRUCTURAL_GATE_REQUIREMENTS.get(gid)
    if not required:
        return []
    missing = []
    for key in required:
        if key not in ctx:
            missing.append(key)
        else:
            v = ctx[key]
            if v is None or v == "" or v == []:
                missing.append(key)
    # 特例：character 是 dict，键存在即视为提供（safe_eval 内部再取子字段）
    return [m for m in missing if m != "character"] + (
        ["character"] if "character" in required and not ctx.get("character") else []
    )


# 章节进度门禁：仅在达到足够章节数时评估（如"第三章必须有爽点"在首章不适用）
# gid -> 需要达到的 chapter_index（0-based），不足则跳过
PROGRESSION_GATES = {
    "G3-04": 1,  # 第二章目标：第 2 章才评估
    "G3-05": 2,  # 第三章爽点：第 3 章
    "G3-06": 2,  # 第三章钩子：第 3 章
    "PLE-01": 2,  # 爽点密度（跨 3 章节奏）：至少 3 章
    "PLE-04": 1,  # 升级节奏：至少 2 章
    "APL-02": 2,  # 全稿审计逾期：至少 3 章
}


def _missing_progression(gid: str, ctx: dict) -> bool:
    """进度门禁：chapter_index 不足时跳过"""
    need = PROGRESSION_GATES.get(gid)
    if need is None:
        return False
    ch = int(ctx.get("chapter_index", 0) or 0)
    return ch < need


# ─── P1-5 (2026-09-07): schema 驱动自动绑定 ─────────────────────
# safe_eval 的历史形态是 143 个 `if gid=="X"` 分支，未覆盖的门禁会静默落到
# `return gate.pass_result()`——"registry 有而 dispatcher 无"的死门禁（此前
# STC-01..22 与 RVI-06 共 23 道即如此：注册、被遍历、却永不真跑）。
# 修复：跨章专用门禁已声明进 STRUCTURAL_GATE_REQUIREMENTS（单章缺数据即
# SKIPPED）；此处提供 schema 驱动兜底——若调用方（跨章/全稿路径）通过
# style_baseline / context 提供了 evaluate 所需参数，则按 GATE_CATALOG 的
# params schema 自动绑定真跑；必要参数仍缺失则显式 SKIPPED，绝不静默 PASS。

def _auto_bind_evaluate(gate, context: dict) -> GateResult:
    """按 registry params schema 自动绑定并调用 gate.evaluate。

    参数来源优先级：context[param] → context["style_baseline"][param]。
    必填（无默认值）参数缺失时返回 SKIPPED（passed=True, skipped=True），
    避免把"无数据"误判为"通过"或"违规"。
    """
    import inspect

    from wenjian.audit.gates import GATE_CATALOG

    meta = GATE_CATALOG.get(gate.gate_id)
    if not meta:
        # registry 外门禁（罕见）：保守 PASS
        return gate.pass_result()

    sig = inspect.signature(gate.evaluate)
    style_baseline = context.get("style_baseline") or {}
    kwargs: dict = {}
    missing_required: list[str] = []
    for pname in meta.get("params", []):
        p = sig.parameters.get(pname)
        if pname in context and context[pname] is not None:
            kwargs[pname] = context[pname]
        elif pname in style_baseline:
            kwargs[pname] = style_baseline[pname]
        elif p is not None and p.default is not inspect.Parameter.empty:
            kwargs[pname] = p.default  # 有默认值：用默认（门禁内部自判"基线不足"）
        else:
            missing_required.append(pname)

    if missing_required:
        return GateResult(
            gate_id=gate.gate_id,
            name=gate.name,
            severity=gate.severity,
            passed=True,
            message=f"SKIPPED — schema 自动绑定缺必要参数: {', '.join(missing_required[:3])}",
            skipped=True,
        )
    try:
        return gate.evaluate(**kwargs)
    except Exception as e:  # 自动绑定失败不应中断全量审计
        return GateResult(
            gate_id=gate.gate_id,
            name=gate.name,
            severity=gate.severity,
            passed=True,
            message=f"SKIPPED — 自动绑定评估异常: {e}",
            skipped=True,
        )


def _hook_density(text: str) -> float:
    return sum(text.count(h) for h in HOOK_KEYWORDS) / max(len(text) / 1000, 1)


class AuditPipeline:
    """三层面审计管道：实时 + 全稿 + 叙事增强。"""

    def __init__(self, config=None, genre_id: str = None, platform: str = None):
        self.config = config or {}
        self.profile: GenreProfile = get_profile(genre_id, platform)
        self._enrichment_cache: dict = {}

    def _enrich_context(self, context: dict) -> dict:
        ctx = dict(context)
        p = self.profile
        for k, attr in [
            ("deadline", "inciting_incident_deadline"),
            ("platform", "platform"),
            ("gap_overload_threshold", "gap_overload_threshold"),
            ("max_open_gaps", "max_open_gaps"),
            ("net_gap_rate", "max_gap_net_rate"),
            ("min_touchpoints", "min_touchpoints_for_critical"),
            ("hook_position_limit", "hook_position_limit"),
        ]:
            if k not in ctx:
                ctx[k] = getattr(p, attr)

        # ── 单章文本字段规范化 + 基础推导（#C 误报治理） ──
        text = ctx.get("chapter_text") or ctx.get("text") or ""
        ctx["chapter_text"] = text
        if "char_count" not in ctx or not ctx["char_count"]:
            ctx["char_count"] = len(text)
        if "chapter_index" not in ctx:
            ctx["chapter_index"] = int(ctx.get("chapter_number", 1) or 1) - 1
        if "dialogue_lines" not in ctx:
            ctx["dialogue_lines"] = sum(
                1 for ln in text.splitlines() if any(m in ln for m in "\"\" '' 「」")
            )
        if "line_count" not in ctx:
            ctx["line_count"] = max(len([ln for ln in text.splitlines() if ln.strip()]), 1)
        if "paragraph_count" not in ctx:
            ctx["paragraph_count"] = max(len([p for p in text.split("\n") if p.strip()]), 1)
        if "first_hook_position" not in ctx or ctx["first_hook_position"] in (99999, None):
            pos = 99999
            for kw in HOOK_KEYWORDS:
                i = text.find(kw)
                if 0 <= i < pos:
                    pos = i
            ctx["first_hook_position"] = pos
        if "touchpoints" not in ctx:
            ctx["touchpoints"] = sum(
                text.count(m)
                for m in [
                    "指尖",
                    "掌心",
                    "目光",
                    "眼神",
                    "声音",
                    "气味",
                    "味道",
                    "光线",
                    "月光",
                    "灯光",
                    "温度",
                    "颤抖",
                    "心跳",
                    "呼吸",
                    "呻吟",
                    "看见",
                    "听见",
                    "闻到",
                    "摸",
                    "握",
                    "滑过",
                ]
            )
        if "direct_emotions" not in ctx:
            ctx["direct_emotions"] = sum(
                text.count(m)
                for m in [
                    "愤怒",
                    "悲伤",
                    "开心",
                    "害怕",
                    "惊讶",
                    "高兴",
                    "痛苦",
                    "恐惧",
                    "喜悦",
                    "愧疚",
                    "沉默",
                ]
            )
        if "gap_densities" not in ctx or not ctx["gap_densities"]:
            gd = sum(1 for kw in HOOK_KEYWORDS if kw in text)
            # 语义悬念补充：疑问句/破折号/省略号 也是缺口信号
            gd += text.count("？") + text.count("——") + min(text.count("…"), 3)
            ctx["gap_densities"] = [round(gd / max(len(text) / 1000, 1), 2)]
        if "gap_count" not in ctx:
            ctx["gap_count"] = int(ctx["gap_densities"][-1])
        if "character_count" not in ctx or not ctx["character_count"]:
            # 中文角色提及启发式：2-3字名 + 说/道/问
            import re as _re

            names = set(_re.findall(r"([一-鿿]{2,3})(?:说|道|问|看|走|坐)", text))
            ctx["character_count"] = min(len(names), 8)
        if "words_since_last_gap" not in ctx:
            ctx["words_since_last_gap"] = len(text)
        return ctx

    def run_realtime(self, context: dict) -> AuditReport:
        ctx = self._enrich_context(context)
        report = AuditReport(report_id="realtime")
        for gid in ["SVT-01", "SVT-02", "GDA-01", "GDA-04", "TPE-01", "TPE-02"]:
            gate = get_gate(gid)
            try:
                result = self.safe_eval(gate, ctx)
            except Exception as e:
                result = GateResult(
                    gate_id=gid,
                    name=gate.name,
                    severity=gate.severity,
                    passed=False,
                    message=f"evaluation error: {e}",
                )
            report.add(result)
        return report

    def safe_eval(self, gate, context):
        """安全eval: 自动过滤gate.evaluate不接受的关键字参数"""
        import inspect

        gid = gate.gate_id
        sig = inspect.signature(gate.evaluate)
        accepted = set(sig.parameters.keys())
        cc = context.get("char_count", 0) or 0
        tp = context.get("touchpoints", 0) or 0
        emo = context.get("direct_emotions", 0) or 0
        gd = (context.get("gap_densities") or [0])[-1]
        ch_idx = context.get("chapter_index", 0) or 0
        dl = context.get("dialogue_lines", 0) or 0
        ln = context.get("line_count", 0) or 1
        pc = context.get("paragraph_count", 0) or 1
        hook = context.get("first_hook_position", 99999)
        char_ct = context.get("character_count", 0) or 0
        ct = context.get("chapter_text", "") or ""
        flipped = context.get("scene_flipped", False)
        gap_count = context.get("gap_count", 0) or 0
        ch = context.get("character", {})
        act_pct = context.get("act_pct", 0)
        act_sentiment = context.get("act_sentiment", 0)
        chapter_sentiment = context.get("chapter_sentiment", 0)
        webnovel_rhythm_score = context.get("webnovel_rhythm_score", 0)
        webnovel_rhythm_verdict = context.get("webnovel_rhythm_verdict", "")
        readability = context.get("readability", 0)
        pos_dist = context.get("pos_distribution", {})
        difficult_word_ratio = context.get("difficult_word_ratio", 0)
        avg_sentence_len = context.get("avg_sentence_len", 0)

        def kfilter(**kwargs):
            """只保留gate接受的参数"""
            return {k: v for k, v in kwargs.items() if k in accepted}

        try:
            if gid == "SVT-01":
                return gate.evaluate(context.get("entry_value", ""), context.get("exit_value", ""))
            if gid == "SVT-02":
                return gate.evaluate(context.get("recent_scene_flips", []))
            if gid == "SVT-03":
                return gate.evaluate(context.get("value_pair_counts", {}))
            if gid == "SVT-04":
                return gate.evaluate(
                    context.get("has_irreversible_turn", False), context.get("act_number", 1)
                )
            if gid == "IIT-01":
                return gate.evaluate(
                    context.get("inciting_position", 0), context.get("deadline", 25)
                )
            if gid == "IIT-02":
                return gate.evaluate(
                    context.get("has_conscious_desire", False),
                    context.get("has_unconscious_desire", False),
                )
            if gid == "IIT-03":
                return gate.evaluate(context.get("is_reversible", True))
            if gid.startswith("DDT-"):
                if gid == "DDT-01":
                    return gate.evaluate(
                        ch.get("name", ""),
                        ch.get("has_conscious", False),
                        ch.get("has_unconscious", False),
                    )
                if gid == "DDT-02":
                    return gate.evaluate(ch.get("name", ""), ch.get("desire_spoken", False))
                if gid == "DDT-03":
                    return gate.evaluate(ch.get("recent_progress", []))
                if gid == "DDT-04":
                    return gate.evaluate(
                        context.get("position", 0), ch.get("desire_status", "latent")
                    )
            if gid == "GDA-01":
                return gate.evaluate(
                    context.get("gap_densities", []), context.get("_gap_floor", 1.0)
                )
            if gid == "GDA-02":
                return gate.evaluate(
                    context.get("gap_densities", []), context.get("gap_overload_threshold", 6.0)
                )
            if gid == "GDA-03":
                return gate.evaluate(context.get("gap_intensities", []))
            if gid == "GDA-04":
                return gate.evaluate(context.get("words_since_last_gap", 0))
            if gid == "CLM-01":
                return gate.evaluate(context.get("active_layers", []))
            if gid == "CLM-02":
                return gate.evaluate(
                    context.get("position_pct", 0), context.get("has_crossover", False)
                )
            if gid == "CLM-03":
                return gate.evaluate(
                    context.get("external_intensity", 0), context.get("internal_intensity", 0)
                )
            if gid == "RVI-01":
                return gate.evaluate(context.get("chapters_since_new_gap", 0))
            if gid == "RVI-02":
                return gate.evaluate(context.get("chapters_since_resolution", 0))
            if gid == "RVI-03":
                return gate.evaluate(context.get("gap_id", ""), context.get("hint_count", 0))
            if gid == "RVI-04":
                return gate.evaluate(
                    context.get("total_open_gaps", 0),
                    context.get("net_gap_rate", 0),
                    context.get("max_open_gaps", 15),
                )
            if gid == "RVI-05":
                return gate.evaluate(
                    context.get("gap_id", ""),
                    context.get("tension", 5),
                    context.get("chapters_unmentioned", 0),
                )
            if gid == "TPE-01":
                return gate.evaluate(emo, tp)
            if gid == "TPE-02":
                return gate.evaluate(
                    context.get("scene_id", ""), tp, True, context.get("min_touchpoints", 2)
                )
            if gid == "TPE-03":
                return gate.evaluate(
                    context.get("scene_id", ""),
                    context.get("touchpoint_emotion", ""),
                    context.get("context_emotion", ""),
                )
            if gid == "PRP-01":
                return gate.evaluate(
                    context.get("declared_platform", ""), context.get("active_template", "")
                )
            if gid == "PRP-02":
                return gate.evaluate(
                    hook,
                    context.get("platform", "webnovel"),
                    context.get("hook_position_limit", 150),
                )
            if gid == "PRP-03":
                return gate.evaluate(
                    context.get("chapters_since_climax", 0),
                    self.profile.chapters_between_mini_climax or 5,
                    context.get("platform", "webnovel"),
                )
            if gid == "G3-01":
                return gate.evaluate(
                    context.get("first_conflict_position", 99999),
                    **kfilter(
                        first_sentiment=chapter_sentiment, act_number=context.get("act_number", 0)
                    ),
                )
            if gid == "G3-02":
                return gate.evaluate(context.get("protagonist_in_ch1", True))
            if gid == "G3-03":
                return gate.evaluate(context.get("why_questions", 1))
            if gid == "G3-04":
                return gate.evaluate(cc > 500)
            if gid == "G3-05":
                return gate.evaluate(gd > 0, **kfilter(rhythm_score=webnovel_rhythm_score))
            if gid == "G3-06":
                return gate.evaluate(True)
            if gid == "G3-07":
                return gate.evaluate(len(str(ct)[:50]) > 0)
            if gid == "BRK-01":
                return gate.evaluate(
                    context.get("has_cliffhanger", False), context.get("has_unresolved", False)
                )
            if gid == "BRK-02":
                return gate.evaluate("climax" if gd > 0 else "mid", **kfilter(act_pct=act_pct))
            if gid == "BRK-03":
                return gate.evaluate(
                    cc,
                    context.get("platform", "webnovel"),
                    **kfilter(avg_sentence_len=avg_sentence_len),
                )
            if gid == "BRK-04":
                return gate.evaluate(False)
            if gid == "BRK-01B":
                return gate.evaluate(ct)
            if gid == "BRK-04B":
                return gate.evaluate(ct)
            if gid == "DLG-01":
                return gate.evaluate(dl, ln, **kfilter(pos_distribution=pos_dist))
            if gid == "DLG-02":
                return gate.evaluate(emo, dl)
            if gid == "DLG-03":
                return gate.evaluate(min(dl // 2 + 1, 10))
            if gid == "DLG-04":
                return gate.evaluate(0, **kfilter(difficult_word_ratio=difficult_word_ratio))
            if gid == "DLG-05":
                return gate.pass_result()
            if gid == "DLG-06":
                return gate.evaluate(0, dl)
            if gid == "DLG-07":
                return gate.evaluate(tp > emo, max(ch_idx, 0), **kfilter(act_pct=act_pct))
            if gid == "LANG-01":
                return gate.evaluate(ct, **kfilter(readability=readability))
            if gid == "LANG-02":
                return gate.evaluate(ct)
            if gid == "LANG-03":
                return gate.evaluate(ct, **kfilter(difficult_word_ratio=difficult_word_ratio))
            if gid == "LANG-04":
                return gate.evaluate(ct.count("被"), max(len(ct) // 100, 1))
            if gid == "LANG-05":
                fillers = [
                    "基本上",
                    "实际上",
                    "非常",
                    "真的",
                    "有点",
                    "某种",
                    "似乎",
                    "好像",
                    "几乎",
                    "开始",
                    "然后",
                    "于是",
                    "接着",
                ]
                return gate.evaluate(sum(ct.count(f) for f in fillers), len(ct))
            if gid == "NFR-01":
                return gate.evaluate(ch_idx, context.get("recap_interval", 4))
            if gid == "NFR-02":
                return gate.evaluate(ch_idx, context.get("goal_restatement_interval", 3))
            if gid == "NFR-03":
                return gate.evaluate("", 0, 2)
            if gid == "NFR-04":
                return gate.evaluate("", ch_idx, **kfilter(readability=readability))
            if gid == "NFR-05":
                return gate.evaluate(True, ch_idx)
            if gid == "RSM-01":
                return gate.evaluate("主角", True, False)
            if gid == "RSM-02":
                return gate.evaluate(["主角"], "无")
            if gid == "RSM-03":
                return gate.evaluate(max(char_ct, 5), max(char_ct // 2, 3), 0)
            if gid == "PLE-01":
                return gate.evaluate(
                    int(max(tp, 0) // 2),
                    int(max(gd, 0) // 2),
                    ch_idx,
                    **kfilter(rhythm_score=webnovel_rhythm_score),
                )
            if gid == "PLE-02":
                return gate.evaluate(int(gd) if gd > 3 else 0, gd / max(cc / 1000, 1))
            if gid == "PLE-03":
                return gate.evaluate(True, True, True) if gd > 1 else gate.pass_result()
            if gid == "PLE-04":
                return gate.evaluate(ch_idx, False)
            if gid == "PLE-05":
                return gate.evaluate(True, True, True) if gd > 0 else gate.pass_result()
            if gid == "PLE-06":
                return gate.evaluate(max(tp, 1), max(tp, 1))
            if gid == "PLE-07":
                return gate.evaluate(
                    context.get("platform", "webnovel"),
                    min(context.get("upgrade_intervals", [1])),
                    max(context.get("upgrade_intervals", [1])),
                    **kfilter(rhythm_verdict=webnovel_rhythm_verdict),
                )
            if gid == "SCQ-01":
                return gate.evaluate("scene", gd > 0)
            if gid == "SCQ-02":
                return gate.evaluate(
                    context.get("previous_exit", ""),
                    context.get("current_entry", ""),
                    context.get("chain_strength", 1),
                )
            if gid == "SCQ-03":
                return gate.evaluate([1, 2, 3])
            if gid == "SCQ-04":
                return gate.evaluate(gd > 0, flipped)
            if gid == "SCQ-05":
                return gate.evaluate(max(dl // 2, 1), max(emo, 1))
            if gid == "ROE-01":
                return gate.evaluate(max(tp, 0), max(cc, 1), **kfilter(sentiment=chapter_sentiment))
            if gid == "ROE-02":
                return gate.evaluate(max(tp // 2, 0), max(tp // 3, 0), 0)
            if gid == "ROE-03":
                return gate.evaluate(max(tp, 3), max(ch_idx, 3), 3)
            if gid == "ROE-04":
                return gate.evaluate(max(ch_idx, 0), False)
            if gid == "ROE-05":
                return gate.evaluate(max(tp, 0), max(emo, 0))
            if gid == "ROE-06":
                return gate.evaluate(max(char_ct, 0), max(ch_idx, 1), max(ch_idx, 1))
            if gid == "QLT-01":
                return gate.evaluate(0, max(pc, 1), 0)
            if gid == "QLT-01B":
                return gate.evaluate(ct)
            if gid == "QLT-02":
                return gate.evaluate(0, ch_idx)
            if gid == "QLT-03":
                return gate.evaluate(
                    float(gd) / 5,
                    ch_idx,
                    context.get("platform", "webnovel"),
                    **kfilter(sentiment=chapter_sentiment),
                )
            if gid == "QLT-04":
                return gate.evaluate(
                    1.0 if gd > 0 else 0.0,
                    "叙事" if gd > 0 else "无关",
                    **kfilter(rhythm_score=webnovel_rhythm_score),
                )
            if gid == "QLT-05":
                return gate.evaluate(max(gap_count, 0))
            if gid == "SPN-01":
                return gate.evaluate(
                    "?",
                    float(gd),
                    float(gd),
                    ch_idx,
                    **kfilter(act_pct=act_pct, act_sentiment=act_sentiment),
                )
            if gid == "SPN-02":
                return gate.evaluate(float(max(gd, 0)))
            if gid == "SPN-03":
                return gate.evaluate("?", float(gd), ch_idx, **kfilter(act_pct=act_pct))
            if gid == "SPN-04":
                return gate.evaluate(float(max(gd, 0)), max(int(gd), 0), 0)
            if gid == "ARC-01":
                return gate.evaluate(
                    context.get("position_pct", 0), context.get("inciting_position", 0) > 0
                )
            if gid == "ARC-02":
                return gate.evaluate("生存", "成长", 0)
            if gid == "ARC-03":
                return gate.evaluate("弱点", 0, 1)
            if gid == "ARC-04":
                return gate.evaluate(False, "", "", **kfilter(chapter_sentiment=chapter_sentiment))
            if gid == "ARC-05":
                return gate.evaluate(30, ch_idx, 0)
            if gid == "ARC-06":
                return gate.evaluate(ch_idx, context.get("total_chapters", 30))
            if gid == "ARC-07":
                return gate.evaluate(gd, gd, 0, False, **kfilter(sentiment=chapter_sentiment))
            if gid == "ARC-08":
                return gate.evaluate(hook < 99999, gd, **kfilter(act_pct=act_pct))
            if gid == "ARC-09":
                return gate.evaluate(1, **kfilter(sentiment=chapter_sentiment))
            if gid == "STR-01":
                return gate.evaluate(gd, ch_idx, **kfilter(readability=readability))
            if gid == "STR-02":
                return gate.evaluate("scene", True)
            if gid == "STR-03":
                return gate.evaluate(True, True, True, flipped)
            if gid == "STR-04":
                return gate.evaluate([gd], 0)
            if gid == "STR-05":
                return gate.evaluate(False, "scene")
            if gid == "STR-06":
                return gate.evaluate(cc, max(context.get("total_chapters", 30) // 30 * 3000, 1500))
            if gid == "STR-07":
                return gate.evaluate(
                    context.get("position_pct", 0), False, False, **kfilter(act_pct=act_pct)
                )
            if gid == "CRN-01":
                return gate.evaluate("主角", char_ct)
            if gid == "CRN-02":
                return gate.evaluate("主角", max(char_ct // 2, 1), max(char_ct // 3, 1))
            if gid == "CRN-03":
                return gate.evaluate(max(char_ct, 1), max(char_ct, 1))
            if gid == "CRN-04":
                return gate.evaluate(False, False, False)
            if gid == "CRN-05":
                return gate.evaluate(False, 1, False)
            if gid == "CRN-06":
                return gate.evaluate(char_ct, max(char_ct * 2, 0))
            if gid in ("MTS-01", "MT-01"):
                return gate.evaluate(int(max(gd, 1)), cc)
            if gid in ("MTS-02", "MT-02"):
                return gate.evaluate(int(max(gd / 2, 1)), cc)
            if gid == "CTP-01":
                return gate.evaluate(gd > 0, tp > 0, flipped)
            if gid == "CTP-02":
                return gate.evaluate("", max(emo - tp, 0))
            if gid == "CTB-01":
                return gate.evaluate(max(context.get("total_chapters", 0), 1), 0)
            if gid == "CTB-02":
                return gate.evaluate(0, ch_idx)
            if gid == "PRC-01":
                return gate.evaluate(emo, tp)
            if gid == "PRC-02":
                return gate.evaluate(context.get("gap_densities", []))
            if gid == "MCO-01":
                return gate.evaluate(max(gap_count, 0), cc)
            if gid == "MCO-02":
                return gate.evaluate(0, max(pc // 3, 1))
            if gid == "APL-01":
                return gate.evaluate(hook, max(gap_count, 0))
            if gid == "APL-02":
                return gate.evaluate(hook < 99999, flipped)
            avg_s = cc / max(dl + ln + 1, 1)
            if gid == "MRD-01":
                return gate.evaluate(min(avg_s, 50), min(gd / 5, 1))
            avg_p = cc / max(pc, 1)
            if gid == "MRD-02":
                return gate.evaluate(min(avg_p, 200), max(0, int(avg_p > 200) * pc // 5))
            if gid == "INR-01":
                return gate.evaluate(min(max(char_ct, 1), 5))
            if gid == "G10-04":
                return gate.evaluate(chapter_index=ch_idx, chapter_text=ct)
            if gid == "G10-05":
                return gate.evaluate(
                    chapter_index=ch_idx,
                    gap_density=gd,
                    **kfilter(climax_signals=context.get("climax_signals", 0), act_pct=act_pct),
                )
            if gid == "G10-07":
                return gate.evaluate(
                    chapter_index=ch_idx,
                    chapter_text=ct,
                    **kfilter(proactivity_score=context.get("proactivity_score", 0)),
                )
            if gid == "G10-08":
                return gate.evaluate(
                    chapter_index=ch_idx,
                    chapter_text=ct,
                    **kfilter(opponent_present=context.get("opponent_present", False)),
                )
            if gid == "G10-09":
                return gate.evaluate(
                    chapter_index=ch_idx,
                    chapter_text=ct,
                    **kfilter(
                        failure_detected=context.get("failure_detected", False),
                        sentiment=chapter_sentiment,
                    ),
                )
            if gid == "G10-10":
                return gate.evaluate(
                    chapter_index=ch_idx,
                    chapter_text=ct,
                    **kfilter(
                        upgrade_detected=context.get("upgrade_detected", False),
                        rhythm_score=webnovel_rhythm_score,
                    ),
                )
            if gid == "IIT-04":
                return gate.evaluate(
                    context.get("position_pct", 0), 0, 0, **kfilter(act_pct=act_pct)
                )
            if gid == "IIT-05":
                return gate.evaluate(
                    context.get("position_pct", 0),
                    float(gd),
                    gd,
                    **kfilter(sentiment=chapter_sentiment),
                )
            if gid == "QLT-06":
                return gate.evaluate(ch_idx, _hook_density(ct) if ct else 0, 1)
            if gid == "DRM-01":
                return gate.evaluate(
                    chapter_text=ct, **kfilter(domain_tags=context.get("domain_tags"))
                )
            if gid == "DRM-02":
                return gate.evaluate(
                    **kfilter(
                        problem_stated=context.get("problem_stated", False),
                        solution_applied=context.get("solution_applied", False),
                        position_pct=context.get("position_pct", 0),
                    )
                )
            if gid == "HOL-01":
                return gate.evaluate(
                    chapter_text=ct, **kfilter(position_pct=context.get("position_pct", 0))
                )
            if gid == "NEU-01":
                return gate.evaluate(chapter_text=ct, **kfilter(sentiment=chapter_sentiment))
            if gid == "NEU-02":
                return gate.evaluate(chapter_text=ct)
            if gid == "NEU-03":
                return gate.evaluate(chapter_text=ct)
            if gid == "TRB-01":
                return gate.evaluate(
                    chapter_text=ct, **kfilter(position_pct=context.get("position_pct", 0))
                )
            if gid == "WNM-01":
                return gate.evaluate(chapter_text=ct)
            # P1-5: 显式分支外的门禁不再静默 pass——schema 自动绑定（真跑）或 SKIPPED
            return _auto_bind_evaluate(gate, context)
        except Exception as e:
            return GateResult(
                gate_id=gid,
                name=gate.name,
                severity=gate.severity,
                passed=False,
                message=f"evaluation error: {e}",
            )

    def run_full(self, context: dict) -> AuditReport:
        ctx = self._enrich_context(context)
        report = AuditReport(report_id="full")
        if (
            "SVT-03" in ALL_GATES
            and ctx.get("position_pct", 0) < self.profile.value_monotone_activation_pct
        ):
            ctx["_skip_svt03"] = True
        if "IIT-03" in ALL_GATES and self.profile.skip_irreversibility_check:
            ctx["_skip_iit03"] = True
        if "GDA-01" in ALL_GATES:
            ctx["_gap_floor"] = self.profile.gap_density_floor

        for gid, cls in ALL_GATES.items():
            if (gid == "SVT-03" and ctx.get("_skip_svt03")) or (
                gid == "IIT-03" and ctx.get("_skip_iit03")
            ):
                continue
            gate = cls()
            # 结构适用性门禁：缺跨章上下文字段时跳过（不误报）
            missing = _missing_structural_fields(gid, ctx)
            if missing:
                report.add(
                    GateResult(
                        gate_id=gid,
                        name=gate.name,
                        severity=gate.severity,
                        passed=True,
                        message=f"SKIPPED — 结构门禁需跨章数据（缺: {', '.join(missing[:3])}），本章节不计入",
                    )
                )
                report.gate_results[-1].skipped = True
                continue
            # 进度门禁：章节数不足时跳过（"第三章必须有爽点"在首章不适用）
            if _missing_progression(gid, ctx):
                report.add(
                    GateResult(
                        gate_id=gid,
                        name=gate.name,
                        severity=gate.severity,
                        passed=True,
                        message=f"SKIPPED — 该门禁需至少第{PROGRESSION_GATES[gid] + 1}章上下文，当前第{int(ctx.get('chapter_index', 0)) + 1}章不计入",
                    )
                )
                report.gate_results[-1].skipped = True
                continue
            try:
                result = self.safe_eval(gate, ctx)
            except Exception as e:
                result = GateResult(
                    gate_id=gid,
                    name=gate.name,
                    severity=gate.severity,
                    passed=False,
                    message=f"evaluation error: {e}",
                )
            report.add(result)
        return report

    def summarize(self, report: AuditReport) -> dict:
        all_gates = report.gate_results
        passed = sum(1 for r in all_gates if r.passed and not r.skipped)
        skipped = sum(1 for r in all_gates if r.skipped)
        blocked = sum(
            1 for r in all_gates if not r.passed and not r.skipped and r.severity.value == "block"
        )
        return {"total": len(all_gates), "passed": passed, "blocked": blocked, "skipped": skipped}


pipeline = AuditPipeline()
