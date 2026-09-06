"""文鉴门禁组 — 知识库补全: Dramatica / Lisa Cron / Truby道德论战 / 十章法则 G10 / 好莱坞加点 / 网文断章类型。

基于 skill_package/wenjian/craft/ 下 7 个知识库文档的缺口分析，全部零 API Key，纯启发式。
"""

from __future__ import annotations

import re

from wenjian.models import GateResult, GateSeverity

from .base import BaseGate

# ═══════════════════════════════════════════════════════════
#  Dramatica 四维结构 (dramatica-four-dimensions-zh.md)
# ═══════════════════════════════════════════════════════════


class DRM01_FourDomainDiagnosis(BaseGate):
    """Dramatica 四维故事结构诊断：检测故事主要发生在哪个域（外部行动/内部心智/社会关系/抽象理念），
    以及是否缺少必要域。"""

    gate_id = "DRM-01"
    name = "Dramatica 四维结构诊断"
    description = "好故事在4个域（外部行动/内部心智/社会关系/抽象理念）中至少激活2个"
    severity = GateSeverity.WARN

    DOMAIN_KEYWORDS = {
        "objective_plot": [
            "行动",
            "战斗",
            "追",
            "逃",
            "闯",
            "破",
            "杀",
            "攻",
            "守",
            "闯关",
            "任务",
        ],
        "subjective_mind": ["迷茫", "怀疑", "回忆", "思考", "内心", "挣扎", "决定", "选择", "觉悟"],
        "relationship": ["信任", "背叛", "依赖", "背离", "和解", "联盟", "敌对", "关系"],
        "symbolism": ["象征", "寓意", "宿命", "命运", "因果", "轮回", "天道", "法则"],
    }

    def evaluate(self, chapter_text: str = "", domain_tags: list = None) -> GateResult:
        if domain_tags:
            active = len(domain_tags)
        else:
            text = chapter_text or ""
            active = 0
            found = {}
            for domain, keywords in self.DOMAIN_KEYWORDS.items():
                hits = sum(text.count(kw) for kw in keywords)
                if hits >= 3:
                    active += 1
                    found[domain] = hits
        if active < 2:
            domains_found = list(found.keys()) if "found" in dir() else (domain_tags or [])
            return self.fail_result(
                message=f"仅激活 {active}/4 个 Dramatica 域（建议≥2）—当前域: {domains_found or '无'}",
                details={"active_domains": active, "domains_found": domains_found},
            )
        return self.pass_result(details={"active_domains": active})


class DRM02_LogicContradiction(BaseGate):
    """Dramatica 逻辑矛盾诊断：Problem 是否在终幕被 Solution 解决？解决是否逻辑一致？"""

    gate_id = "DRM-02"
    name = "Dramatica 逻辑矛盾诊断"
    description = (
        "核心问题（Problem）是否在终幕被对应的解决方案（Solution）解决，中间逻辑链是否一致"
    )
    severity = GateSeverity.BLOCK

    def evaluate(
        self, problem_stated: bool = False, solution_applied: bool = False, position_pct: float = 0
    ) -> GateResult:
        if position_pct < 80:
            return self.pass_result(message="未到终幕，暂不评估")
        if problem_stated and not solution_applied:
            return self.fail_result(
                message="终幕已到但核心问题未被解决—Dramatica逻辑矛盾",
                details={"problem_stated": problem_stated, "solution_applied": solution_applied},
            )
        return self.pass_result()


# ═══════════════════════════════════════════════════════════
# 好莱坞大师技法补充 · hollywood-master-techniques-zh.md
# ═══════════════════════════════════════════════════════════


class HOL01_MidpointType(BaseGate):
    """中点类型检测：伪胜利中点 vs 伪失败中点。IIT-04 只检测位置，本门禁检测类型。"""

    gate_id = "HOL-01"
    name = "中点类型门禁"
    description = "中点应是伪胜利（主角以为赢了实则不然）或伪失败（主角以为输了实则关键线索到手）"
    severity = GateSeverity.WARN

    FALSE_VICTORY_SIGNALS = ["以为", "看似", "似乎赢了", "表面上"]
    FALSE_DEFEAT_SIGNALS = ["却不知", "没想到", "阴差阳错", "因祸得福", "转机"]

    def evaluate(self, chapter_text: str = "", position_pct: float = 0) -> GateResult:
        if position_pct < 40 or position_pct > 60:
            return self.pass_result(message="不在中点范围")
        text = chapter_text or ""
        has_victory = any(s in text for s in self.FALSE_VICTORY_SIGNALS)
        has_defeat = any(s in text for s in self.FALSE_DEFEAT_SIGNALS)
        if not has_victory and not has_defeat:
            return self.fail_result(
                message="中点位置缺少伪胜利或伪失败信号—中点转折意图不明确",
                details={"has_false_victory": has_victory, "has_false_defeat": has_defeat},
            )
        midpoint_type = "false_victory" if has_victory else "false_defeat"
        return self.pass_result(details={"midpoint_type": midpoint_type})


