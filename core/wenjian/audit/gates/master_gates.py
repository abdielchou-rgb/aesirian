"""文鉴门禁组扩展 — 大师技法：中点、一无所有、主题证明、B故事、对手网、勾子散布、注水比、断章定位、升级节奏、邪恶力量揭示。

每个门禁都基于 craft/*.md 知识库理论，嵌入可比量化的启发式。全部零 API Key。
"""

from __future__ import annotations
import re
from .base import BaseGate
from wenjian.models import GateResult, GateSeverity

# ─── 有用的辅助函数 ─────────────────────────────────

HOOK_KEYWORDS = ["突然","但是","然而","没想到","却发现","竟","原来","为什么","怎么回事","来不及","有件事","你知"]
HOOK_TAGS = ["来不及","发现","决定","危机","悬念","转折"]

def _hook_density(text: str) -> float:
    """每千字勾子密度"""
    count = sum(text.count(h) for h in HOOK_KEYWORDS)
    return count / max(len(text) / 1000, 1)

def _hook_distribution(text: str) -> list[dict]:
    """将文本分为 5 段，每段返回勾子信息"""
    seg_len = max(len(text) // 5, 1)
    segs = []
    for i in range(5):
        seg = text[i*seg_len:(i+1)*seg_len]
        segs.append({
            "segment": i+1,
            "start_char": i*seg_len,
            "hook_count": sum(seg.count(h) for h in HOOK_KEYWORDS),
            "tags_found": [t for t in HOOK_TAGS if t in seg],
        })
    return segs

def _segment_overlap(a: str, b: str) -> float:
    """两段文本的信息重叠度"""
    # 提取实义词
    reals_a = set(re.findall(r'[一-鿿]{2,}', a))
    reals_b = set(re.findall(r'[一-鿿]{2,}', b))
    if not reals_a or not reals_b:
        return 0
    intersection = reals_a & reals_b
    return len(intersection) / max(len(reals_a | reals_b), 1)


# ─── 勾子散布 ────────────────────────────────────────

class BRK01B_HookDistribution(BaseGate):
    gate_id = "BRK-01B"
    name = "勾子散布门禁"
    description = "好的章节在前中后都有勾子，不是只在章末"
    severity = GateSeverity.WARN

    def evaluate(self, text: str = "") -> GateResult:
        if len(text) < 300: return self.pass_result(message="文本太短")
        segs = _hook_distribution(text)
        empty_segs = [s for s in segs if s["hook_count"] == 0]
        longest_empty = 0
        if empty_segs:
            for s in empty_segs:
                l = s["start_char"]
                if l > longest_empty: longest_empty = l

        worst_hook_gap = (longest_empty + len(text)//5) if longest_empty > 0 else 0
        details = {"segments": segs, "worst_gap_chars": worst_hook_gap}

        if len(empty_segs) >= 2:
            return self.fail_result(message=f"章节有 {len(empty_segs)}/5 段无勾子，最长无钩区域约 {worst_hook_gap} 字", details=details)
        if worst_hook_gap > 2000:
            return self.fail_result(message=f"最长 {worst_hook_gap} 字无钩子—读者可能在这个区间弃书", details=details)
        return self.pass_result(details=details)


# ─── 注水比 ──────────────────────────────────────────

class QLT01B_FillerDetection(BaseGate):
    gate_id = "QLT-01B"
    name = "注水比门禁"
    description = "相邻段落的信息重叠度估评内容密度"
    severity = GateSeverity.WARN

    def evaluate(self, text: str = "") -> GateResult:
        if len(text) < 500: return self.pass_result(message="文本太短")
        paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
        if len(paras) < 2: return self.pass_result()
        water_count = 0
        for i in range(len(paras)-1):
            overlap = _segment_overlap(paras[i], paras[i+1])
            if overlap > 0.7: water_count += 1
        water_ratio = water_count / max(len(paras), 1)
        if water_ratio > 0.4:
            return self.fail_result(message=f"注水比 {water_ratio:.0%}—相邻段落内容高度重复", details={"water_ratio": round(water_ratio,2), "watery_paras": water_count, "total_paras": len(paras)})
        if water_ratio > 0.25:
            return self.fail_result(message=f"注水比 {water_ratio:.0%}—部分段落存在冗余", details={"water_ratio": round(water_ratio,2), "watery_paras": water_count})
        return self.pass_result(details={"water_ratio": round(water_ratio,2)})


# ─── 断章位置 ────────────────────────────────────────

class BRK04B_BreakPosition(BaseGate):
    gate_id = "BRK-04B"
    name = "断章定位门禁"
    description = "大师级断章不是在任意位置断，是在呼吸节奏点上"
    severity = GateSeverity.WARN

    BREAK_SIGNALS = {"危机":["来不及","追上","包围","逼近","紧逼","危险"],
                      "发现":["发现","揭穿","暴露","竟然是"],
                      "决定":["决定","我要","必须","一定要"],
                      "悬念":["不知道","谁能","到底","难道是","你知"],
                      "转折前":["有件事","有个秘密","其实","真相"]}

    def evaluate(self, text: str = "") -> GateResult:
        if len(text) < 200: return self.pass_result()
        last_200 = text[-200:]
        signals_found = {}
        for signal_type, keywords in self.BREAK_SIGNALS.items():
            hits = [kw for kw in keywords if kw in last_200]
            if hits: signals_found[signal_type] = hits
        has_break_signal = len(signals_found) > 0
        if not has_break_signal:
            return self.fail_result(message="章末200字无断章信号—最好的断章位置是后果/发现/决定/危机/悬念/转折前", details={"break_types_found": list(signals_found.keys())})
        return self.pass_result(details={"break_types_found": list(signals_found.keys())})


# ─── 中点检测 ────────────────────────────────────────

class IIT04_Midpoint(BaseGate):
    gate_id = "IIT-04"
    name = "中点转折门禁"
    description = "故事中点（45%-55%）应发生从反应到进攻的转折"
    severity = GateSeverity.WARN

    def evaluate(self, position_pct: float = 0, flip_count_before: int = 0, flip_count_after: int = 0) -> GateResult:
        if position_pct < 40 or position_pct > 60:
            return self.pass_result(message="不在中点范围")
        if flip_count_after <= flip_count_before:
            return self.fail_result(message=f"中点后主动行动频率({flip_count_after})未超过中点前({flip_count_before})—中点转折缺失", details={"position": position_pct, "before": flip_count_before, "after": flip_count_after})
        return self.pass_result()


# ─── 一无所有检测 ────────────────────────────────────

class IIT05_AllIsLost(BaseGate):
    gate_id = "IIT-05"
    name = "一无所有门禁"
    description = "第二幕结尾主角应跌入最低谷"
    severity = GateSeverity.WARN

    def evaluate(self, position_pct: float = 0, emotion_peak: float = 0, gap_density: float = 0) -> GateResult:
        if position_pct < 65 or position_pct > 85:
            return self.pass_result(message="不在第二幕结尾范围")
        if emotion_peak < 1 and gap_density < 1:
            return self.fail_result(message=f"一无所有点缺失—主角在第二幕结尾没有情绪低谷", details={"position": position_pct})
        return self.pass_result()


# ─── 主题证明 ────────────────────────────────────────

class STR07_ThemeProved(BaseGate):
    gate_id = "STR-07"
    name = "主题证明门禁"
    description = "终幕必须通过一个象征性事件证明故事主题"
    severity = GateSeverity.WARN

    def evaluate(self, position_pct: float = 0, opening_mirror: bool = False, choice_signal: bool = False) -> GateResult:
        if position_pct < 85: return self.pass_result(message="不在终幕范围")
        if not opening_mirror and not choice_signal:
            return self.fail_result(message="终幕缺少主题证明—主角没有面对与开篇呼应的选择", details={"opening_mirror": opening_mirror, "choice_signal": choice_signal})
        return self.pass_result()


# ─── B 故事整合 ─────────────────────────────────────

class DLG07_BStory(BaseGate):
    gate_id = "DLG-07"
    name = "B故事整合门禁"
    description = "B故事（感情/关系线）必须在3个关键节点与主线交错"
    severity = GateSeverity.WARN

    def evaluate(self, b_story_exits: bool = True, crossover_points: int = 0) -> GateResult:
        if not b_story_exits: return self.pass_result(message="无B故事")
        if crossover_points < 2:
            return self.fail_result(message=f"B故事与主线的交叉点仅{crossover_points}个（建议3+）", details={"crossover_points": crossover_points})
        return self.pass_result()


# ─── 邪恶力量揭示 ──────────────────────────────────

class RVI06_EvilForceReveal(BaseGate):
    gate_id = "RVI-06"
    name = "邪恶力量揭示门禁"
    description = "表面反派对后的力量应有节奏地揭示"
    severity = GateSeverity.WARN

    def evaluate(self, hints_before: int = 0, layers_revealed: int = 1) -> GateResult:
        if layers_revealed >= 2 and hints_before < 1:
            return self.fail_result(message=f"揭示{layers_revealed}层幕后力量但此前暗示数为{hints_before}—机械降神风险", details={"hints": hints_before, "layers": layers_revealed})
        if layers_revealed == 1 and hints_before == 0:
            return self.pass_result(message="单层反派")
        return self.pass_result()


# ─── Truby 对手网 ───────────────────────────────────

class CRN06_OpponentNetwork(BaseGate):
    gate_id = "CRN-06"
    name = "对手网门禁"
    description = "Truby核心：每个角色不由'他是谁'定义，由'和谁有什么关系'定义"
    severity = GateSeverity.WARN

    def evaluate(self, total_characters: int = 0, unique_relations: int = 0) -> GateResult:
        if total_characters < 3: return self.pass_result()
        ratio = unique_relations / max(total_characters, 1)
        if ratio < 1.5:
            return self.fail_result(message=f"角色关系稀疏（{unique_relations}关系/{total_characters}角色，期望比>{1.5}）—Truby对手网理论：每个角色=他与所有人的关系之和", details={"total_chars": total_characters, "unique_relations": unique_relations, "ratio": round(ratio,2)})
        return self.pass_result()


# ─── 升级节奏（网文）──────────────────────────────────

class PLE07_UpgradeRhythm(BaseGate):
    gate_id = "PLE-07"
    name = "升级节奏门禁"
    description = "不同题材有标准的升级节奏间隔"
    severity = GateSeverity.WARN

    RHYTHMS = {"xianxia_modern": (5,15,30), "xuanhuan": (3,10,20), "urban_modern": (3,8,15)}

    def evaluate(self, genre: str = "xianxia_modern", chapters_since_minor: int = 99, chapters_since_major: int = 99) -> GateResult:
        r = self.RHYTHMS.get(genre, self.RHYTHMS["xianxia_modern"])
        issues = []
        if chapters_since_minor > r[0]:
            issues.append(f"小升级间隔(ch.{chapters_since_minor})超预期(≤{r[0]})")
        if chapters_since_major > r[1]:
            issues.append(f"中升级间隔(ch.{chapters_since_major})超预期(≤{r[1]})")
        if issues:
            return self.fail_result(message="; ".join(issues), details={"genre": genre, "rhythm_expected": {"minor": r[0], "medium": r[1], "major": r[2]}})
        return self.pass_result()


# ─── 付费章节注水检测 ──────────────────────────────

class QLT06_PayWallCheck(BaseGate):
    gate_id = "QLT-06"
    name = "付费章节注水检测门禁"
    description = "上架章节（30-40章）前后是否存在明显的质量下降"
    severity = GateSeverity.BLOCK

    def evaluate(self, chapter_index: int = 0, hook_density: float = 0, avg_hook_density: float = 0) -> GateResult:
        # 上架章节范围：30-40
        if 25 <= chapter_index <= 40:
            if hook_density < avg_hook_density * 0.7:
                return self.fail_result(message=f"上架章节(ch.{chapter_index})勾子密度({hook_density:.1f})明显低于平均水平({avg_hook_density:.1f})—可能有注水", details={"chapter": chapter_index, "hook_density": hook_density, "avg": avg_hook_density, "drop": f"{int((1-hook_density/max(avg_hook_density,0.01))*100)}%"})
            return self.pass_result()
        return self.pass_result()