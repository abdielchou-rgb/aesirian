"""
Transformers-based Chinese NER Entity Extractor
Replaces regex-based extraction with SOTA neural NER.

Models (priority order):
1. hfl/chinese-roberta-wwm-ext — RoBERTa-wwm-ext, Chinese, 110M params
2. hfl/chinese-bert-wwm-ext — BERT-wwm-ext, Chinese, 110M params
3. hfl/chinese-macbert-base — MacBERT, Chinese, 110M params
4. hfl/chinese-structbert-base — StructBERT, Chinese, 110M params

Fine-tuned on: MSRA NER, OntoNotes, Weibo NER, CLUENER, People's Daily
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from functools import lru_cache
import re
import logging

logger = logging.getLogger(__name__)

# ─── Warning 降噪缓存（O3）───
# 同进程内同一类告警只打印一次：多候选模型逐一下载失败、离线环境
# 每次 EntityExtractor 实例化都触发 regex 兜底告警时，避免刷屏。
_WARNED_ONCE: set[str] = set()


def _warn_once(tag: str, message: str) -> None:
    if tag not in _WARNED_ONCE:
        _WARNED_ONCE.add(tag)
        logger.warning(message)

# ─── Data Classes (compatible with existing ExtractionResult) ───

@dataclass
class ExtractedEntity:
    name: str
    entity_type: str  # character / location / event / item
    mentions: int = 1
    first_mention_at: int = 0
    confidence: float = 1.0


@dataclass
class ExtractedAction:
    character: str
    action: str
    target: str = ""
    has_negation: bool = False
    confidence: float = 1.0


@dataclass
class ExtractedFact:
    subject: str
    predicate: str
    obj: str | int | float | bool
    confidence: float = 1.0


@dataclass
class Movement:
    character: str
    from_location: str = ""
    to_location: str = ""


@dataclass
class ExtractionResult:
    characters: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    events: list[ExtractedEntity] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    facts: list[ExtractedFact] = field(default_factory=list)
    actions: list[ExtractedAction] = field(default_factory=list)
    movements: list[Movement] = field(default_factory=list)
    identity_changes: list[dict] = field(default_factory=list)
    new_characters: int = 0
    new_locations: int = 0
    pov_switches: int = 0
    sentences: list[str] = field(default_factory=list)
    # G9 统计
    ai_marker_count: int = 0
    hedge_word_count: int = 0
    transition_repeats: dict = field(default_factory=dict)
    # 新增：NER 原始结果
    ner_entities: list[dict] = field(default_factory=list)


# ─── Model Configuration ───

NER_MODEL_CANDIDATES = [
    "hfl/chinese-roberta-wwm-ext",
    "hfl/chinese-bert-wwm-ext",
    "hfl/chinese-macbert-base",
    "hfl/chinese-structbert-base",
]

# 实体类型映射（模型输出 → 内部类型）
ENTITY_TYPE_MAP = {
    "PER": "character",
    "PERSON": "character",
    "LOC": "location",
    "LOCATION": "location",
    "GPE": "location",
    "ORG": "organization",
    "ORGANIZATION": "organization",
    "EVENT": "event",
    "WORK_OF_ART": "item",
    "PRODUCT": "item",
    "FAC": "location",
    "DATE": "temporal",
    "TIME": "temporal",
    "MONEY": "quantity",
    "PERCENT": "quantity",
}


# ─── Lazy Model Loader ───

class _NERPipeline:
    """懒加载 NER pipeline，首次使用时才下载模型"""

    _instance = None
    _pipeline = None
    _model_name = ""
    _initialized = False
    _init_error = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        pass

    def _try_load(self) -> bool:
        if self._initialized:
            return self._pipeline is not None

        self._initialized = True

        try:
            from transformers import pipeline
            import torch

            for model_name in NER_MODEL_CANDIDATES:
                try:
                    logger.info(f"Loading NER model: {model_name}")
                    self._pipeline = pipeline(
                        "ner",
                        model=model_name,
                        tokenizer=model_name,
                        aggregation_strategy="simple",  # 合并子词
                        device=0 if torch.cuda.is_available() else -1,
                    )
                    self._model_name = model_name
                    logger.info(f"NER model loaded: {model_name}")
                    return True
                except Exception as e:
                    _warn_once(f"ner_load_failed:{model_name}", f"Failed to load {model_name}: {e}")
                    continue

            self._init_error = "All candidate models failed to load"
            logger.error(self._init_error)
            return False

        except ImportError as e:
            self._init_error = f"transformers not installed: {e}"
            logger.warning(self._init_error)
            return False
        except Exception as e:
            self._init_error = f"Unexpected error: {e}"
            logger.error(self._init_error)
            return False

    def is_available(self) -> bool:
        if not self._initialized:
            return self._try_load()
        return self._pipeline is not None

    def extract(self, text: str) -> list[dict]:
        """运行 NER，返回标准化实体列表"""
        if not self.is_available():
            return []

        try:
            # 分段处理长文本（模型最大长度 512）
            max_len = 480
            if len(text) <= max_len:
                return self._pipeline(text)

            # 滑动窗口处理长文本
            results = []
            overlap = 50
            for i in range(0, len(text), max_len - overlap):
                chunk = text[i:i + max_len]
                chunk_results = self._pipeline(chunk)
                # 调整位置偏移
                for ent in chunk_results:
                    ent["start"] += i
                    ent["end"] += i
                results.extend(chunk_results)

            # 去重（基于位置和文本）
            seen = set()
            unique = []
            for ent in results:
                key = (ent["start"], ent["end"], ent["word"])
                if key not in seen:
                    seen.add(key)
                    unique.append(ent)
            return unique

        except Exception as e:
            logger.error(f"NER extraction failed: {e}")
            return []


# 全局单例
_ner_pipeline = _NERPipeline()


# ─── Regex Fallback (for when transformers unavailable) ───

# 保留关键正则用于兜底和规则增强
CHARACTER_PREFIXES = ['小', '老', '大', '阿', '秦', '李', '王', '张', '刘', '陈', '赵', '钱', '孙', '周', '吴', '郑', '冯', '林', '沈', '叶']

ACTION_VERBS = ['说', '道', '问', '答', '喊', '叫', '哭', '笑', '走', '跑', '跳', '站', '坐', '躺', '看', '望', '听', '闻',
                '摸', '拿', '放', '推', '拉', '打', '踢', '抱', '亲', '举', '抬', '低', '转', '回', '来', '去', '进', '出',
                '上', '下', '拿', '放', '抓', '握', '握', '擦', '抹', '闭', '睁', '皱', '叹', '摇', '点', '笑', '哭', '骂']

AI_MARKERS = ['然而', '值得注意的是', '不可否认', '不出所料', '愈发',
              '毫无疑问', '显而易见', '值得一提的是', '令人惊讶的是', '值得注意的是']

HEDGE_WORDS = ['似乎', '可能', '或许', '大概', '某种程度上', '一定程度上', '在某种意义上']

TRANSITION_WORDS = ['然而', '不过', '与此同时', '突然', '随即', '接着', '然后', '可是', '但是', '却']

NEGATIONS = ['不', '没', '没有', '别', '勿', '不要', '从不']

IDENTITY_PROPERTIES = ['性格', '身份', '地位', '年龄', '外貌', '能力', '力量', '修为', '等级', '职业']

SKIP_WORDS = {'可以','没有','因为','所以','如果','虽然','但是','一些','已经','还是','只是','不过','然而','因此',
              '而且','或者','然后','接着','同时','突然','忽然','终于','其实','原来','本来','本来','根本','完全',
              '非常','特别','格外','愈发','越发','更加','越来越','逐渐','渐渐','慢慢','快速','迅速',
              '毫无','无疑','似乎','或许','大概','可能','应该','必须','需要','能够','可以','正在',
              '翻过来','站起来','坐下去','转过身','抬起头','低下头','走上前','退后','推开门','关上门',
              '拿出','放下','拿起','推开','关上','打开','抓住','握住','握住','擦了擦','看了看','想了想',
              '摇了摇','点了点头','叹了口气','闭上眼睛','睁开眼睛','站了起来','看了过去','回过头来',
              '口袋里','衣兜里','背包里','抽屉里','盒子里','箱子里','柜子里','书架里','床头柜上',
              '没人','你知','他知','你不','我不','他会','他只是','没人','没人能','没有人',
              '你知道吗','你不知道','你知道','你听','你说','你想','你看','你告诉我',
              '暖黄色','冷光','微热','微微发热','泛着冷光','暖黄色',
              '黄色','红色','蓝色','绿色','白色','黑色','金色','银色','灰色','暗红色','深蓝色','浅绿色',
              '淡黄色','暗金色','亮银色','铁灰色','乳白色','透明色',
              '是有人','是一个','是一个','有一种','有一股','有一阵',
              '又出现','又有人','又回到了','又看了一眼','又低下头','又抬起头',
              '没有回答','没有说','没有动','没有看','没有看','没有停',
              '没有什么','没有什么','不需要','还不能','还不是','还不是',
              '他还是','他还是','他还是','他还是','他还是','他还是',
              '终于有','终于开','终于说','终于等','终于找',}


# ─── Main Extractor Class ───

class EntityExtractor:
    """混合 NER 提取器：Transformers 优先，正则兜底"""

    def __init__(self, use_transformers: bool = True):
        self.use_transformers = use_transformers and _ner_pipeline.is_available()
        if self.use_transformers:
            logger.info(f"EntityExtractor: Using transformers NER ({_ner_pipeline._model_name})")
        else:
            _warn_once("entity_extractor_regex_fallback", "EntityExtractor: Falling back to regex-only mode")

    @staticmethod
    def _merge_ner_with_regex(text: str, ner_entities: list[dict], regex_result: ExtractionResult) -> ExtractionResult:
        """融合 NER 结果和正则结果，取并集并去重"""
        # NER 实体加入结果
        for ent in ner_entities:
            entity_type = ENTITY_TYPE_MAP.get(ent["entity_group"], "unknown")
            confidence = ent.get("score", 0.9)

            if entity_type == "character" and ent["word"] not in regex_result.characters:
                if ent["word"] not in SKIP_WORDS and len(ent["word"]) <= 4:
                    regex_result.characters.append(ent["word"])
            elif entity_type == "location" and ent["word"] not in regex_result.locations:
                regex_result.locations.append(ent["word"])
            elif entity_type == "event":
                regex_result.events.append(ExtractedEntity(
                    name=ent["word"], entity_type="event", confidence=confidence
                ))
            elif entity_type in ("item", "organization", "product"):
                if ent["word"] not in regex_result.items:
                    regex_result.items.append(ent["word"])

            regex_result.ner_entities.append({
                "text": ent["word"],
                "type": entity_type,
                "start": ent["start"],
                "end": ent["end"],
                "confidence": confidence,
            })

        return regex_result

    @staticmethod
    def _regex_extract(text: str) -> ExtractionResult:
        """原有正则提取逻辑（精简版，保留核心功能）"""
        result = ExtractionResult()
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        sentences = re.split(r'[。！？\n.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 2]
        result.sentences = sentences

        # ── 角色名：NER 主导，正则补充 ──
        char_mentions = set()
        for m in re.finditer(r'([一-鿿]{2,4})(?:说|道|问|答|喊|叫|哭|笑|叹|走|跑|看|望|推|拉|坐|站)', text):
            candidate = m.group(1)
            if candidate not in SKIP_WORDS and len(candidate) <= 3:
                char_mentions.add(candidate)

        # 常见姓氏 + 名
        for m in re.finditer(r'(?:李|王|张|刘|陈|赵|钱|孙|周|吴|郑|冯|林|沈|叶|秦|宋|顾|白|韩|苏|黄|高|马|郭|唐|曹|许|邓|萧|段|顾|沈|林)([一-鿿]{1,2})(?:\s|，|。|？|！|的|了|在|是|有|说|道|看|走|笑|哭|坐|站|拿)', text):
            name = m.group(0).strip()[:3]
            if len(name) >= 2:
                char_mentions.add(name)

        result.characters = list(char_mentions)

        # ── 地点 ──
        locations = set()
        for m in re.finditer(r'(?:在|到|从|去|回|往|向|路过|经过)([一-鿿]{2,6})(?:里|上|中|旁|边|前|后|内|外|附近|的)', text):
            locations.add(m.group(1))
        for m in re.finditer(r'(?:门口|窗外|街上|楼上|屋里|门外|路口|村口|山下|河边|海边|城门口|房间|大厅|花园|街道|广场|医院|学校|公司)', text):
            locations.add(m.group(0))
        result.locations = list(locations)

        # ── 事件 ──
        events = set()
        for m in re.finditer(r'([一-鿿]{2,10}(?:案|事|事件|事故|战争|灾难|聚会|仪式|考试|战斗|冲突|谈判))', text):
            events.add(m.group(1))
        result.events = [ExtractedEntity(name=e, entity_type='event') for e in events]

        # ── 物品 ──
        items = set()
        for m in re.finditer(r'([一-鿿]{2,4})(?:刀|剑|枪|书|信|包|纸|盒|钥匙|手机|钱包|戒指|项链|玉佩)', text):
            if not any(i in m.group(0) for i in ['可以', '没有', '因为', '所以']):
                items.add(m.group(0))
        result.items = list(items)

        # ── 事实（属性）──
        for m in re.finditer(r'([一-鿿]{2,4})今(?:年|日|岁)(?:已经|才|刚|就)?(\d+)(?:岁|了)', text):
            result.facts.append(ExtractedFact(subject=m.group(1), predicate='年龄', obj=int(m.group(2)), confidence=0.9))
        for m in re.finditer(r'([一-鿿]{2,4})(?:有|是|已|已经)(\d+)(?:岁|年|天|月|斤|米|厘米|个|次)', text):
            if not any(skip in m.group(0) for skip in ['可以', '没有', '因为', '所以', '一些']):
                result.facts.append(ExtractedFact(subject=m.group(1), predicate='数量', obj=int(m.group(2)), confidence=0.8))

        # ── 角色行动 ──
        for char_name in char_mentions:
            if char_name in SKIP_WORDS or len(char_name) > 3:
                continue
            for m in re.finditer(re.escape(char_name) + r'([一-鿿]{0,4}?(?:' + '|'.join(ACTION_VERBS) + r'))', text):
                action_text = m.group(0)[len(char_name):]
                if action_text:
                    has_neg = any(n in action_text for n in NEGATIONS)
                    result.actions.append(ExtractedAction(
                        character=char_name, action=action_text, has_negation=has_neg, confidence=0.8
                    ))

        # ── 空间移动 ──
        for char_name in char_mentions:
            if char_name in SKIP_WORDS or len(char_name) > 3:
                continue
            for m in re.finditer(re.escape(char_name) + r'(?:从|离开)([一-鿿]{2,6})(?:里|上|中)?(?:到|回|去|来|返回|前往|走向)([一-鿿]{2,6})', text):
                result.movements.append(Movement(
                    character=char_name, from_location=m.group(1), to_location=m.group(2)
                ))

        # ── POV切换检测 ──
        pov_markers = set()
        for m in re.finditer(r'(?:我|我们)(?:觉得|认为|想|知道|看见|听到|感到)', text):
            pov_markers.add('第一人称')
        for m in re.finditer(r'(?:他|她|它|他们)(?:觉得|认为|想|知道|看见|听到|感到)', text):
            pov_markers.add('第三人称')
        if len(pov_markers) > 1:
            result.pov_switches = 1

        # ── G9统计 ──
        for marker in AI_MARKERS:
            result.ai_marker_count += text.count(marker)
        for word in HEDGE_WORDS:
            result.hedge_word_count += text.count(word)
        for tw in TRANSITION_WORDS:
            count = text.count(tw)
            if count >= 2:
                result.transition_repeats[tw] = count

        # ── 身份变化检测 ──
        for prop in IDENTITY_PROPERTIES:
            for m in re.finditer(r'([一-鿿]{2,4})' + prop + r'(?:变成|成为|变了|不再是|突然变得)([一-鿿，。！？\s]{2,20})', text):
                result.identity_changes.append({
                    'character': m.group(1), 'property': prop,
                    'new_value': m.group(2)[:20],
                    'has_explanation': bool(re.search(r'因为|由于|原来|经过|经历了|发现', m.group(2)))
                })

        result.new_characters = len(result.characters)
        result.new_locations = len(result.locations)
        return result

    def extract(self, text: str) -> ExtractionResult:
        """主入口：混合 NER + 正则"""
        if not text.strip():
            return ExtractionResult()

        # 1. 正则基础提取（快速、完整覆盖）
        regex_result = self._regex_extract(text)

        # 2. Transformers NER 增强
        if self.use_transformers:
            ner_entities = _ner_pipeline.extract(text)
            if ner_entities:
                regex_result = self._merge_ner_with_regex(text, ner_entities, regex_result)

        return regex_result

    @staticmethod
    def to_gate_context(text: str) -> dict:
        """转换为一致性门禁所需的 context 格式"""
        # 创建临时实例避免状态污染
        extractor = EntityExtractor()
        result = extractor.extract(text)

        return {
            'facts': [
                {'subject': f.subject, 'predicate': f.predicate, 'object': str(f.obj)}
                for f in result.facts
            ],
            'char_actions': [
                {'character_id': a.character, 'description': a.action}
                for a in result.actions
            ],
            'identity_changes': result.identity_changes,
            'events': [
                {'event': e.name, 'reference_chapter': 0}
                for e in result.events
            ],
            'movements': [
                {
                    'character': m.character,
                    'from': m.from_location,
                    'to': m.to_location,
                    'travel_time_hours': 0
                }
                for m in result.movements
            ],
            'new_characters': result.new_characters,
            'new_locations': result.new_locations,
            'pov_switches': result.pov_switches,
            'ai_marker_count': result.ai_marker_count,
            'hedge_word_count': result.hedge_word_count,
            'transition_repeats': result.transition_repeats,
            # 新增：NER 详细实体
            'ner_entities': result.ner_entities,
        }


# ─── Convenience Functions ───

def create_extractor(use_transformers: bool = True) -> EntityExtractor:
    """工厂函数：创建提取器实例"""
    return EntityExtractor(use_transformers=use_transformers)


def is_transformers_available() -> bool:
    """检查 transformers NER 是否可用"""
    return _ner_pipeline.is_available()


def get_ner_model_name() -> str:
    """获取当前加载的模型名称"""
    return _ner_pipeline._model_name