# ═══════════════════════════════════════════════════════════
#  Lisa Cron 神经科学 (lisa-cron-neuroscience-zh.md)
# ═══════════════════════════════════════════════════════════


class NEU01_StakePresence(BaseGate):
    """读者大脑在问：这事威胁到我了吗？主角必须有立刻失去的东西。赌注必须在第一页建立。"""

    gate_id = "NEU-01"
    name = "赌注存在门禁"
    description = "Lisa Cron: 读者在第一页就在问'主角会失去什么'—每场景需有明确赌注"
    severity = GateSeverity.WARN

    STAKE_KEYWORDS = [
        "失去",
        "代价",
        "赌上",
        "押上",
        "冒险",
        "拼命",
        "豁出去",
        "不成功便",
        "唯一机会",
        "最后一次",
        "命悬",
        "生死",
        "存亡",
        "毁灭",
        "覆灭",
        "倾家",
        "身败名裂",
        "万劫不复",
        "回不了头",
        "没有退路",
    ]

    def evaluate(self, chapter_text: str = "") -> GateResult:
        text = chapter_text or ""
        stake_hits = sum(text.count(kw) for kw in self.STAKE_KEYWORDS)
        if stake_hits == 0:
            return self.fail_result(
                message="场景缺少赌注信号—读者不知道主角可能失去什么", details={"stake_hits": 0}
            )
        return self.pass_result(details={"stake_hits": stake_hits})


class NEU02_EmpathyTrigger(BaseGate):
    """他跟我一样吗？主角的困境必须是读者能代入的'普遍困境'。"""

    gate_id = "NEU-02"
    name = "共情触发门禁"
    description = "Lisa Cron: 读者代入靠普遍困境—困境太特殊读者不关心，太普通读者觉得无聊"
    severity = GateSeverity.WARN

    UNIVERSAL_DILEMMAS = {
        "生存": ["活命", "活下去", "饥饿", "贫困", "绝境", "无路可走", "末日"],
        "归属": ["被排斥", "不被接受", "孤独", "无人理解", "格格不入", "异类"],
        "尊严": ["侮辱", "看不起", "轻视", "嘲笑", "践踏", "羞辱"],
        "爱": ["失去", "分离", "误会", "错过", "背叛", "辜负"],
        "公正": ["冤枉", "诬陷", "不公", "迫害", "打压", "冤屈"],
        "自由": ["囚禁", "束缚", "身不由己", "被控制", "没有选择"],
    }

    def evaluate(self, chapter_text: str = "") -> GateResult:
        text = chapter_text or ""
        found_dilemmas = {}
        for category, keywords in self.UNIVERSAL_DILEMMAS.items():
            hits = sum(text.count(kw) for kw in keywords)
            if hits > 0:
                found_dilemmas[category] = hits
        if not found_dilemmas:
            return self.fail_result(
                message="未检测到普遍困境信号—读者可能难以共情", details={"dilemmas_found": "无"}
            )
        top = max(found_dilemmas, key=lambda c: found_dilemmas[c])
        return self.pass_result(
            details={"dilemmas_found": list(found_dilemmas.keys()), "primary": top}
        )


class NEU03_ExpectedSurprise(BaseGate):
    """接下来会怎样？读者喜欢被意外，但必须在意外后觉得'原来如此'。每2-3页必须有一个'小预期偏差'。"""

    gate_id = "NEU-03"
    name = "预期偏差必然感门禁"
    description = "Lisa Cron: 读者喜欢'没想到但合理'的转折—意外必须事后觉得必然"
    severity = GateSeverity.WARN

    SURPRISE_SIGNALS = ["没想到", "竟", "原来", "却", "不料", "谁知", "谁曾想", "没想到的是"]
    INEVITABLE_SIGNALS = ["难怪", "原来如此", "怪不得", "果然", "早该想到", "原来是因为"]

    def evaluate(self, chapter_text: str = "") -> GateResult:
        text = chapter_text or ""
        surprise_count = sum(text.count(s) for s in self.SURPRISE_SIGNALS)
        inevitable_count = sum(text.count(s) for s in self.INEVITABLE_SIGNALS)
        char_count = len(text) or 1
        density = surprise_count / max(char_count / 1000, 1)

        if char_count > 500 and surprise_count == 0:
            return self.fail_result(
                message="章节无预期偏差—读者全程可预测，容易失去兴趣",
                details={"surprise_count": 0, "density_per_1k": 0},
            )
        if surprise_count > 0 and inevitable_count == 0:
            return self.fail_result(
                message=f"有 {surprise_count} 处意外但无'原来如此'—意外缺少必然感",
                details={"surprise_count": surprise_count, "inevitable_count": 0},
            )
        return self.pass_result(
            details={
                "surprise_count": surprise_count,
                "inevitable_count": inevitable_count,
                "density_per_1k": round(density, 1),
            }
        )


