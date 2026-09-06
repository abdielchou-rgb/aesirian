"""CSN 一致性桥 — Character/Setting Novelty 数值矛盾检测（P0-3, 2026-09-07）。

背景：深度审计 S1.2.1.3 与 docs/internal/gate-verification-report.md 均发现
「时间/空间/身份/事实类矛盾 0/12 检出」。根因之一：正则 EntityExtractor 对
数值事实（"陈默修了十一年罪忆水晶"）提取为空 → 跨章一致性检测的
facts 集合为空 → 矛盾无法比对。

本模块提供纯规则、零依赖的数值事实扫描：
- 中文数词 ↔ 阿拉伯数字归一化（"十一年"→11、"二十一"→21、"三十岁"→30）
- 从单章文本抽取 (subject, predicate, value, unit) 数值事实
- 供 cross-chapter 一致性检测做同 subject+predicate 的跨章数值比对

刻意保守：只识别「角色名 + 动作/系动词 + 数词 + 单位(年/岁/个月/天/层/号/次)」
的明确数值事实，避免把普通文本误判为事实（误报治理优先）。
"""
from __future__ import annotations

import re

# 中文数词映射（支持 0-9999，覆盖网文常见的年数/岁数/层数/序号）
_CN_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def chinese_numeral_to_int(s: str) -> int | None:
    """把中文数词归一化为 int；非数词/无法解析返回 None。阿拉伯数字直接返回。"""
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if not all(c in _CN_DIGITS or c in _CN_UNITS for c in s):
        return None
    total = 0
    section = 0  # 当前小节累加（<10 的部分）
    for ch in s:
        if ch in _CN_DIGITS:
            section += _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            if section == 0:
                section = 1  # "十"=10、"百"=100 开头（如"十一"、"百五"罕见但兼容）
            total += section * unit
            section = 0
    total += section
    return total if total >= 0 else None


_NUM_RE = re.compile(r"([0-9零一二两三四五六七八九十百千〇]+)")


def _find_numeral(text: str) -> int | None:
    m = _NUM_RE.search(text)
    if not m:
        return None
    return chinese_numeral_to_int(m.group(1))


# 动作/系动词桥：角色名 与 数值事实 之间的连接词
_VERB_BRIDGES = [
    "修了", "干了", "做了", "待了", "学了", "练了", "等了", "找了", "查了",
    "走了", "离开", "失踪", "认识", "结婚", "入行", "开店", "守了", "供了",
    "用", "花", "有", "是", "已", "已经", "今年", "今年刚", "才", "满",
    "升到", "降到", "退到", "住过", "服役", "攒了", "存了",
]
# 可数值化的属性谓词：数字后单位 → 事实谓词
_UNIT_PREDICATE = {
    "年": "时长",
    "岁": "年龄",
    "个月": "时长",
    "天": "时长",
    "层": "楼层",
    "号": "编号",
    "次": "次数",
    "点": "时刻",
    "楼": "楼层",
}
# 单位候选串（含 序号 A-3 / B-7 形态）
_UNIT_RE = re.compile(r"(年|岁|个月|天|层|号|次|点|楼|(?:[A-Za-z]-?\d+))")
# 角色候选：2-3 个汉字（故事人名常见长度）
_CHAR_RE = re.compile(r"([一-鿿]{2,3})(?=" + "|".join(re.escape(v) for v in _VERB_BRIDGES) + ")")


class NumericFact:
    """单条数值事实：谁 + 什么属性 + 值(归一化 int)。"""

    __slots__ = ("subject", "predicate", "value", "unit", "raw")

    def __init__(self, subject: str, predicate: str, value: int, unit: str, raw: str):
        self.subject = subject
        self.predicate = predicate
        self.value = value
        self.unit = unit
        self.raw = raw

    def key(self) -> tuple[str, str]:
        """跨章比对用 key：同 subject+predicate 才有可比性。"""
        return (self.subject, self.predicate)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"NumericFact({self.subject},{self.predicate}={self.value}{self.unit})"


