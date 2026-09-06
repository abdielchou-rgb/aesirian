"""双向约束传播 = 提案制（FOUR_CARD_PLAN.md §2）

铁律：永不静默改写。AI 的任何联动修改都以 Diff 浮出，作者「接受/拒绝/保留冲突」。

本模块提供：
1. Diff / CardEdit 数据类型与传播方向表（PROPAGATION_TABLE）
2. forward_derive —— 阶段 A：试样故事 → 四卡（LLM 增强 + 纯规则离线降级）
3. propose_diff  —— 阶段 B：编辑任意卡 → diff 提案列表（规则驱动基座）

LLM 不可用时全部优雅降级为规则驱动，沿用项目「纯规则优先，LLM 增强」原则。
"""

from __future__ import annotations

import re
import uuid
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # 仅类型标注用；运行时在函数内延迟导入避免循环依赖
    from core.four_cards import FourCardProject

# ═══════════════════════════════════════════
# §2 数据类型
# ═══════════════════════════════════════════


class DiffStatus(str, Enum):  # noqa: UP042  # StrEnum 需 3.11+，CI 矩阵含 3.10
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONFLICTED = "conflicted"


class Diff(BaseModel):
    """一条待作者批准的联动修改提案。"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    target_card: str = Field(description="哪张卡要改：biographies/framework/chapters/sample")
    field: str = Field(description="改哪个字段，如 lie / goal / summary / text")
    before: str = Field(default="", description="修改前内容")
    after: str = Field(default="", description="修改后内容")
    rationale: str = Field(default="", description="为什么（来自 want/wound/lie 因果链）")
    source_card: str = Field(default="", description="因哪张卡的改动触发")
    status: DiffStatus = DiffStatus.PENDING

    @property
    def is_pending(self) -> bool:
        return self.status == DiffStatus.PENDING

    def accept(self) -> Diff:
        self.status = DiffStatus.ACCEPTED
        return self

    def reject(self) -> Diff:
        self.status = DiffStatus.REJECTED
        return self

    def mark_conflicted(self) -> Diff:
        self.status = DiffStatus.CONFLICTED
        return self


class CardEdit(BaseModel):
    """捕获用户在某张卡上的编辑。card 取值见 PROPAGATION_TABLE 键。"""

    card: str = Field(description="被编辑的卡：biographies/framework/chapters/sample")
    index: int | None = Field(default=None, description="list 卡内的目标下标；缺省=整卡/首项")
    field: str = Field(default="", description="被改字段名，如 lie / goal / summary / text")
    before: str = Field(default="", description="编辑前内容")
    after: str = Field(default="", description="编辑后内容")


# ─── §2 优先级表（回答"改一处，该改谁"）───

PROPAGATION_TABLE: dict[str, dict] = {
    "biographies": {  # 锚
        "targets": ["framework", "chapters", "sample"],
        "needs_confirmation": True,
        "level": "anchor",
        "label": "人物小传(锚)",
    },
    "framework": {
        "targets": ["chapters"],
        "needs_confirmation": True,
        "level": "normal",
        "label": "框架",
    },
    "chapters": {
        "targets": ["framework"],
        "needs_confirmation": True,
        "level": "normal",
        "label": "章节",
    },
    "sample": {
        "targets": ["biographies"],  # 反向
        "needs_confirmation": True,
        "level": "reverse",
        "label": "试样故事",
    },
}

CARD_LABELS = {
    "biographies": "人物小传",
    "framework": "框架",
    "chapters": "章节",
    "sample": "试样故事",
}

# ═══════════════════════════════════════════
# 规则驱动派生的文本启发式
# ═══════════════════════════════════════════

_POSITIVE_KWS = (
    "胜利",
    "发现",
    "成长",
    "获得",
    "成功",
    "和解",
    "突破",
    "救出",
    "夺回",
    "回到",
    "微笑",
    "握紧",
)
_NEGATIVE_KWS = (
    "失败",
    "损失",
    "打击",
    "失去",
    "背叛",
    "死亡",
    "崩溃",
    "误会",
    "遗弃",
    "抛弃",
    "伤口",
    "刀",
)

_TRAUMA_KWS = (
    "遗弃",
    "抛弃",
    "背叛",
    "失去",
    "死了",
    "被杀",
    "被骗",
    "被卖",
    "挨打",
    "丢下",
    "丢弃",
    "离开",
    "逃",
    "饿",
)
_TRAUMA_MARKERS = (
    "小时候",
    "那年",
    "当年",
    "曾经",
    "七岁",
    "八岁",
    "九岁",
    "幼年",
    "童年",
    "那天夜里",
)

_LIE_TEMPLATES = [
    (("背叛", "出卖", "骗"), "对人交心等于引刀自戕——先亮刀的人不会被捅"),
    (("遗弃", "抛弃", "丢下", "丢"), "不被需要的人终会被丢下，所以要抢先丢下别人"),
    (("失去", "死了", "被杀", "亡"), "留住任何东西都会再失去，不如从不伸手"),
    (("挨打", "打", "辱", "欺"), "软弱只会招来拳头，硬壳才是活路"),
]
_DEFAULT_LIE = "世上没有人会平白对自己好，先下手为强"

_CHANGE_TEMPLATE = "在故事高潮，他选择放下「{lie}」这条保命法则，把信任交给最不可能的那个人"
_CHANGE_DEFAULT = "在故事高潮，他面临守住法则或交付出真心之间的最后一搏"

_TENSION_SOURCES = ("目标冲突", "信念冲突", "戏剧反讽", "秘密暴露风险", "递归错位")
_TRAUMA_TO_TENSION = {
    "目标冲突": ("夺回", "找", "追", "抢", "复仇", "证明"),
    "信念冲突": ("骗", "背叛", "撒谎", "误会", "隐瞒"),
    "戏剧反讽": ("知道", "秘密", "真相", "发现", "认出"),
    "秘密暴露风险": ("秘密", "藏", "瞒", "暴露", "揭穿"),
    "递归错位": ("以为", "认为", "误会", "猜"),
}


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?…])", text)
    return [p.strip() for p in parts if p.strip()]


def _charge_of(sentence: str) -> str:
    """粗判句子价值电荷：positive / negative / neutral。"""
    pos = sum(1 for kw in _POSITIVE_KWS if kw in sentence)
    neg = sum(1 for kw in _NEGATIVE_KWS if kw in sentence)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _has_causal_marker(sentence: str) -> bool:
    return any(m in sentence for m in ("因为", "所以", "于是", "因此", "才", "导致", "逼得"))


def _extract_character_name(text: str) -> str:
    """取正文里首个 'XX说/想/走/看/问' 形态的 2-3 字人名；无则按视角代词兜底。"""
    m = re.search(r"([一-鿿]{2,3})(?:说|想|看|走|笑|哭|站|握|推|问|道|答|抬头|低头|转身)", text)
    if m:
        return m.group(1)
    if "她" in text and "他" not in text:
        return "她（女主视角）"
    return "他（男主视角）"


def _extract_want(text: str) -> str:
    m = re.search(r"(?:想|要|渴望|希望|必须|非得)(?:去|要)?([^，。；,!?]{2,24})", text)
    if m and len(m.group(1)) >= 2:
        return m.group(1).strip()
    m2 = re.search(r"为了([^，。；,!?]{2,30})", text)
    if m2:
        return "为了" + m2.group(1).strip()
    return "完成那件日夜压在心口的事（待作者校准）"


def _extract_wound(text: str) -> str:
    """抓创伤：优先带童年标记的句子，其次含创伤动词的片段。"""
    sents = _split_sentences(text)
    for s in sents:
        if any(mk in s for mk in _TRAUMA_MARKERS) and any(kw in s for kw in _TRAUMA_KWS):
            return s[:36]
    for s in sents:
        if any(kw in s for kw in _TRAUMA_KWS):
            return s[:36]
    return ""


def _derive_lie(wound: str, want: str) -> str:
    if not wound:
        return _DEFAULT_LIE
    for kws, template in _LIE_TEMPLATES:
        if any(k in wound for k in kws):
            return template
    return _DEFAULT_LIE


def _infer_tension(sentence: str) -> str:
    """把句子里的关键词映射到 tom_engine 的张力类型。"""
    for t, kws in _TRAUMA_TO_TENSION.items():
        if any(k in sentence for k in kws):
            return t
    return "目标冲突"


def _infer_voice_traits(text: str) -> list[str]:
    traits: list[str] = []
    sents = _split_sentences(text)
    if sents:
        avg_len = sum(len(s) for s in sents) / len(sents)
        if avg_len < 14:
            traits.append("短句克制")
        elif avg_len < 24:
            traits.append("中速叙事")
        else:
            traits.append("长句铺陈")
    if (
        sum(1 for s in sents if any(q in s for q in ("说", "道", "问", "答"))) / max(1, len(sents))
        > 0.3
    ):
        traits.append("对话驱动")
    sensory_hits = sum(1 for w in ("冷", "热", "光", "暗", "颜色", "声音", "香", "痛") if w in text)
    if sensory_hits >= 3:
        traits.append("感官细腻")
    if not traits:
        traits.append("待校准")
    return traits


def _default_framework_beats(
    want: str, lie: str, charge_turns: list[tuple[int, str]]
) -> list[dict]:
    """把文本中的正负电荷翻转压成框架 beats；不足 3 个用三段模板补齐。"""
    beats: list[dict] = []
    seen = 0
    for idx, turn in charge_turns:
        beats.append(
            {
                "index": idx,
                "goal": f"碾过主角的谎言：{lie}",
                "value_turn": turn,
                "tension_source": "信念冲突",
            }
        )
        seen += 1
    # 兜底三段模板：起因(负) → 深化(负) → 翻转(正)
    for _i, (goal_tpl, turn) in enumerate(
        (
            (f"把主角推进 want（{want}）与现状的裂缝", "正→负"),
            ("让 lie 以最痛的方式显形，逼主角重估代价", "负→负"),
            ("把主角逼到 change 临界点：守谎或交心", "负→正"),
        )
    ):
        if seen >= 3:
            break
        beats.append(
            {"index": seen + 1, "goal": goal_tpl, "value_turn": turn, "tension_source": "目标冲突"}
        )
        seen += 1
    return beats[:6]


# ═══════════════════════════════════════════
# 阶段 A：正向推导（试样故事 → 四卡）
# ═══════════════════════════════════════════


def _rule_forward_derive(sample_text: str):
    """纯规则离线版：无 LLM 时也能产出结构完整的四卡。"""
    from core.four_cards import (
        ChapterBeat,
        CharacterBiography,
        FourCardProject,
        FrameworkBeat,
        SampleStory,
    )

    text = sample_text.strip()
    name = _extract_character_name(text)
    want = _extract_want(text)
    wound = _extract_wound(text)
    lie = _derive_lie(wound, want)
    change = _CHANGE_TEMPLATE.format(lie=lie) if wound else _CHANGE_DEFAULT

    # 章节 beats：按句群切（≤6 句一组），标注价值翻转与因果链接
    sents = _split_sentences(text)
    chapters: list[ChapterBeat] = []
    buckets: list[list[str]] = []
    for s in sents:
        if not buckets or len(buckets[-1]) >= 6:
            buckets.append([])
        buckets[-1].append(s)
    for _i, bucket in enumerate(buckets, start=1):
        summary = " ".join(bucket)[:60]
        charge_turns = [
            _charge_of(bucket[j])
            for j in range(len(bucket))
            if j and _charge_of(bucket[j]) != _charge_of(bucket[j - 1])
        ]
        # 段内若正负混存则记一次翻转，否则按末句电荷定方向
        turn = "正→负" if not charge_turns else "负→正"
        if charge_turns and charge_turns[-1] == "positive":
            turn = "负→正"
        chapters.append(
            ChapterBeat(
                summary=summary,
                value_turn=turn,
                causally_linked=any(_has_causal_marker(s) for s in bucket),
            )
        )

    # 框架 beats：全篇电荷翻转点（句子级）→ 张力轨迹
    charge_turns_all: list[tuple[int, str]] = []
    prev_charge = _charge_of(sents[0]) if sents else "neutral"
    for j, s in enumerate(sents[1:], start=2):
        cur = _charge_of(s)
        if prev_charge != "neutral" and cur != "neutral" and cur != prev_charge:
            charge_turns_all.append(
                (j, f"{prev_charge}→{cur}".replace("positive", "正").replace("negative", "负"))
            )
        prev_charge = cur
    fw = _default_framework_beats(want, lie, charge_turns_all)
    framework = [FrameworkBeat(**b) for b in fw]

    # 用 reader_model 给试样打沉浸度分
    try:
        from core.reader_model import ReaderModelSimulator

        score = ReaderModelSimulator().evaluate_transportation(text).overall
    except Exception:
        score = 0.0

    return FourCardProject(
        biographies=[
            CharacterBiography(
                name=name,
                want=want,
                wound=wound,
                lie=lie,
                change=change,
                voice_traits=_infer_voice_traits(text),
            )
        ],
        framework=framework,
        chapters=chapters,
        sample=SampleStory(text=text, transportation_score=round(score, 1)),
    )


def _llm_forward_derive(sample_text: str):
    """LLM 版：pydantic_ai 一个多输出结构化调用，prompt 内置 Chain of Ask Why。"""
    try:  # 依赖缺失/环境异常一律降级到规则路径
        from pydantic_ai import Agent

        from core.four_cards import FourCardProject
        from core.pydantic_ai_engine import get_pydantic_ai_engine
    except Exception:
        return None

    engine = get_pydantic_ai_engine()
    if not engine.available():
        return None

    agent = Agent(
        engine._model,  # 复用 pydantic_ai 已配置模型
        output_type=FourCardProject,
        system_prompt=(
            "你是叙事结构分析师。从一段试样故事反推人物与结构，采用 Chain of Ask Why：\n"
            "1. 他想要什么（want，具体到失败可见）→ 2. 为什么想要（追溯到塑造性创伤 wound）→ "
            "3. 伤口让他信了什么错的（lie）→ 4. 高潮时放弃/死守这个谎（change）。\n"
            "框架 beats 每个标注 value_turn（正→负/负→正）与 tension_source（信念冲突/戏剧反讽/"
            "递归错位/秘密暴露风险/目标冲突）；章节 beats 标注 summary 与是否因果链接。\n"
            "只填能从文本证据支撑的内容；无法推断的字段留空或使用保守默认，禁止编造细节。"
        ),
    )
    try:
        result = agent.run_sync(f"试样故事：\n{sample_text}\n\n请输出四卡结构。")
        project: FourCardProject = result.output
        # 补上沉浸度评分（规则层保证非空）
        from core.reader_model import ReaderModelSimulator

        score = ReaderModelSimulator().evaluate_transportation(sample_text).overall
        project.sample.text = sample_text
        project.sample.transportation_score = round(score, 1)
    except Exception:
        return None
    else:
        return project


def forward_derive(sample_text: str):
    """阶段 A 主入口：LLM 增强，不可用/退化时规则降级。返回 FourCardProject。

    判定：仅当 LLM 结构化输出经 _drop_shell_biographies 后仍含 ≥1 个有效人物卡时才采纳，
    否则视为退化输出（空壳/空数组）并回落到规则路径，保证返回结构完整可用。
    """
    if not sample_text or not sample_text.strip():
        from core.four_cards import FourCardProject

        return FourCardProject.empty()
    project = _llm_forward_derive(sample_text)
    if project is not None:
        project = _drop_shell_biographies(project)
        if project.biographies:
            return project
    return _rule_forward_derive(sample_text)


def _drop_shell_biographies(project) -> FourCardProject:
    """收敛派生人物卡：剔除空壳角色（只有 name/voice 而无 want/wound/lie/change），
    且派生阶段聚焦核心主角（当前 UI/编辑入口为单主角形态；多角色演示由种子
    demo_luoyang_project.json 手工维护，不走 forward_derive）。"""
    filled = [
        b
        for b in project.biographies
        if (b.want or "").strip()
        or (b.wound or "").strip()
        or (b.lie or "").strip()
        or (b.change or "").strip()
    ]
    project.biographies = filled[:1]
    return project


# ═══════════════════════════════════════════
# 阶段 B：反向提案（编辑任意卡 → diff）
# ═══════════════════════════════════════════


def _edit_field_label(card: str, field: str) -> str:
    """把 {card}.{field} 转成人类可读的卡片字段说明。"""
    card_label = CARD_LABELS.get(card, card)
    field_label = {
        "name": "角色名",
        "want": "欲望 want",
        "wound": "创伤 wound",
        "lie": "错误信念 lie",
        "change": "转变 change",
        "goal": "张力目标 goal",
        "value_turn": "价值翻转 value_turn",
        "tension_source": "张力来源",
        "summary": "剧情摘要",
        "text": "正文",
        "voice_traits": "口吻标记",
    }.get(field, field)
    return f"{card_label}·{field_label}"


def _rule_propose_diff(edit: CardEdit, project) -> list[Diff]:
    """规则驱动反向提案：按传播方向表生成可落地的 diff（离线可用）。"""
    rule = PROPAGATION_TABLE.get(edit.card)
    if not rule:
        return []
    diffs: list[Diff] = []

    def make(target: str, field: str, after: str, rationale: str) -> None:
        diffs.append(
            Diff(
                target_card=target,
                field=field,
                before=edit.after if False else "",
                after=after,
                rationale=rationale,
                source_card=edit.card,
            )
        )

    # 找出（可能多个人物中）受影响的锚：缺省取首个 biography
    bio = None
    if project.biographies:
        bio = (
            project.biographies[edit.index]
            if edit.index is not None and edit.index < len(project.biographies)
            else project.biographies[0]
        )

    if edit.card == "biographies" and bio is not None:
        # 锚级变更：全量重算框架 + 章节 + 试样
        if edit.field in ("lie", "wound", "want"):
            rationale = (
                f"人物小传·{edit.field} 变更触发锚级重算："
                f"lie/wound/want 因果链变化将改变每个张力 beat 要碾过的对象。"
            )
            for i, _beat in enumerate(project.framework):
                if i < 3:
                    make(
                        "framework",
                        "goal",
                        f"碾过主角更新后的谎言：{bio.lie or edit.after}",
                        rationale,
                    )
            make(
                "chapters",
                "summary",
                "（建议）重排章节翻转：让 lie 的新版本以更痛的方式显形",
                rationale,
            )
            make(
                "sample",
                "text",
                f"（建议）改写试样场景：把主角放进 want「{bio.want or edit.after}」与 lie「{bio.lie or edit.after}」碰撞的处境",
                rationale,
            )
        elif edit.field == "name":
            for i, _beat in enumerate(project.framework):
                if i < 2:
                    make(
                        "framework",
                        "goal",
                        f"{edit.after}碾过主角的谎言：{bio.lie}",
                        f"角色名更新为「{edit.after}」，同步框架 beat 主语。",
                    )

    elif edit.card == "framework":
        # 框架被改 → 提案改章节（张力轨迹变化影响翻转快照）
        make(
            "chapters",
            "value_turn",
            edit.after or "负→正",
            f"框架 beat 的张力轨迹改为「{_edit_field_label('framework', edit.field)}」，"
            f"对应章节的价值翻转快照需对齐。",
        )

    elif edit.card == "chapters":
        # 章节被改 → 提案改框架
        make(
            "framework",
            "goal",
            f"（建议）该章张力目标改为匹配新剧情：{edit.after or edit.before}",
            "章节剧情变更改变了该处实际碾过的 wound/lie，框架张力目标需对齐。",
        )

    elif edit.card == "sample" and bio is not None:
        # 试样故事被改 → 反向提案改小传（want/wound/lie 校准）
        make(
            "biographies",
            "want",
            f"（建议校准）{edit.after or '试样呈现的新欲望'}",
            "试样故事改了，说明 pilot 验证出的 want 与人物小传锚不一致，需校准。",
        )
    return diffs


def _llm_propose_diff(edit: CardEdit, project) -> list[Diff] | None:
    """LLM 增强：让模型产出各目标卡的 after 候选（复用 generate_variant）。"""
    try:
        from core.pydantic_ai_engine import get_pydantic_ai_engine
    except Exception:
        return None

    engine = get_pydantic_ai_engine()
    if not engine.available():
        return None
    rule = PROPAGATION_TABLE.get(edit.card)
    if not rule:
        return None

    context = (
        f"当前四卡项目摘要：\n"
        f"{project.model_dump_json()}\n\n"
        f"作者编辑了 {CARD_LABELS.get(edit.card)} 的 {edit.field}: "
        f"{edit.before!r} → {edit.after!r}。"
    )
    instruction = (
        f"请按传播方向 {rule['targets']} 给出其余卡片应如何修改的 JSON 数组，"
        f"每项 {{target_card, field, before, after, rationale}}。"
        f"只输出 JSON。"
    )
    raw = engine.generate_variant(context, instruction, word_target=300, temperature=0.4)
    if not raw:
        return None
    import json

    try:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return None
        items = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    diffs = []
    for it in items:
        if not isinstance(it, dict) or "target_card" not in it:
            continue
        diffs.append(
            Diff(
                target_card=str(it.get("target_card", "")),
                field=str(it.get("field", "")),
                before=str(it.get("before", "")),
                after=str(it.get("after", "")),
                rationale=str(it.get("rationale", "")),
                source_card=edit.card,
            )
        )
    return diffs or None


def propose_diff(edit: CardEdit, project) -> list[Diff]:
    """阶段 B 主入口：捕获编辑 → 按传播方向表生成 diff。作者批准才落地。"""
    rule = PROPAGATION_TABLE.get(edit.card)
    if not rule:
        return []
    llm_diffs = _llm_propose_diff(edit, project)
    diffs = llm_diffs if llm_diffs is not None else _rule_propose_diff(edit, project)
    for d in diffs:
        project.add_diff(d)
    return diffs


def apply_diff(project, diff_id: str, accept: bool = True) -> bool:
    """作者裁决：接受则把 after 应用到对应卡；拒绝则标 rejected。"""
    for d in project.pending_diffs:
        if d.id != diff_id:
            continue
        if accept and d.status == DiffStatus.PENDING:
            _apply_one(project, d)
            d.accept()
        elif not accept:
            d.reject()
        return True
    return False


def _apply_one(project, diff: Diff) -> None:
    """把单条 diff 的 after 写进目标卡（仅接受路径调用）。"""
    if diff.target_card == "biographies":
        target = project.biographies
    elif diff.target_card == "framework":
        target = project.framework
    elif diff.target_card == "chapters":
        target = project.chapters
    elif diff.target_card == "sample":
        # sample 是单对象
        if hasattr(project.sample, diff.field):
            setattr(project.sample, diff.field, diff.after)
        return
    else:
        return
    if target and hasattr(target[0], diff.field):
        setattr(target[0], diff.field, diff.after)
    # diff.field 为空时视为整卡替换提示，不落地