# ═══════════════════════════════════════════════════════════
#  Truby 道德论战 (truby-22-step-zh.md)
# ═══════════════════════════════════════════════════════════


class TRB01_MoralArgument(BaseGate):
    """Truby核心：故事不是主角成长，是主角的道德论战—纠结→选择→付出代价→揭示。"""

    gate_id = "TRB-01"
    name = "道德论战门禁"
    description = "Truby: 主角必须在道德层面纠结→做出选择→付出代价→实现自我揭示"
    severity = GateSeverity.WARN

    MORAL_STRUGGLE = ["纠结", "挣扎", "两难", "左右为难", "犹豫", "徘徊", "矛盾", "进退两难"]
    MORAL_CHOICE = ["决定", "选择", "最终", "下定决心", "豁出去", "拼了", "赌一把", "走向"]
    MORAL_COST = ["代价", "失去", "牺牲", "放弃", "承受", "背负", "付出", "换来"]
    MORAL_REVEAL = ["明白", "终于懂了", "醒悟", "顿悟", "意识到", "发现原来", "原来是"]

    def evaluate(self, chapter_text: str = "", position_pct: float = 0) -> GateResult:
        text = chapter_text or ""
        struggle = sum(text.count(kw) for kw in self.MORAL_STRUGGLE)
        choice = sum(text.count(kw) for kw in self.MORAL_CHOICE)
        cost = sum(text.count(kw) for kw in self.MORAL_COST)
        reveal = sum(text.count(kw) for kw in self.MORAL_REVEAL)

        has_arc = bool(struggle and choice)
        has_cost = bool(cost)
        has_reveal = bool(reveal)

        if position_pct > 50 and not has_arc:
            return self.fail_result(
                message="章节缺少道德论战弧线（纠结→选择）—Truby认为这是故事的核心驱动力",
                details={
                    "moral_struggle": struggle,
                    "moral_choice": choice,
                    "moral_cost": cost,
                    "moral_reveal": reveal,
                },
            )
        if position_pct > 75 and not has_cost:
            return self.fail_result(
                message="主角做出了选择但未付出代价—Truby: 选择必须有代价才有意义",
                details={"moral_struggle": struggle, "moral_choice": choice, "moral_cost": 0},
            )
        return self.pass_result(
            details={
                "arc_complete": has_arc and has_cost and has_reveal,
                "stage": "reveal"
                if has_reveal
                else ("cost" if has_cost else ("choice" if choice else "struggle")),
            }
        )


# ═══════════════════════════════════════════════════════════
# 网文断章类型 · webnovel-master-craft-zh.md
# ═══════════════════════════════════════════════════════════


class WNM01_BreakTypeCategory(BaseGate):
    """6种大师级断章位置的具体分类检测。BRK-04B检测有无信号，本门禁检测具体是哪种。"""

    gate_id = "WNM-01"
    name = "断章类型分类门禁"
    description = "大师有6种断章：后果/发现/决定/危机/悬念/转折前。检测具体使用的是哪种"
    severity = GateSeverity.WARN

    BREAK_PATTERNS = {
        "后果断章": [r"缓缓倒下", r"消息传遍", r"传开了", r"轰动了", r"震惊了"],
        "发现断章": [r"里面是[—…]", r"竟然是", r"赫然是", r"原来是"],
        "决定断章": [r"我要去[。！]", r"抬起头", r"决定了", r"必须去"],
        "危机断章": [r"来不及了", r"身后.*门.*踢开", r"逼近", r"追上了"],
        "悬念断章": [r"谁派你来的", r"为什么", r"到底是谁", r"怎么能"],
        "转折前断章": [r"有件事你.*不知道", r"一直瞒着", r"其实", r"真相是"],
    }

    def evaluate(self, chapter_text: str = "") -> GateResult:
        text = chapter_text or ""
        if len(text) < 200:
            return self.pass_result(message="文本太短")
        last_400 = text[-400:]
        types_found = {}
        for break_type, patterns in self.BREAK_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, last_400):
                    types_found[break_type] = True
                    break
        if not types_found:
            return self.fail_result(
                message="章末400字未识别出任何大师断章类型—建议使用6种之一（后果/发现/决定/危机/悬念/转折前）",
                details={"types_found": []},
            )
        best_type = list(types_found.keys())[0]
        return self.pass_result(
            details={
                "types_found": list(types_found.keys()),
                "best_type": best_type,
                "recommendation": f"已检测到 '{best_type}' 型断章",
            }
        )