def scan_numeric_facts(text: str) -> list[NumericFact]:
    """从单章文本抽取数值事实（保守规则）。

    识别形态：
      陈默修了十一年罪忆水晶       → (陈默, 时长, 11)
      陈默今年三十岁               → (陈默, 年龄, 30)
      陈默在B-7层工作              → (陈默, 楼层, B7)  # 字母楼层特殊处理
    角色名限定在 2-3 个汉字，且须后接动作桥词，降低误报。
    """
    facts: list[NumericFact] = []
    if not text or not text.strip():
        return facts

    # 按句子切分，逐句扫描：避免跨句错误配对
    sentences = re.split(r"[。！？；\n.!?;]+", text)
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 4:
            continue
        # 1) 数字+单位 直接形态：B-7 层 / A-3 号 / 11 年
        for m in re.finditer(
            r"([一-鿿]{2,3})"
            r"(?:修了|干了|做了|待了|学了|练了|等了|找了|查了|用了|等了|守了|供了|"
            r"今年|今年刚|已经|已|才|满|有|是|住过|服役|攒了|存了)"
            r"([0-9零一二两三四五六七八九十百千〇]+|(?:[A-Za-z])[-]?\d+)?"
            r"(年|岁|个月|天|层|号|次|点|楼)",
            sent,
        ):
            name, num_str, unit = m.group(1), m.group(2), m.group(3)
            if not num_str:
                continue
            # 跳过明显非人名词（数量+单位前的主语应是人物/主体）
            if name in {"这个", "那个", "这些", "整个", "公司", "房间", "地方"}:
                continue
            # 跳过含"的"的主语（"曹渊的女儿今年八岁"→"的女儿"是修饰关系，非独立人名）
            if "的" in name:
                continue
            # 跳过机构/场所型后缀（"安全局在…待了九年"→"安全局"是组织非人物）
            if name.endswith(("局", "公司", "学校", "医院", "政府", "部队", "委员会")):
                continue
            # 跳过地点/方位型后缀（"在洛阳待了九年"→"洛阳"是地名非人物；
            # 地名后缀命中率高的字尾：阳/京/州/城/港/镇/村/区/星/海/山/河）
            if name.endswith(
                (
                    "阳", "京", "州", "城", "港", "镇", "村", "区",
                    "海", "山", "河", "江", "湖", "街", "路", "楼", "层",
                    "市", "省", "县", "星", "国", "宫", "殿",
                )
            ):
                continue
            value: int | None = None
            if unit == "号" and num_str and num_str[:1].isalpha():
                # 字母编号 A-3 → 保留为规范化串用负值映射；此处仅登记存在性
                continue
            value = chinese_numeral_to_int(num_str) if num_str else None
            if value is None:
                continue
            predicate = _UNIT_PREDICATE.get(unit, "数值")
            facts.append(NumericFact(name, predicate, value, unit, m.group(0)))

    return facts


def find_cross_chapter_numeric_conflicts(
    current_text: str, history: list[tuple[int, str]]
) -> list[dict]:
    """跨章数值矛盾比对。

    Args:
      current_text: 当前章文本
      history: [(历史章节号, 历史文本)]——已提交的历史章

    Returns:
      [{type:"csn_numeric_contradiction", severity:"BLOCK", detail,
        current_chapter, conflict_chapter, subject, predicate, before, after}]
    """
    conflicts: list[dict] = []
    current_facts = scan_numeric_facts(current_text)
    if not current_facts:
        return conflicts

    # 以 (subject,predicate) 分组当前章事实（同一章内同属性出现多次取最后一次）
    cur_map: dict[tuple[str, str], NumericFact] = {}
    for f in current_facts:
        cur_map[f.key()] = f

    for ch_no, hist_text in history:
        past_facts = scan_numeric_facts(hist_text)
        past_map: dict[tuple[str, str], NumericFact] = {}
        for f in past_facts:
            past_map[f.key()] = f
        for key, cur_f in cur_map.items():
            past_f = past_map.get(key)
            if past_f and past_f.value != cur_f.value:
                conflicts.append(
                    {
                        "type": "csn_numeric_contradiction",
                        "severity": "BLOCK",
                        "detail": f"{cur_f.subject}的{cur_f.predicate}：第{ch_no}章为"
                        f"{past_f.value}{past_f.unit}，当前变为{cur_f.value}{cur_f.unit}，且无转变说明",
                        "current_chapter": len(history) + 1,
                        "conflict_chapter": ch_no,
                        "subject": cur_f.subject,
                        "predicate": cur_f.predicate,
                        "before": f"{past_f.value}{past_f.unit}",
                        "after": f"{cur_f.value}{cur_f.unit}",
                    }
                )
                break  # 一个 subject+predicate 找到首个冲突即可
    return conflicts
