"""文鉴 Genre Profile System — 体裁感知的门禁参数覆盖。

映射体裁（仙侠、历史、言情等）和平台（网文、出版、流媒体等）
到门禁参数调整值。
"""

from dataclasses import dataclass, field


@dataclass
class GenreProfile:
    id: str
    name: str
    description: str
    platform: str = "webnovel"
    pace: str = "normal"

    gate_overrides: dict = field(default_factory=dict)

    inciting_incident_deadline: float = 8.0
    hook_position_limit: int = 150
    max_open_gaps: int = 15
    max_gap_net_rate: float = 0.8
    gap_overload_threshold: float = 6.0
    chapters_between_mini_climax: int = 5
    min_touchpoints_for_critical: int = 2
    value_monotone_activation_pct: float = 15.0
    enable_worldbuilding_exemption: bool = False
    skip_irreversibility_check: bool = False
    gap_density_floor: float = 1.0

    recap_interval: int = 4
    goal_restatement_interval: int = 3
    min_foreshadow_mentions: int = 2
    require_jump_anchor: bool = True
    require_subtext_layer: bool = True


GENRE_PROFILES: dict[str, GenreProfile] = {}


def _reg(p: GenreProfile):
    GENRE_PROFILES[p.id] = p


_reg(
    GenreProfile(
        id="xianxia_modern",
        name="现代仙侠（快节奏）",
        description="近年快节奏修仙小说，开篇即高潮，信息密度大",
        platform="webnovel",
        pace="fast",
        gap_overload_threshold=7.0,
        inciting_incident_deadline=5.0,
        hook_position_limit=100,
        max_open_gaps=18,
        max_gap_net_rate=1.0,
        chapters_between_mini_climax=3,
    )
)

_reg(
    GenreProfile(
        id="xianxia_traditional",
        name="传统仙侠（慢热）",
        description="传统修仙小说，前期世界观铺垫长，节奏偏缓",
        platform="webnovel",
        pace="slow",
        gap_density_floor=0.5,
        inciting_incident_deadline=10.0,
        hook_position_limit=200,
        enable_worldbuilding_exemption=True,
        value_monotone_activation_pct=20.0,
    )
)

_reg(
    GenreProfile(
        id="historical_rebirth",
        name="历史重生",
        description="穿越/重生历史类，长篇铺垫型，背景介绍段落较长",
        platform="webnovel",
        pace="normal",
        enable_worldbuilding_exemption=True,
        chapters_between_mini_climax=7,
        inciting_incident_deadline=8.0,
        hook_position_limit=200,
    )
)

_reg(
    GenreProfile(
        id="historical_conflict",
        name="历史权谋/战争",
        description="冲突驱动的历史小说，权谋斗争和战争场面为主",
        platform="webnovel",
        pace="normal",
        gap_overload_threshold=5.0,
        chapters_between_mini_climax=4,
        min_touchpoints_for_critical=3,
        inciting_incident_deadline=6.0,
    )
)

_reg(
    GenreProfile(
        id="xuanhuan",
        name="玄幻",
        description="高魔高武世界，升级流主线，战斗与修炼交替",
        platform="webnovel",
        pace="fast",
        gap_overload_threshold=7.0,
        max_open_gaps=15,
        inciting_incident_deadline=5.0,
        chapters_between_mini_climax=4,
        skip_irreversibility_check=True,
    )
)

_reg(
    GenreProfile(
        id="urban_modern",
        name="都市/现代",
        description="现代都市题材，情感/职场/悬疑驱动，节奏适中",
        platform="webnovel",
        pace="normal",
        inciting_incident_deadline=8.0,
        hook_position_limit=200,
        max_open_gaps=12,
    )
)

_reg(
    GenreProfile(
        id="publication_literary",
        name="出版文学",
        description="传统出版文学，预期读者连续阅读",
        platform="publication_novel",
        pace="slow",
        inciting_incident_deadline=15.0,
        hook_position_limit=3000,
        max_open_gaps=8,
        gap_overload_threshold=4.0,
        gap_density_floor=0.5,
        chapters_between_mini_climax=0,
    )
)

_reg(
    GenreProfile(
        id="romance",
        name="言情",
        description="情感驱动，CP感、甜虐比例、误会循环是关键",
        platform="webnovel",
        pace="normal",
        inciting_incident_deadline=8.0,
        hook_position_limit=200,
        max_open_gaps=12,
        chapters_between_mini_climax=5,
        min_touchpoints_for_critical=3,
    )
)

_reg(
    GenreProfile(
        id="suspense",
        name="悬疑",
        description="悬念驱动，信息释放节奏、紧张度曲线是关键",
        platform="webnovel",
        pace="fast",
        gap_overload_threshold=5.0,
        inciting_incident_deadline=5.0,
        hook_position_limit=150,
        max_open_gaps=14,
        chapters_between_mini_climax=3,
    )
)

_reg(
    GenreProfile(
        id="streaming_first",
        name="流媒体优先",
        description="奈飞式超高密度叙事，每章2+翻转，前500字激励事件",
        platform="streaming_first",
        pace="fast",
        inciting_incident_deadline=5.0,
        hook_position_limit=300,
        max_open_gaps=18,
        max_gap_net_rate=1.0,
        gap_overload_threshold=5.0,
        chapters_between_mini_climax=3,
        min_touchpoints_for_critical=3,
        recap_interval=2,
        goal_restatement_interval=2,
    )
)


def get_profile(genre_id: str = None, platform: str = None) -> GenreProfile:
    """解析体裁配置。体裁未知时回退到平台默认。"""
    if genre_id and genre_id in GENRE_PROFILES:
        return GENRE_PROFILES[genre_id]
    platform_map = {
        "webnovel": "xianxia_modern",
        "publication_novel": "publication_literary",
        "streaming_first": "streaming_first",
    }
    fallback_id = platform_map.get(platform or "", "xianxia_modern")
    return GENRE_PROFILES.get(fallback_id, GENRE_PROFILES["xianxia_modern"])


def list_profiles() -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "platform": p.platform,
            "pace": p.pace,
        }
        for p in GENRE_PROFILES.values()
    ]
