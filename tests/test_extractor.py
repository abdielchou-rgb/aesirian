"""实体提取引擎测试"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.entity_extractor import EntityExtractor


def test_extract_characters():
    text = "张伟推开门。李娜说：你不该来的。王刚笑着摇摇头。"
    result = EntityExtractor.extract(text)
    assert "张伟" in result.characters, f"应提取到张伟，实际{result.characters}"
    assert "李娜" in result.characters or "李" in result.characters
    print(f"[PASS] 角色提取: {result.characters}")


def test_extract_actions():
    text = "张伟推开门。李娜说：你不该来的。"
    result = EntityExtractor.extract(text)
    assert len(result.actions) > 0
    print(f"[PASS] 行动提取: {[(a.character, a.action) for a in result.actions]}")


def test_extract_locations():
    text = "她坐在房间里，窗外下着雨。他走到门口，回头看了一眼。"
    result = EntityExtractor.extract(text)
    assert len(result.locations) > 0, f"应提取到地点，实际{result.locations}"
    print(f"[PASS] 地点提取: {result.locations}")


def test_extract_age():
    text = "林晚今年25岁了。"
    result = EntityExtractor.extract(text)
    assert any(f.predicate == "年龄" for f in result.facts), f"应提取年龄，实际{result.facts}"
    print(f"[PASS] 年龄提取: {result.facts}")


def test_extract_movement():
    text = "王刚从门口走到窗前。"
    result = EntityExtractor.extract(text)
    assert len(result.movements) > 0
    print(f"[PASS] 移动提取: {result.movements}")


def test_g9_markers():
    ai_text = "然而，值得注意的是，不可否认这个事实是毫无疑问的。这是一次令人惊讶的发现。"
    normal_text = "他推开门。桌上放着凉透的茶。她不在。窗外下雨了。他走到窗前。"

    ai_result = EntityExtractor.extract(ai_text)
    normal_result = EntityExtractor.extract(normal_text)

    assert ai_result.ai_marker_count > normal_result.ai_marker_count
    print(
        f"[PASS] G9 AI标志词检测: AI文本={ai_result.ai_marker_count} > 正常文本={normal_result.ai_marker_count}"
    )


def test_to_gate_context():
    text = "张伟今年25岁。他走到门口，李娜在屋里哭。"
    context = EntityExtractor.to_gate_context(text)
    assert "facts" in context
    assert "char_actions" in context
    assert context["new_characters"] > 0
    print(
        f"[PASS] 门禁上下文转换: facts={len(context['facts'])}, actions={len(context['char_actions'])}"
    )


if __name__ == "__main__":
    test_extract_characters()
    test_extract_actions()
    test_extract_locations()
    test_extract_age()
    test_extract_movement()
    test_g9_markers()
    test_to_gate_context()
    print("\n✅ 实体提取全部测试通过")
