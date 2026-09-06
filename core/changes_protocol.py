"""
CHANGES 协议层 — G0 门禁 (Tianming 模式)

核心机制：
AI生成每个章节时必须在末尾附加结构化JSON变更声明。
G0门禁验证声明的完整性，然后G1-G5使用"CHANGES声明 vs KG对比"双通道。

设计原则：
1. 不要求AI严格遵守格式——我们容忍并修复格式偏差
2. 声明越详细，门禁越准确——AI有动力详细声明
3. 声明与文本矛盾时以KG为准——防止AI虚构声明
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable
import json
import re


class ChangeField(Enum):
    """CHANGES声明标准字段（Tianming 12字段的子集）"""
    CHARACTER_STATE = "character_state"          # 角色状态变化
    RELATIONSHIP = "relationship"                 # 关系变化
    EVENT = "event"                               # 新事件
    FORESHADOWING = "foreshadowing"               # 伏笔
    LOCATION_STATE = "location_state"             # 地点状态
    ITEM_TRANSFER = "item_transfer"               # 物品转移
    SECRET = "secret"                             # 秘密
    TIME_PROGRESSION = "time_progression"         # 时间推进
    BELIEF_CHANGE = "belief_change"               # 信念变化（扩展字段）
    NEW_CHARACTER = "new_character"               # 新角色出现


@dataclass
class ChangesDeclaration:
    """结构化的CHANGES声明"""
    character_state: list[dict] = field(default_factory=list)
    relationship: list[dict] = field(default_factory=list)
    event: list[dict] = field(default_factory=list)
    foreshadowing: list[dict] = field(default_factory=list)
    location_state: list[dict] = field(default_factory=list)
    item_transfer: list[dict] = field(default_factory=list)
    secret: list[dict] = field(default_factory=list)
    time_progression: list[dict] = field(default_factory=list)
    belief_change: list[dict] = field(default_factory=list)  # 扩展字段
    new_character: list[dict] = field(default_factory=list)   # 扩展字段

    @property
    def field_count(self) -> int:
        """非空字段数"""
        return sum(1 for f in self.__dataclass_fields__ if getattr(self, f))

    def is_empty(self) -> bool:
        return self.field_count == 0

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in self.__dataclass_fields__.__members__.values()}


class ChangesParser:
    """
    CHANGES声明解析器

    支持4种格式（Tianming兼容）：
    1. <chapter_changes>...</chapter_changes> XML块
    2. ---CHANGES--- 标记 + JSON
    3. ### CHANGES 头 + JSON
    4. 尾部JSON对象
    """

    # CHANGES区域的正则
    PATTERNS = [
        (r'<chapter_changes>(.*?)</chapter_changes>', re.DOTALL),       # XML
        (r'---CHANGES---\s*\n(.*?)(?:\n---|$)', re.DOTALL),            # 标记
        (r'### CHANGES\s*\n(.*?)(?:\n###|$)', re.DOTALL),              # 头
        (r'(\{[\s\S]*"character_state"[\s\S]*\})', re.DOTALL),         # 尾部JSON
    ]

    @classmethod
    def extract_changes_region(cls, text: str) -> Optional[str]:
        """从文本中提取CHANGES区域"""
        for pattern, flags in cls.PATTERNS:
            m = re.search(pattern, text, flags)
            if m:
                return m.group(1).strip()
        return None

    @classmethod
    def parse(cls, text: str) -> tuple[ChangesDeclaration, list[str]]:
        """解析CHANGES声明，返回声明对象+校验错误列表"""
        errors = []
        declaration = ChangesDeclaration()

        region = cls.extract_changes_region(text)
        if not region:
            return declaration, ["未找到CHANGES声明区域"]

        # 清理可能的代码块标记
        region = re.sub(r'^```(?:json)?\s*|\s*```$', '', region, flags=re.MULTILINE)

        # 修复常见JSON错误（中文引号、单引号、尾逗号）
        region = cls._repair_json(region)

        try:
            data = json.loads(region)
        except json.JSONDecodeError as e:
            return declaration, [f"JSON解析失败: {e}"]

        if not isinstance(data, dict):
            return declaration, ["CHANGES声明不是JSON对象"]

        # 映射到字段
        field_map = {
            'character_state': 'character_state',
            'character_states': 'character_state',
            'relationship': 'relationship',
            'relationships': 'relationship',
            'event': 'event',
            'events': 'event',
            'foreshadowing': 'foreshadowing',
            'foreshadowings': 'foreshadowing',
            'location_state': 'location_state',
            'location_states': 'location_state',
            'item_transfer': 'item_transfer',
            'item_transfers': 'item_transfer',
            'secret': 'secret',
            'secrets': 'secret',
            'time_progression': 'time_progression',
            'belief_change': 'belief_change',
            'belief_changes': 'belief_change',
            'new_character': 'new_character',
            'new_characters': 'new_character',
        }

        for raw_key, records in data.items():
            key_lower = raw_key.lower().replace('-', '_')
            target_field = field_map.get(key_lower)
            if target_field and isinstance(records, list):
                setattr(declaration, target_field, records)

        # 校验：至少声明了角色信念变化或状态变化
        has_core_content = bool(declaration.character_state or declaration.belief_change
                               or declaration.new_character or declaration.relationship)
        if not has_core_content:
            errors.append("CHANGES声明至少需要 character_state/belief_change/new_character/relationship 之一")

        if declaration.is_empty():
            errors.append("CHANGES声明为空")

        return declaration, errors

    @classmethod
    def _repair_json(cls, text: str) -> str:
        """修复常见JSON格式错误"""
        # 中文引号→英文
        text = text.replace('“', '"').replace('”', '"').replace('‘', "'")
        # 单引号→双引号（只在非字符串上下文中）
        text = re.sub(r"(?<!\\)'", '"', text)
        # 尾逗号
        text = re.sub(r',(\s*[\]}])', r'\1', text)
        # 中文冒号→英文（只在键名位置）
        text = re.sub(r'(?<=["\'])\s*：\s*(?=["\'])', ':', text)
        return text


class G0ChangesGate:
    """
    G0 门禁 — CHANGES协议验证

    这是门禁管线的第一道。验证AI是否提供了完整的变更声明。
    G0通过后，G1-G5使用声明中的结构化数据做精确验证。
    """

    def __init__(self):
        self.parser = ChangesParser()

    def validate(self, text: str) -> tuple[bool, ChangesDeclaration, list[str]]:
        """执行G0验证

        Returns:
            (passes, declaration, errors)
        """
        declaration, errors = self.parser.parse(text)
        passes = len(errors) == 0 and not declaration.is_empty()
        return passes, declaration, errors

    def merge_with_extraction(self, text: str, kg_context: dict) -> dict:
        """
        双通道合并：CHANGES声明 vs 文本提取

        返回综合上下文，供G1-G5使用。
        CHANGES声明的数据优先级高于实体提取。
        """
        passes, declaration, _ = self.validate(text)

        if passes:
            # 从CHANGES声明提取信念变化
            belief_changes = declaration.belief_change
            for change in belief_changes:
                character = change.get('character', '')
                proposition = change.get('proposition', '')
                new_value = change.get('new_value', None)
                if character and proposition and new_value is not None:
                    if 'facts' not in kg_context:
                        kg_context['facts'] = []
                    kg_context['facts'].append({
                        'subject': character,
                        'predicate': proposition,
                        'object': new_value,
                    })

            # 新角色
            for new_char in declaration.new_character:
                name = new_char.get('name', '')
                if name:
                    if 'facts' not in kg_context:
                        kg_context['facts'] = []
                    kg_context['facts'].append({
                        'subject': name,
                        'predicate': '首次出现',
                        'object': 'true',
                    })

            # 关系变化 → char_actions
            for rel in declaration.relationship:
                source = rel.get('source', '')
                target = rel.get('target', '')
                change = rel.get('change', '')
                if source and change:
                    if 'char_actions' not in kg_context:
                        kg_context['char_actions'] = []
                    kg_context['char_actions'].append({
                        'character_id': source,
                        'description': f"{change}与{target}的关系",
                    })

        return kg_context

    @staticmethod
    def format_prompt_instructions() -> str:
        """生成插入到AI写作prompt中的CHANGES协议说明"""
        return """
【章节变更声明协议】
在每一章正文结束后，你必须附加一份JSON格式的CHANGES声明，说明本章中发生了哪些变化。
CHANGES声明必须放在 `---CHANGES---` 标记之后。

示例结构：
---CHANGES---
{
  "character_state": [
    {"name": "角色名", "state": "新状态", "reason": "原因"}
  ],
  "belief_change": [
    {"character": "角色名", "proposition": "信念命题", "new_value": "新信念内容"}
  ],
  "new_character": [
    {"name": "新角色名", "role": "角色描述", "first_appearance": "出现场景"}
  ],
  "relationship": [
    {"source": "角色A", "target": "角色B", "change": "变化描述"}
  ]
}

关键要求：
1. character_state 和 belief_change 至少提供一个
2. 新出现的角色必须声明在 new_character 中
3. 使用中文键名也可（自动映射）
"""