# ═══════════════════════════════════════════════════════════
#  G10 十章法则 (webnovel-ten-chapter-law-zh.md)
# ═══════════════════════════════════════════════════════════


class G10_04_WorldExpansion(BaseGate):
    """第4章必须有世界观展开—让读者对世界有感知。缺失则读者像在空白空间里读故事。"""

    gate_id = "G10-04"
    name = "第四章世界观门禁"
    description = "十章法则第4条：第4章必须展开世界观，让读者对故事世界有感知"
    severity = GateSeverity.WARN

    WORLD_KEYWORDS = [
        "世界",
        "大陆",
        "宗门",
        "帝国",
        "王朝",
        "势力",
        "规则",
        "体系",
        "等级",
        "境界",
        "修炼",
        "灵力",
        "魔法",
        "科技",
        "系统",
        "法则",
        "天道",
        "传承",
        "历史",
        "传说",
        "远古",
        "千年",
        "万年前",
        "由来",
        "起源",
    ]

    def evaluate(self, chapter_index: int = 0, chapter_text: str = "") -> GateResult:
        if chapter_index != 4:
            return self.pass_result(message=f"当前第{chapter_index}章，非第4章")
        text = chapter_text or ""
        world_hits = sum(text.count(kw) for kw in self.WORLD_KEYWORDS)
        if world_hits < 5:
            return self.fail_result(
                message=f"第4章世界观展开不足（仅{world_hits}个世界构建词）—读者仍对世界无感知",
                details={"chapter": chapter_index, "world_keyword_hits": world_hits},
            )
        return self.pass_result(details={"world_keyword_hits": world_hits})


class G10_05_FirstMiniClimax(BaseGate):
    """第5章必须有第一次小高潮。前半段无事件高潮，读者失去耐心流失。"""

    gate_id = "G10-05"
    name = "第五章小高潮门禁"
    description = "十章法则第5条：第5章必须出现第一次小高潮"
    severity = GateSeverity.WARN

    CLIMAX_SIGNALS = [
        "爆发",
        "对决",
        "决战",
        "反击",
        "逆袭",
        "翻盘",
        "突破",
        "晋级",
        "揭晓",
        "转折",
    ]

    def evaluate(
        self, chapter_index: int = 0, gap_density: float = 0, climax_signals: int = 0
    ) -> GateResult:
        if chapter_index != 5:
            return self.pass_result(message=f"当前第{chapter_index}章，非第5章")
        score = max(gap_density, 0) + climax_signals
        if score < 2:
            return self.fail_result(
                message="第5章缺少小高潮信号—读者可能在1/2处失去耐心",
                details={
                    "chapter": chapter_index,
                    "gap_density": gap_density,
                    "climax_signals": climax_signals,
                },
            )
        return self.pass_result(details={"climax_score": score})


class G10_07_ProactiveAction(BaseGate):
    """第7章：主角第一次主动行动。一直被动会让读者失望。"""

    gate_id = "G10-07"
    name = "第七章主动行动门禁"
    description = "十章法则第7条：第7章主角应第一次主动推动剧情，而非一直被事件推着走"
    severity = GateSeverity.WARN

    PROACTIVE_SIGNALS = [
        "决定",
        "主动",
        "亲自",
        "独自",
        "暗中",
        "悄悄",
        "秘密",
        "计划",
        "布局",
        "我要",
        "我去",
        "我来",
        "出手",
        "行动",
        "出发",
        "上路",
        "启程",
    ]

    def evaluate(
        self, chapter_index: int = 0, chapter_text: str = "", proactivity_score: float = 0
    ) -> GateResult:
        if chapter_index != 7:
            return self.pass_result(message=f"当前第{chapter_index}章，非第7章")
        text = chapter_text or ""
        hits = sum(text.count(s) for s in self.PROACTIVE_SIGNALS) + int(proactivity_score * 5)
        if hits < 3:
            return self.fail_result(
                message=f"第7章缺少主动行动信号（仅{hits}个）—主角一直被动会让读者失望",
                details={"chapter": chapter_index, "proactive_hits": hits},
            )
        return self.pass_result(details={"proactive_hits": hits})


