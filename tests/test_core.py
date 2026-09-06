"""ToM引擎 + 知识图谱 + 门禁系统集成测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from tom_engine import TheoryOfMindEngine, BeliefSource, TensionType
from knowledge_graph import TemporalKnowledgeGraph, NodeType, EdgeType
from consistency_gates import ConsistencyGateSystem, GateLevel


def test_tom_belief_update():
    """ToM引擎：信念更新和戏剧反讽检测"""
    tom = TheoryOfMindEngine()
    tom.add_character("zhang", "张伟")
    tom.add_character("li", "李娜")

    # 设置读者知道的真相和张伟的错误信念
    tom.reader_knowledge["谁是凶手"] = "王刚"  # 真相：凶手是王刚

    # 张伟被欺骗——认为凶手是李娜
    tom.update_belief(
        "zhang", "谁是凶手", "李娜",
        confidence=0.9,
        source=BeliefSource.DECEPTION
    )

    # 李娜目击了真相
    tom.update_belief(
        "li", "谁是凶手", "王刚",
        confidence=1.0,
        source=BeliefSource.DIRECT_WITNESS
    )

    # 王敏真诚地误信凶手是李娜（推理源=非错误信念）——与李娜目击真凶构成信念冲突
    tom.add_character("wang", "王敏")
    tom.update_belief(
        "wang", "谁是凶手", "李娜",
        confidence=0.8,
        source=BeliefSource.INFERENCE
    )

    # 检测张力——应该有戏剧反讽（读者知道张伟搞错了）
    tensions = tom.detect_tension()

    has_dramatic_irony = any(
        t.type == TensionType.DRAMATIC_IRONY
        for t in tensions
    )
    has_belief_conflict = any(
        t.type == TensionType.BELIEF_CONFLICT
        for t in tensions
    )

    assert has_dramatic_irony, "应该有戏剧反讽——读者知道张伟的信念是错的"
    assert has_belief_conflict, "应该有信念冲突——李娜(目击真凶)与王敏(推理误信)信念矛盾"

    # 快照恢复
    snapshot = tom.to_snapshot()
    restored = TheoryOfMindEngine.from_snapshot(snapshot)
    assert restored.get_character("zhang") is not None

    print(f"[PASS] ToM信念更新: 发现{len(tensions)}个张力点")
    for t in tensions:
        print(f"  - [{t.type.value}] {t.description}")


def test_tom_recursive_belief():
    """ToM引擎：递归信念（三层嵌套）"""
    tom = TheoryOfMindEngine()
    tom.add_character("a", "角色A")
    tom.add_character("b", "角色B")
    tom.add_character("c", "角色C")

    # 设置：角色A以为角色B不知道角色C的秘密
    tom.update_recursive_belief(
        "a", "b", "角色C是卧底", "不知道",
        confidence=0.9, depth=2
    )

    # 但实际上B知道——这里用 world_beliefs 存储B对世界的事实认知
    tom.update_belief(
        "b", "角色C是卧底", "知道",
        confidence=1.0, source=BeliefSource.DIRECT_WITNESS
    )

    tensions = tom.detect_tension()
    has_recursive = any(
        t.type == TensionType.RECURSIVE_MISMATCH
        for t in tensions
    )

    assert has_recursive, "应该有递归错位张力"
    print(f"[PASS] ToM递归嵌套: 正确检测到递归信念错位")


def test_tom_action_validation():
    """ToM引擎：行动倾向校验（G2门禁的核心）"""
    tom = TheoryOfMindEngine()
    tom.add_character("a", "角色A")

    tom.update_belief("a", "角色B是朋友", True, confidence=1.0)

    # 一致性检查：举报朋友 → 应该冲突
    conflict = tom.validate_action("a", "角色A举报了角色B")
    assert conflict is not None, "举报朋友应与信念冲突"

    # 一致性检查：保护朋友 → 应该不冲突
    no_conflict = tom.validate_action("a", "角色A保护了角色B")
    assert no_conflict is None, "保护朋友不应冲突"

    print(f"[PASS] ToM行动校验: 正确检测行动与信念的一致性")


def test_knowledge_graph():
    """知识图谱：节点、边、冲突检测"""
    kg = TemporalKnowledgeGraph()

    kg.add_node("张伟", NodeType.CHARACTER, {"年龄": 25, "status": "alive"})
    kg.add_node("李娜", NodeType.CHARACTER, {"年龄": 24, "status": "alive"})
    kg.add_node("钥匙", NodeType.ITEM)

    kg.add_edge("张伟", "李娜", EdgeType.RELATES_TO, {"type": "恋人"})
    kg.add_edge("张伟", "钥匙", EdgeType.OWNS)

    # 冲突检测
    conflicts = kg.detect_conflicts("30岁了", "张伟")
    assert len(conflicts) > 0, "年龄矛盾应被检测到"

    no_conflict = kg.detect_conflicts("张伟和李娜在约会", "张伟")
    # 这条没有直接矛盾

    # 时序一致性
    kg.current_chapter = 5
    kg.add_node("命案", NodeType.EVENT)
    kg.add_edge("张伟", "命案", EdgeType.PARTICIPATES)

    kg.current_chapter = 3
    time_conflict = kg.check_temporal_consistency("命案", 2)
    assert time_conflict is not None, "参与早于事件应有冲突"

    print(f"[PASS] 知识图谱: 节点/边/冲突检测/时序一致性全部通过")


def test_gate_system():
    """一致性门禁系统"""
    gates = ConsistencyGateSystem()

    # G1：事实一致性（需要知识图谱，测试基本的）
    no_kg_result = gates.check_g1_fact_consistency("测试文本", facts=[])
    assert no_kg_result is None, "没有知识图谱时不检查G1"

    # G9：去AI化检测
    ai_text = "然而，值得注意的是，不可否认这个事实是毫无疑问的。由此可见，这是一个令人惊讶的发现。值得一提的是，这种情况并不罕见。愈发明显的是，我们需要重新思考这个问题。毫无疑问，答案就在眼前。"
    g9_result = gates.audit_g9_deai_detection(ai_text)
    assert g9_result is not None, "AI腔文本应被检测到"
    assert g9_result.gate_id == "G9"

    # G9：健康文本
    normal_text = "他推开门。桌上放着一杯凉透的茶。她不在。窗外下雨了。他走到窗前。"
    g9_normal = gates.audit_g9_deai_detection(normal_text)
    assert g9_normal is None, "自然文本应通过G9"

    print(f"[PASS] 一致性门禁: G1跳过/G9 AI检测/G9正常文本全部正确")


def test_reader_model():
    """读者模型模拟器"""
    from reader_model import ReaderModelSimulator

    reader = ReaderModelSimulator()

    # 评估叙事传输度
    high_transport = (
        "她的手在发抖。不是那种明显的颤抖——只是指尖轻轻碰了碰杯沿，"
        "然后缩回去。他说了什么吗？她听不清。"
        "为什么偏偏是今天？为什么偏偏是他？"
    )
    score = reader.evaluate_transportation(high_transport)
    assert score.overall > 30, "有感染力的文本传输度应 > 30"
    print(f"[PASS] 读者模型: 叙事传输度={score.overall:.1f}/100")

    # 更新和查询
    reader.update_from_text("张伟走到门口。李娜在屋里哭。", 1)
    assert len(reader.model.known_characters) > 0
    print(f"[PASS] 读者模型: 角色索引构建, 已知角色={reader.model.known_characters}")


def test_cooldown_matrix():
    """事件冷却矩阵"""
    from reader_model import EventCooldownMatrix

    matrix = EventCooldownMatrix(decay_rate=0.7)

    matrix.record_usage("打脸")
    matrix.record_usage("打脸")
    matrix.record_usage("打脸")
    matrix.record_usage("觉醒")

    hot = matrix.get_hot_patterns(threshold=0.5)
    assert len(hot) > 0, "过度使用的模式应被标记为'热'"

    cold = matrix.get_cold_patterns()
    assert "碾压" in cold, "从未使用的模式应在'冷'列表"

    saturation = matrix.check_saturation(window=3, threshold=0.5)
    assert saturation is not None, "3次打脸在最近3次使用中应触发饱和"

    matrix.advance_time(3)
    cooled = matrix.get_cooldown("打脸")
    assert cooled < 3.0, "衰减后冷却值应降低"

    print(f"[PASS] 冷却矩阵: 记录/检测/衰减全部正确")


if __name__ == "__main__":
    test_tom_belief_update()
    test_tom_recursive_belief()
    test_tom_action_validation()
    test_knowledge_graph()
    test_gate_system()
    test_reader_model()
    test_cooldown_matrix()
    print("\n✅ 所有测试通过！")
