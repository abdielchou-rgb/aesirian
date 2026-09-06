"""
叙事提示模板 — Æsirian LLM 续写建议专用

设计原则：
1. 系统提示 + 用户提示模板分离，方便单独测试/替换
2. 输出严格 JSON 数组，便于后端解析
3. 字符限制硬编码在提示里（text≤40字, rationale≤20字）
4. 中文输出，方法论来源标注
"""

from __future__ import annotations

SYSTEM_PROMPT = """你是一个专业小说写作助手。基于作者当前的故事状态，提供3-5个具体的续写方向。

每个建议必须包含以下字段：
- type: 建议类型
  - tension：未解决的张力点/冲突推进
  - character：角色行动倾向/信念转变
  - reader：读者沉浸度/认知模式利用
  - pattern：叙事模式/节拍切换
- text: 续写开头或方向指引（不超过40字）
- rationale: 为什么这样建议（不超过20字）
- source: 来自什么方法论（如"Campbell英雄之旅"、"Propp叙事功能"、"ToM信念冲突"、"读者传输度模型"）

要求：
1. 至少包含1个tension类型和1个character类型
2. text必须具体可操作，不要泛泛而谈
3. 优先利用已有的角色张力和信念冲突

只输出JSON数组，不解释。格式示例：
[{"type":"tension","text":"陈默发现水晶里藏着女儿的...","rationale":"私人情感打破职业防线","source":"ToM信念冲突"}]"""


def build_user_prompt(
    premise: str,
    characters: list,
    tensions: list[dict],
    trends: dict,
    chapter: int,
) -> str:
    """根据当前项目状态构建用户提示

    Parameters
    ----------
    premise : str
        故事前提/标题
    characters : list
        角色列表（dict 或 str）
    tensions : list[dict]
        当前张力点列表，每项包含 description, intensity, involved
    trends : dict
        读者模型趋势数据，包含 transportation_trend 等
    chapter : int
        当前章节数

    Returns
    -------
    str
        用户提示文本（控制在500 token以内）
    """
    parts: list[str] = []

    # 故事前提
    parts.append(f"故事前提：{premise[:80]}")

    # 角色列表
    if characters:
        char_names = []
        for c in characters[:8]:
            if isinstance(c, dict):
                char_names.append(c.get("name", "?"))
            else:
                char_names.append(str(c))
        parts.append(f"角色：{', '.join(char_names)}")

    # 未解决张力（最多3条，每条截断）
    if tensions:
        parts.append("未解决张力：")
        for t in tensions[:3]:
            desc = t.get("description", "")[:50]
            intensity = t.get("intensity", 0)
            involved = ", ".join(t.get("involved", [])[:3])
            parts.append(f"  - [{intensity:.1f}] {desc}（涉及：{involved}）")

    # 读者趋势
    transport_trend = trends.get("transportation_trend", "→ 平稳")
    open_questions = trends.get("open_questions", [])
    parts.append(f"读者沉浸度趋势：{transport_trend}")
    if open_questions:
        parts.append(f"读者心中未解问题：{', '.join(str(q)[:30] for q in open_questions[:2])}")

    # 进度
    parts.append(f"当前进度：第{chapter}章")

    parts.append("\n请给出3-5个续写方向：")
    return "\n".join(parts)


def build_user_prompt_from_constraints(
    premise: str,
    chapter: int,
    constraints: dict,
) -> str:
    """从场景约束字典构建用户提示（便捷封装）

    与 orchestrator.generate_scene_constraints() 的输出格式对齐。
    """
    tensions = constraints.get("tension_points", [])

    # 从角色倾向提取角色名
    character_names = [
        t.get("character", "")
        for t in constraints.get("character_tendencies", [])
        if t.get("character")
    ]

    trends = constraints.get("reader_state", {})
    return build_user_prompt(
        premise=premise,
        characters=character_names,
        tensions=tensions,
        trends=trends,
        chapter=chapter,
    )