class G10_08_OpponentIntro(BaseGate):
    """第8章：对手正式登场。没有对手则无张力。"""

    gate_id = "G10-08"
    name = "第八章对手登场门禁"
    description = "十章法则第8条：第8章对手必须正式登场，没有对手=没有张力"
    severity = GateSeverity.WARN

    OPPONENT_SIGNALS = [
        "对手",
        "敌人",
        "宿敌",
        "反派",
        "仇人",
        "对头",
        "死对头",
        "劲敌",
        "挑衅",
        "针对",
        "为难",
        "阻挠",
        "设局",
        "埋伏",
        "截杀",
        "追杀",
    ]

    def evaluate(
        self, chapter_index: int = 0, chapter_text: str = "", opponent_present: bool = False
    ) -> GateResult:
        if chapter_index != 8:
            return self.pass_result(message=f"当前第{chapter_index}章，非第8章")
        if opponent_present:
            return self.pass_result(details={"opponent_detected": True})
        text = chapter_text or ""
        hits = sum(text.count(s) for s in self.OPPONENT_SIGNALS)
        if hits < 2:
            return self.fail_result(
                message="第8章对手未正式登场—无对手则无张力，读者失去方向",
                details={"chapter": chapter_index, "opponent_hits": hits},
            )
        return self.pass_result(details={"opponent_hits": hits})


class G10_09_FirstFailure(BaseGate):
    """第9章：主角第一次失败/挫折。一直赢会让读者觉得无聊。"""

    gate_id = "G10-09"
    name = "第九章挫折门禁"
    description = "十章法则第9条：第9章主角应遭遇第一次失败或挫折，一直赢=无聊"
    severity = GateSeverity.WARN

    FAILURE_SIGNALS = [
        "失败",
        "落败",
        "不敌",
        "惨败",
        "受挫",
        "遭遇",
        "陷阱",
        "中计",
        "受伤",
        "重伤",
        "昏迷",
        "濒死",
        "被困",
        "包围",
        "无力",
        "绝望",
        "损失",
        "丢失",
        "被夺",
        "败退",
        "撤退",
        "逃走",
        "逃跑",
    ]

    def evaluate(
        self, chapter_index: int = 0, chapter_text: str = "", failure_detected: bool = False
    ) -> GateResult:
        if chapter_index != 9:
            return self.pass_result(message=f"当前第{chapter_index}章，非第9章")
        if failure_detected:
            return self.pass_result(details={"failure_detected": True})
        text = chapter_text or ""
        hits = sum(text.count(s) for s in self.FAILURE_SIGNALS)
        if hits < 2:
            return self.fail_result(
                message="第9章缺少失败/挫折信号—主角一直赢会让读者觉得无聊",
                details={"chapter": chapter_index, "failure_hits": hits},
            )
        return self.pass_result(details={"failure_hits": hits})


class G10_10_FirstUpgrade(BaseGate):
    """第10章：第一次升级/突破。前10章无成长，读者弃书。"""

    gate_id = "G10-10"
    name = "第十章首次升级门禁"
    description = "十章法则第10条：第10章主角应完成第一次升级/突破，前10章无成长=读者弃书"
    severity = GateSeverity.WARN

    UPGRADE_SIGNALS = [
        "突破",
        "晋级",
        "升级",
        "进阶",
        "突破瓶颈",
        "顿悟",
        "觉醒",
        "领悟",
        "获得",
        "掌握",
        "学会",
        "练成",
        "修成",
        "突破桎梏",
        "脱胎换骨",
    ]

    def evaluate(
        self, chapter_index: int = 0, chapter_text: str = "", upgrade_detected: bool = False
    ) -> GateResult:
        if chapter_index != 10:
            return self.pass_result(message=f"当前第{chapter_index}章，非第10章")
        if upgrade_detected:
            return self.pass_result(details={"upgrade_detected": True})
        text = chapter_text or ""
        hits = sum(text.count(s) for s in self.UPGRADE_SIGNALS)
        if hits < 2:
            return self.fail_result(
                message="第10章缺少升级/突破信号—前10章无成长，读者可能弃书",
                details={"chapter": chapter_index, "upgrade_hits": hits},
            )
        return self.pass_result(details={"upgrade_hits": hits})
