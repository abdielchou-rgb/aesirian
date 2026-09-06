"""
可配置审计维度 — InkOS模式

按genre类型动态构建审计维度集：
- 悬疑推理: 激活时序检测 + 红鲱鱼密度 + 线索回路完整性
- 仙侠玄幻: 激活战力体系一致性 + 等级晋升规则 + 世界观规则
- 都市逆袭: 激活爽点密度 + 逆袭节奏 + 资源增长曲线
- 言情: 激活情感弧线 + CP互动频率 + 甜虐比
- 通用: 默认激活维度

每个维度独立可开关，可调节阈值。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Genre(Enum):
    MYSTERY = "悬疑推理"
    XIANXIA = "仙侠玄幻"
    URBAN_REVENGE = "都市逆袭"
    ROMANCE = "言情"
    HISTORICAL = "历史权谋"
    GROWTH = "成长逆袭"
    SCIFI = "科幻末世"
    GENERAL = "通用"


@dataclass
class AuditDimension:
    """一个可审计维度"""

    id: str
    name: str
    description: str
    active_by_default: bool = True
    weight: float = 1.0  # 对总分的权重
    threshold_warn: float = 0.6  # WARN阈值
    threshold_block: float = 0.3  # BLOCK阈值

    # 如何检查——由门禁系统实现
    check_fn: str | None = None  # 对应的方法名

    # InkOS风格：维度说明（注入LLM审计prompt）
    prompt_note: str = ""


# ─── 维度注册表 ───

DIMENSION_REGISTRY: dict[str, AuditDimension] = {
    # ====== 通用维度（所有类型都激活）=======
    "D01": AuditDimension("D01", "角色信念一致性", "角色的行为与其信念状态一致", weight=2.0),
    "D02": AuditDimension("D02", "身份连续性", "角色人格/能力/关系不突变", weight=1.5),
    "D03": AuditDimension("D03", "时间线一致性", "事件顺序、年龄、季节合理", weight=1.5),
    "D04": AuditDimension("D04", "空间一致性", "地理位置和距离合理", weight=1.0),
    "D05": AuditDimension("D05", "去AI化检测", "句式多样性、词汇自然度", weight=1.5),
    "D06": AuditDimension("D06", "叙事节奏", "章节内冲突密度达标", weight=1.5),
    # ====== 悬疑推理专属 =======
    "D10": AuditDimension(
        "D10",
        "时序精密性",
        "时间线必须精确可追溯，不允许模糊时间跳跃",
        active_by_default=False,
        weight=2.0,
        prompt_note="悬疑推理要求时间线精确到天甚至小时。检查时间表述是否模糊",
    ),
    "D11": AuditDimension(
        "D11",
        "红鲱鱼密度",
        "假线索与真线索的比例合理",
        active_by_default=False,
        weight=1.5,
        prompt_note="悬疑推理需要红鲱鱼（假线索）。检查是否有足够的分歧方向",
    ),
    "D12": AuditDimension(
        "D12",
        "线索回路完整性",
        "所有线索必须闭环或显式保留",
        active_by_default=False,
        weight=2.0,
        prompt_note="悬疑推理不允许'失落的线索'——每一条线索要么回收，要么显式标注为待续",
    ),
    # ====== 仙侠玄幻专属 =======
    "D20": AuditDimension(
        "D20",
        "战力体系一致性",
        "战力等级体系不能乱",
        active_by_default=False,
        weight=2.0,
        prompt_note="修仙境界/等级体系必须严格遵守。越级挑战必须有合理解释",
    ),
    "D21": AuditDimension(
        "D21",
        "升级节奏",
        "主角突破/升级间隔合理",
        active_by_default=False,
        weight=1.5,
        prompt_note="每10-15章一个升级节奏。太快=水分，太慢=拖沓",
    ),
    "D22": AuditDimension(
        "D22",
        "世界观规则",
        "世界观设定的一致性和约束",
        active_by_default=False,
        weight=2.0,
        prompt_note="仙侠世界的物理/魔法规则不可随意打破",
    ),
    # ====== 都市逆袭专属 =======
    "D30": AuditDimension(
        "D30",
        "爽点密度",
        "打脸/逆袭/碾压频率达标",
        active_by_default=False,
        weight=1.5,
        prompt_note="都市逆袭每3章至少1个爽点。检查最近章节的爽点密度",
    ),
    "D31": AuditDimension(
        "D31",
        "逆袭节奏",
        "被压制→机会→逆袭的循环节奏",
        active_by_default=False,
        weight=1.5,
        prompt_note="逆袭需要'低点→转折→高潮'的完整弧线，不能一路顺风",
    ),
    "D32": AuditDimension(
        "D32",
        "资源增长曲线",
        "经济/人脉/地位增长合理",
        active_by_default=False,
        weight=1.0,
        prompt_note="逆袭流的资源增长需要曲线而非直线",
    ),
    # ====== 言情专属 =======
    "D40": AuditDimension(
        "D40",
        "情感弧线完整性",
        "相遇→吸引→障碍→牺牲→重聚",
        active_by_default=False,
        weight=2.0,
        prompt_note="言情需要完整的情感弧线。检查是否有跳过关键阶段",
    ),
    "D41": AuditDimension(
        "D41",
        "甜虐比",
        "甜蜜与虐心的比例合理",
        active_by_default=False,
        weight=1.5,
        prompt_note="甜虐比约3:1。过虐劝退，过甜无张力",
    ),
    "D42": AuditDimension(
        "D42",
        "CP互动频率",
        "主要CP的互动密度",
        active_by_default=False,
        weight=1.0,
        prompt_note="每千字至少1个CP情感触点",
    ),
}


# ─── Genre维度映射 ───

GENRE_DIMENSIONS: dict[Genre, list[str]] = {
    Genre.MYSTERY: ["D01", "D02", "D03", "D04", "D05", "D06", "D10", "D11", "D12"],
    Genre.XIANXIA: ["D01", "D02", "D03", "D04", "D05", "D06", "D20", "D21", "D22"],
    Genre.URBAN_REVENGE: ["D01", "D02", "D03", "D04", "D05", "D06", "D30", "D31", "D32"],
    Genre.ROMANCE: ["D01", "D02", "D03", "D04", "D05", "D06", "D40", "D41", "D42"],
    Genre.HISTORICAL: ["D01", "D02", "D03", "D04", "D05", "D06"],
    Genre.GROWTH: ["D01", "D02", "D03", "D04", "D05", "D06"],
    Genre.SCIFI: ["D01", "D02", "D03", "D04", "D05", "D06"],
    Genre.GENERAL: ["D01", "D02", "D03", "D04", "D05", "D06"],
}


class AuditDimensionManager:
    """审计维度管理器 — 按genre动态构建可审计维度集"""

    def __init__(self, genre: Genre = Genre.GENERAL):
        self.genre = genre
        self._active_cache: list[AuditDimension] | None = None

    def set_genre(self, genre: Genre):
        self.genre = genre
        self._active_cache = None

    def get_active_dimensions(self) -> list[AuditDimension]:
        """获取当前genre激活的维度列表"""
        if self._active_cache is not None:
            return self._active_cache

        dim_ids = GENRE_DIMENSIONS.get(self.genre, GENRE_DIMENSIONS[Genre.GENERAL])
        self._active_cache = [
            DIMENSION_REGISTRY[did] for did in dim_ids if did in DIMENSION_REGISTRY
        ]
        return self._active_cache

    def get_prompt_block(self) -> str:
        """生成注入LLM审计prompt的维度说明块"""
        lines = [f"【可配置审计维度 — 当前genre: {self.genre.value}】"]
        for dim in self.get_active_dimensions():
            note = dim.prompt_note or dim.description
            lines.append(f"  {dim.id} {dim.name}: {note} (权重{dim.weight})")
        return "\n".join(lines)

    def get_weighted_score(self, check_results: dict[str, float]) -> float:
        """根据维度和权重计算加权总分"""
        total_weight = 0
        weighted = 0
        for dim in self.get_active_dimensions():
            if dim.id in check_results:
                weighted += check_results[dim.id] * dim.weight
                total_weight += dim.weight
        return weighted / total_weight if total_weight > 0 else 1.0

    def summary(self) -> dict:
        """输出摘要"""
        dims = self.get_active_dimensions()
        return {
            "genre": self.genre.value,
            "active_dimensions": len(dims),
            "dimensions": [{"id": d.id, "name": d.name, "weight": d.weight} for d in dims],
            "weights_total": sum(d.weight for d in dims),
        }
