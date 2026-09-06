"""
方法论注册表 — 知识底座注册脚本
将 Æsir 知识底座中的方法论注册到注册表中
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.strategy_registry import MethodologyFamily as F
from core.strategy_registry import MethodologyNode as Node
from core.strategy_registry import MethodologyRegistry
from core.strategy_registry import OutputType as O
from core.strategy_registry import TriggerEvent as T


def build_registry() -> MethodologyRegistry:
    reg = MethodologyRegistry()

    # ═══════════════════════════════════════════
    # 叙事结构族 (Narrative Structure)
    # ═══════════════════════════════════════════

    reg.register(
        Node(
            id="M001",
            name="英雄之旅",
            family=F.NARRATIVE_STRUCTURE,
            source="Joseph Campbell, 1949 — 17阶段三幕结构",
            description="所有神话共享同一'单一神话'结构。用于弧线规划和宏观节奏检测。",
            trigger_events=[T.ARC_PLANNING, T.POST_CHAPTER],
            output_type=O.CONSTRAINT,
            weight=2.0,
        )
    )
    reg.register(
        Node(
            id="M002",
            name="15节拍表",
            family=F.NARRATIVE_STRUCTURE,
            source="Blake Snyder, 2005 — Save the Cat!",
            description="精确到每页/每千字定位的关键节拍。用于精确节奏审计。",
            trigger_events=[T.AUDIT, T.POST_CHAPTER],
            output_type=O.ASSESSMENT,
            weight=1.5,
        )
    )
    reg.register(
        Node(
            id="M003",
            name="5幕辩证结构",
            family=F.NARRATIVE_STRUCTURE,
            source="John Yorke, 2013 — Into the Woods",
            description="正→反→合→超越→余韵。用于冲突螺旋检测。",
            trigger_events=[T.ARC_PLANNING, T.POST_CHAPTER],
            output_type=O.CONSTRAINT,
            weight=1.5,
        )
    )
    reg.register(
        Node(
            id="M004",
            name="7基本情节",
            family=F.NARRATIVE_STRUCTURE,
            source="Christopher Booker, 2004",
            description="战胜怪物/白手起家/探寻/远行回归/喜剧/悲剧/重生。弧线类型匹配。",
            trigger_events=[T.DIVERGENCE, T.ARC_PLANNING],
            output_type=O.DIRECTION,
            weight=1.0,
        )
    )
    reg.register(
        Node(
            id="M005",
            name="Story Spine",
            family=F.NARRATIVE_STRUCTURE,
            source="Pixar — Emma Coats推广",
            description="7步：很久以前→每天→有一天→因为这→直到终于→从那以后。最小完整叙事周期。",
            trigger_events=[T.DIVERGENCE, T.CONVERGENCE],
            output_type=O.DIRECTION,
            weight=1.0,
        )
    )

    # ═══════════════════════════════════════════
    # 叙事原子族 (Narrative Atom)
    # ═══════════════════════════════════════════

    reg.register(
        Node(
            id="M010",
            name="31种叙事功能",
            family=F.NARRATIVE_ATOM,
            source="Vladimir Propp, 1928",
            description="所有民间故事共享31种功能。功能位置比功能本身更重要。",
            trigger_events=[T.DIVERGENCE, T.CHARACTER_CREATE],
            output_type=O.DIRECTION,
            weight=2.0,
        )
    )
    reg.register(
        Node(
            id="M011",
            name="36种戏剧情境",
            family=F.NARRATIVE_ATOM,
            source="Georges Polti, 1895",
            description="所有戏剧情境可归结为36种模式。用于冲突模式匹配。",
            trigger_events=[T.DIVERGENCE, T.CHARACTER_CREATE],
            output_type=O.DIRECTION,
            weight=1.5,
        )
    )
    reg.register(
        Node(
            id="M012",
            name="行动素模型",
            family=F.NARRATIVE_ATOM,
            source="A.J. Greimas, 1966",
            description="6功能位置：发送者→对象→接收者 / 主体 / 辅助者-反对者。补全角色功能。",
            trigger_events=[T.DIVERGENCE, T.CHARACTER_CREATE, T.AUDIT],
            output_type=O.ASSESSMENT,
            weight=1.5,
        )
    )
    reg.register(
        Node(
            id="M013",
            name="三态模型",
            family=F.NARRATIVE_ATOM,
            source="Tzvetan Todorov",
            description="平衡→破坏→新平衡。最小叙事完整性判断。",
            trigger_events=[T.AUDIT, T.CONVERGENCE],
            output_type=O.ASSESSMENT,
            weight=1.5,
        )
    )
    reg.register(
        Node(
            id="M014",
            name="故事与话语分析",
            family=F.NARRATIVE_ATOM,
            source="Gérard Genette, 1972",
            description="故事=时间顺序原材料，话语=如何讲述(顺序/视角/节奏/省略)。策略制定。",
            trigger_events=[T.AUDIT, T.POST_CHAPTER],
            output_type=O.CONSTRAINT,
            weight=1.0,
        )
    )

    # ═══════════════════════════════════════════
    # 创意认知族 (Creative Cognition)
    # ═══════════════════════════════════════════

    reg.register(
        Node(
            id="M020",
            name="五阶段模型",
            family=F.CREATIVE_COGNITION,
            source="Graham Wallas, 1926",
            description="准备→孵化→启发→评估→精化。创作阶段检测。",
            trigger_events=[T.FRAGMENT_INPUT, T.CONVERGENCE],
            output_type=O.INSIGHT,
            weight=1.0,
        )
    )
    reg.register(
        Node(
            id="M021",
            name="Geneplore生成-探索",
            family=F.CREATIVE_COGNITION,
            source="Finke, Ward & Smith, 1992",
            description="生成(快速/禁止评判)↔探索(检验/延展/组合)。发散-收敛循环核心。",
            trigger_events=[T.DIVERGENCE, T.CONVERGENCE],
            output_type=O.DIRECTION,
            weight=2.0,
        )
    )
    reg.register(
        Node(
            id="M022",
            name="SCAMPER 7操作",
            family=F.CREATIVE_COGNITION,
            source="Bob Eberle, 1971",
            description="替换/组合/改编/修改/变更用途/去除/反转。创意变异操作符。",
            trigger_events=[T.DIVERGENCE],
            output_type=O.TRANSFORMATION,
            weight=1.5,
        )
    )

    # ═══════════════════════════════════════════
    # 类型契约族 (Genre Contract)
    # ═══════════════════════════════════════════

    reg.register(
        Node(
            id="M030",
            name="网文爽点系统",
            family=F.GENRE_CONTRACT,
            source="中国网文行业数千万部实战",
            description="12种爽点：打脸/扮猪吃老虎/升级/奇遇/装逼/逆袭等。爽点密度/节奏审计。",
            trigger_events=[T.AUDIT, T.CONVERGENCE],
            output_type=O.ASSESSMENT,
            weight=2.0,
        )
    )
    reg.register(
        Node(
            id="M031",
            name="执念驱动",
            family=F.GENRE_CONTRACT,
            source="猫腻",
            description="角色行为由内心深处的执念驱动，而非外部情节。行为反差制造深度。",
            trigger_events=[T.CHARACTER_CREATE, T.AUDIT],
            output_type=O.INSIGHT,
            weight=1.5,
        )
    )
    reg.register(
        Node(
            id="M032",
            name="视觉锤+落地悬念",
            family=F.GENRE_CONTRACT,
            source="辰东",
            description="关键情节绑定可视觉化的画面。每章结尾必须是具体问题而非氛围悬念。",
            trigger_events=[T.POST_CHAPTER, T.AUDIT],
            output_type=O.ASSESSMENT,
            weight=1.0,
        )
    )

    # ═══════════════════════════════════════════
    # 角色系统族 (Character System)
    # ═══════════════════════════════════════════

    reg.register(
        Node(
            id="M040",
            name="7大角色系统",
            family=F.CHARACTER_SYSTEM,
            source="John Truby, 2007",
            description="22个故事步骤+7大角色系统。角色功能完整性检测。",
            trigger_events=[T.CHARACTER_CREATE, T.AUDIT],
            output_type=O.ASSESSMENT,
            weight=1.5,
        )
    )
    reg.register(
        Node(
            id="M041",
            name="Dramatica 4 Throughlines",
            family=F.CHARACTER_SYSTEM,
            source="Dramatica, 1994 — 叙事意图理论",
            description="客观线/主角线/影响线/关系线四视角。ToM v2 的核心架构。",
            trigger_events=[T.ARC_PLANNING, T.CHARACTER_CREATE, T.AUDIT],
            output_type=O.CONSTRAINT,
            weight=2.0,
        )
    )
    reg.register(
        Node(
            id="M042",
            name="3维角色",
            family=F.CHARACTER_SYSTEM,
            source="Lajos Egri, 1946 — The Art of Dramatic Writing",
            description="生理/社会/心理三维。角色立体度检查。",
            trigger_events=[T.CHARACTER_CREATE, T.AUDIT],
            output_type=O.ASSESSMENT,
            weight=1.0,
        )
    )

    # ═══════════════════════════════════════════
    # 认知科学族 (Cognitive Science)
    # ═══════════════════════════════════════════

    reg.register(
        Node(
            id="M050",
            name="12章认知秘密",
            family=F.COGNITIVE_SCIENCE,
            source="Lisa Cron, 2012 — Wired for Story",
            description="从神经科学出发的12条故事法则。逐章认知审计。",
            trigger_events=[T.AUDIT, T.POST_CHAPTER],
            output_type=O.ASSESSMENT,
            weight=2.0,
        )
    )
    reg.register(
        Node(
            id="M051",
            name="微张力",
            family=F.COGNITIVE_SCIENCE,
            source="Donald Maass — Writing the Breakout Novel",
            description="5问法：连续5段是否有未解释的事件/动机/关系。G11门禁基础。",
            trigger_events=[T.AUDIT],
            output_type=O.ASSESSMENT,
            weight=1.5,
        )
    )
    reg.register(
        Node(
            id="M052",
            name="展示不告知谱系",
            family=F.COGNITIVE_SCIENCE,
            source="多来源综合：McKee/Scriptnotes/Cron/Block/Maass",
            description="7种展示技术：感官/行为/潜台词/环境/时间/信息/反差。去AI化检测理论依据。",
            trigger_events=[T.AUDIT],
            output_type=O.ASSESSMENT,
            weight=1.5,
        )
    )

    # ═══════════════════════════════════════════
    # 质量标准族 (Quality Gate)
    # ═══════════════════════════════════════════

    reg.register(
        Node(
            id="M060",
            name="Story Grid 5诫命",
            family=F.QUALITY_GATE,
            source="Shawn Coyne — Story Grid",
            description="煽动事件→转折点→危机→高潮→解决 + 每幕同时有internal/external变化。",
            trigger_events=[T.AUDIT, T.CONVERGENCE],
            output_type=O.ASSESSMENT,
            weight=2.0,
        )
    )
    reg.register(
        Node(
            id="M061",
            name="MICE Quotient",
            family=F.QUALITY_GATE,
            source="Orson Scott Card + Mary Robinette Kowal",
            description="4类型(世界/问题/角色/事件) + 嵌套进出序(开=逆序闭)。结构完整性检测。",
            trigger_events=[T.AUDIT],
            output_type=O.ASSESSMENT,
            weight=1.0,
        )
    )
    reg.register(
        Node(
            id="M062",
            name="前提句完整性",
            family=F.QUALITY_GATE,
            source="Jeff Lyons — Anatomy of a Premise Line",
            description="公式：当[激发]发生在[主角]身上，ta必须[行动]对抗[冲突]以达成[目标]，否则[代价]。",
            trigger_events=[T.FRAGMENT_INPUT, T.CONVERGENCE],
            output_type=O.CONSTRAINT,
            weight=1.0,
        )
    )

    # ═══════════════════════════════════════════
    # 工程实践族 · Engineering
    # ═══════════════════════════════════════════

    reg.register(
        Node(
            id="M070",
            name="三维评估",
            family=F.ENGINEERING,
            source="Chan & Schunn, — 创意评估研究",
            description="新颖性/影响力/可行性三维评分。影响力是最强预测因子，新颖性最弱。",
            trigger_events=[T.DIVERGENCE, T.CONVERGENCE],
            output_type=O.ASSESSMENT,
            weight=1.0,
        )
    )
    reg.register(
        Node(
            id="M071",
            name="Pixar 22条",
            family=F.ENGINEERING,
            source="Emma Coats, 2011",
            description="创作原则集：钦佩努力多过成功、巧合只能惹麻烦不能解麻烦、怕什么就写什么。",
            trigger_events=[T.FRAGMENT_INPUT, T.AUDIT],
            output_type=O.INSIGHT,
            weight=0.8,
        )
    )
    reg.register(
        Node(
            id="M072",
            name="发酵概念",
            family=F.ENGINEERING,
            source="中国网文行业实践",
            description="未选世界线不消失→进入发酵池→跨会话唤醒。多分支管理策略。",
            trigger_events=[T.DIVERGENCE, T.CONVERGENCE],
            output_type=O.DIRECTION,
            weight=1.0,
        )
    )
    reg.register(
        Node(
            id="M073",
            name="三次驯化",
            family=F.ENGINEERING,
            source="Æsir 特有设计",
            description="前3次使用走对话优先路径。不让新用户面对8条世界线感到淹没。",
            trigger_events=[T.FRAGMENT_INPUT],
            output_type=O.INSIGHT,
            weight=0.8,
        )
    )

    return reg


def print_registry_summary(reg: MethodologyRegistry = None):
    if not reg:
        reg = build_registry()
    summary = reg.summary()
    print("📊 方法论注册表总览")
    print(f"   总数: {summary['total']} 个方法论节点")
    for family, count in summary["families"].items():
        print(f"   {family}: {count} 个")
    print("\n   所有触发事件:")
    for event, count in summary["triggers"].items():
        print(f"   {event}: {count} 个方法论可响应")


if __name__ == "__main__":
    reg = build_registry()
    print_registry_summary(reg)

    # 测试：获取所有发散事件的策略
    print("\n--- 发散策略 ---")
    for node in reg.get_by_trigger(T.DIVERGENCE):
        print(f"   {node.id} {node.name} ({node.source})")

    print("\n--- 审计策略 ---")
    for node in reg.get_by_trigger(T.AUDIT):
        print(f"   {node.id} {node.name} ({node.source})")
