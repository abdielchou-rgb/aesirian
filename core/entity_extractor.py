"""
实体提取引擎 — 纯规则中文NLP
为G1-G5门禁提供结构化输入。无外部依赖。

从原始文本中提取：角色名、位置、事件、数字属性、角色行动、POV切换
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re


@dataclass
class ExtractedEntity:
    """从文本中提取的一个实体"""
    name: str
    entity_type: str  # character / location / event / item
    mentions: int = 1
    first_mention_at: int = 0  # 段落号


@dataclass
class ExtractedAction:
    """从文本中提取的一个角色行动"""
    character: str
    action: str
    target: str = ""
    has_negation: bool = False  # 是否包含否定/敌对词


@dataclass
class ExtractedFact:
    """从文本中提取的一个事实陈述"""
    subject: str
    predicate: str
    obj: str | int | float | bool


@dataclass
class Movement:
    """空间移动"""
    character: str
    from_location: str = ""
    to_location: str = ""


@dataclass
class ExtractionResult:
    """完整提取结果"""
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


# ─── 词库 ───

# 常见中文人名/角色名前缀
CHARACTER_PREFIXES = ['小', '老', '大', '阿', '秦', '李', '王', '张', '刘', '陈', '赵', '钱', '孙', '周', '吴', '郑', '冯', '林', '沈', '叶']

# 动作词（用于识别角色行动）
ACTION_VERBS = ['说', '道', '问', '答', '喊', '叫', '哭', '笑', '走', '跑', '跳', '站', '坐', '躺', '看', '望', '听', '闻',
                '摸', '拿', '放', '推', '拉', '打', '踢', '抱', '亲', '举', '抬', '低', '转', '回', '来', '去', '进', '出',
                '上', '下', '拿', '放', '抓', '握', '握', '擦', '抹', '闭', '睁', '皱', '叹', '摇', '点', '笑', '哭', '骂']

# AI标志词
AI_MARKERS = ['然而', '值得注意的是', '不可否认', '不出所料', '愈发',
              '毫无疑问', '显而易见', '值得一提的是', '令人惊讶的是', '值得注意的是']

# 模糊词
HEDGE_WORDS = ['似乎', '可能', '或许', '大概', '某种程度上', '一定程度上', '在某种意义上']

# 过渡词
TRANSITION_WORDS = ['然而', '不过', '与此同时', '突然', '随即', '接着', '然后', '可是', '但是', '却']

# 否定词
NEGATIONS = ['不', '没', '没有', '别', '勿', '不要', '从不']

# 身份相关属性
IDENTITY_PROPERTIES = ['性格', '身份', '地位', '年龄', '外貌', '能力', '力量', '修为', '等级', '职业']


# ─── 提取引擎 ───

# 跳过词——不可能是角色名的常见中文词汇
SKIP_WORDS = {'可以','没有','因为','所以','如果','虽然','但是','一些','已经','还是','只是','不过','然而','因此',
              '而且','或者','然后','接着','同时','突然','忽然','终于','其实','原来','本来','本来','根本','完全',
              '非常','特别','格外','愈发','越发','更加','越来越','逐渐','渐渐','慢慢','快速','迅速',
              '毫无','无疑','似乎','或许','大概','可能','应该','必须','需要','能够','可以','正在',
              '翻过来','站起来','坐下去','转过身','抬起头','低下头','走上前','退后','推开门','关上门',
              '拿出','放下','拿起','推开','关上','打开','抓住','握住','握住','擦了擦','看了看','想了想',
              '摇了摇','点了点头','叹了口气','闭上眼睛','睁开眼睛','站了起来','看了过去','回过头来',
              '口袋里','衣兜里','背包里','抽屉里','盒子里','箱子里','柜子里','书架里','床头柜上',
              # 对话场景常见误识别
              '没人','你知','他知','你不','我不','他会','他只是','没人','没人能','没有人',
              '你知道吗','你不知道','你知道','你听','你说','你想','你看','你告诉我',
              # AI情绪词/颜色词
              '暖黄色','冷光','微热','微微发热','泛着冷光','暖黄色',
              # 颜色词
              '黄色','红色','蓝色','绿色','白色','黑色','金色','银色','灰色','暗红色','深蓝色','浅绿色',
              '淡黄色','暗金色','亮银色','铁灰色','乳白色','透明色',
              # 是有人之类
              '是有人','是一个','是一个','有一种','有一股','有一阵',
              # 动作+动词误识别
              '又出现','又有人','又回到了','又看了一眼','又低下头','又抬起头',
              '没有回答','没有说','没有动','没有看','没有看','没有停',
              '没有什么','没有什么','不需要','还不能','还不是','还不是',
              '他还是','他还是','他还是','他还是','他还是','他还是',
              '终于有','终于开','终于说','终于等','终于找',}

class EntityExtractor:
    """纯规则实体提取器"""

    @staticmethod
    def extract(text: str) -> ExtractionResult:
        if not text.strip():
            return ExtractionResult()

        result = ExtractionResult()
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        sentences = re.split(r'[。！？\n.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 2]
        result.sentences = sentences

        # ── 提取角色名 ──
        # 模式1："XXX说/道/问/答/笑/哭" — 但排除"翻过来""站起来"等组合
        char_mentions = set()
        # 先检查是否被SKIP_WORDS完全覆盖
        for m in re.finditer(r'([一-鿿]{2,4})(?:说|道|问|答|喊|叫|哭|笑|叹|走|跑|看|望|推|拉|坐|站)', text):
            candidate = m.group(1)
            if candidate not in SKIP_WORDS and len(candidate) <= 2:
                char_mentions.add(candidate)
        # 模式2："XXX从/向/对/把/被/在/给/为YYY"
        for m in re.finditer(r'([一-鿿]{2,3})(?:从|向|对|把|被|在|给|为|朝|跟|和|与)(?:[一-鿿]{2,4})(?:说|道|问|笑|哭|拿|走|看|点|摇|叹)', text):
            c = m.group(1)
            if c not in SKIP_WORDS and len(c) <= 3:
                char_mentions.add(c)
        # 模式2b："XXX拿出/放下/拿起/推开"
        for m in re.finditer(r'([一-鿿]{2,3})(?:拿出|放下|拿起|推开|转过身|站起身|低下头|抬起头|走上前|退后|转过身)', text):
            c = m.group(1)
            if c not in SKIP_WORDS and len(c) <= 3:
                char_mentions.add(c)
        # 模式3：常见双姓+名组合
        for m in re.finditer(r'(?:李|王|张|刘|陈|赵|钱|孙|周|吴|郑|冯|林|沈|叶|秦|宋|顾|白|韩|苏|黄|高|马|郭|唐|曹|许|邓|萧|段|顾|沈|林)([一-鿿]{1,2})(?:\s|，|。|？|！|的|了|在|是|有|说|道|看|走|笑|哭|坐|站|拿)', text):
            name = m.group(0).strip()[:2]
            if len(name) == 2:
                char_mentions.add(name)

        result.characters = list(char_mentions)

        # ── 提取地点 ──
        locations = set()
        for m in re.finditer(r'(?:在|到|从|去|回|往|向|路过|经过)([一-鿿]{2,6})(?:里|上|中|旁|边|前|后|内|外|附近|的)', text):
            locations.add(m.group(1))
        for m in re.finditer(r'(?:门口|窗外|街上|楼上|屋里|门外|路口|村口|山下|河边|海边|城门口|房间|大厅|花园|街道|广场|医院|学校|公司)', text):
            locations.add(m.group(0))
        result.locations = list(locations)

        # ── 提取事件 ──
        events = set()
        for m in re.finditer(r'([一-鿿]{2,10}(?:案|事|事件|事故|战争|灾难|聚会|仪式|考试|战斗|冲突|谈判))', text):
            events.add(m.group(1))
        result.events = [ExtractedEntity(name=e, entity_type='event') for e in events]

        # ── 提取物品 ──
        items = set()
        for m in re.finditer(r'([一-鿿]{2,4})(?:刀|剑|枪|书|信|包|纸|盒|钥匙|手机|钱包|戒指|项链|玉佩)', text):
            if not any(i in m.group(0) for i in ['可以', '没有', '因为', '所以']):
                items.add(m.group(0))
        result.items = list(items)

        # ── 提取事实(属性) ──
        # 年龄
        for m in re.finditer(r'([一-鿿]{2,4})今(?:年|日|岁)(?:已经|才|刚|就)?(\d+)(?:岁|了)', text):
            result.facts.append(ExtractedFact(subject=m.group(1), predicate='年龄', obj=int(m.group(2))))
        # 简单数字属性
        for m in re.finditer(r'([一-鿿]{2,4})(?:有|是|已|已经)(\d+)(?:岁|年|天|月|斤|米|厘米|个|次)', text):
            if not any(skip in m.group(0) for skip in ['可以', '没有', '因为', '所以', '一些']):
                result.facts.append(ExtractedFact(subject=m.group(1), predicate='数量', obj=int(m.group(2))))

        # ── 提取角色行动 ──
        for char_name in char_mentions:
            if char_name in SKIP_WORDS or len(char_name) > 3:
                continue
            for m in re.finditer(re.escape(char_name) + r'([一-鿿]{0,4}?(?:' + '|'.join(ACTION_VERBS) + r'))', text):
                action_text = m.group(0)[len(char_name):]
                if action_text:
                    has_neg = any(n in action_text for n in NEGATIONS)
                    result.actions.append(ExtractedAction(
                        character=char_name,
                        action=action_text,
                        has_negation=has_neg
                    ))

        # ── 提取空间移动 ──
        for char_name in char_mentions:
            if char_name in SKIP_WORDS or len(char_name) > 3:
                continue
            # "XXX从A到/回/去B"
            for m in re.finditer(re.escape(char_name) + r'(?:从|离开)([一-鿿]{2,6})(?:里|上|中)?(?:到|回|去|来|返回|前往|走向)([一-鿿]{2,6})', text):
                result.movements.append(Movement(
                    character=char_name,
                    from_location=m.group(1),
                    to_location=m.group(2)
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
            count = text.count(marker)
            result.ai_marker_count += count
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
                    'character': m.group(1),
                    'property': prop,
                    'new_value': m.group(2)[:20],
                    'has_explanation': bool(re.search(r'因为|由于|原来|经过|经历了|发现', m.group(2)))
                })

        result.new_characters = len(result.characters)
        result.new_locations = len(result.locations)
        return result

    @staticmethod
    def to_gate_context(text: str) -> dict:
        """将提取结果转换为一致性门禁所需的context格式"""
        result = EntityExtractor.extract(text)
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
            # 留给读者模型的上下文
            'new_characters': result.new_characters,
            'new_locations': result.new_locations,
            'pov_switches': result.pov_switches,
            'ai_marker_count': result.ai_marker_count,
            'hedge_word_count': result.hedge_word_count,
            'transition_repeats': result.transition_repeats,
        }
