# Æsirian v1.0 工程实施蓝图（最终执行版）

> **目标**：操作简洁 × 吸收顶级项目 × 发挥世界级认知
> **执行者**：opencode agent
> **日期**：2026-09-04
> **状态**：可直接执行

---

## 一、核心设计哲学

### 1.1 一句话定位

> **"Æsirian 是一个理解叙事的写作伙伴——它在你需要时给你建议，不需要时安静陪伴。"**

### 1.2 三条铁律

| 铁律 | 说明 |
|------|------|
| **一键开始** | 首页只有一个输入框，输入想法→开始写作 |
| **渐进披露** | 新手只看核心，专家可展开全部 |
| **认知可见** | ToM 引擎、方法论、审计结果——全部可视化呈现 |

### 1.3 吸收的顶级项目精华（完整版）

| 来源 | 吸收什么 | 怎么吸收 |
|------|---------|---------|
| **NovelAI** | 多层上下文工程 | Memory → Author's Note → Lorebook → 正文 |
| **Sudowrite** | 可视化情节脑图 + 多变体生成 | 节点图 + 3 变体选择 |
| **WriteHERE** | 递归大纲规划（EMNLP 2025） | 前提 → 幕 → 章 → 场景 |
| **AI-Novel-Prod** | 风格引擎 | StyleDNA 提取 + 绑定 + 去AI |
| **CreAgentive** | 双图解耦 | 角色图 + 情节图 → 耦合 |
| **DOME** | 动态大纲 + 时序 KG | 大纲自动更新 + 冲突检测 |
| **GOAT** | 故事值电荷 | 场景正/负值 + 电荷变化 |
| **InkOS** | 去 AI 味 4 规则 | 段落均匀度/模糊词/公式化/列表 |
| **Morpheus** | 三层记忆 L1/L2/L3 | 即时/情景/派生 |
| **Novel-Engine** | Voice Profile | 引导式访谈捕获文风 |
| **Dramatica** | 四视角叙事 | 客观/主角/影响/关系 |
| **Netflix** | 5 秒钩子规则 | 前 500 字必须有冲突 |
| **AnySpark** | 8 阶段处理器 | 生成→验证→修改循环 |

### 1.4 吸收的顶级方法论（完整版）

| 方法论 | 核心 | 应用 |
|--------|------|------|
| **MICE Quotient** | 4 类型嵌套规则（LIFO） | 大纲合法性检查 |
| **Barthes 现实效应** | 细节 > 抽象 | 写作质量提升 |
| **Storr 控制幻觉** | 6 条大脑需求规则 | 叙事张力检查 |
| **Maass 微张力** | 5 问检验法 | 段落级质量 |
| **Show Don't Tell** | 7 技法 | 具体化建议 |
| **Freytag/Yorke** | 高潮位置差异 | 节奏规划 |
| **Campbell 英雄之旅** | 17 阶段 | 弧线模板 |
| **Snyder 救猫咪** | 15 节拍 | 节奏模板 |
| **Propp 31 功能** | 叙事功能序列 | 情节原子 |
| **Greimas 行动素** | 6 功能位置 | 角色关系建模 |
| **Todorov 三态** | 平衡→破坏→新平衡 | 最小叙事单元 |
| **Genette 话语** | 故事 vs 话语 | POV/节奏策略 |
| **Booker 7 情节** | 基本情节类型 | 弧线选择 |
| **Polti 36 情境** | 冲突类型库 | 冲突原子 |
| **Pixar Story Spine** | 7 步通用叙事 | 最小完整故事 |
| **Dan Harmon Story Circle** | 8 步循环 | 弧线模板 |
| **Yorke 5 幕辩证** | 正→反→合→超越→余韵 | 高潮位置 |
| **Egri 骨骼结构** | 前提三段论 | 角色三维 |
| **Lisa Cron 12 章** | 认知神经学 | 读者大脑机制 |
| **Maass 微张力** | 5 问法 | 段落张力 |

### 1.5 吸收的顶级论文（完整版）

| 论文 | 核心 | 应用 |
|------|------|------|
| **WriteHERE** (EMNLP 2025) | 递归任务分解 | 大纲生成器 |
| **DOME** (NAACL 2025) | 动态大纲 + 时序 KG | 大纲规划 |
| **CreAgentive** (arXiv 2025) | 双图解耦 | 角色/情节分离 |
| **EvoSpark** (ACL 2026) | 智能体社会涌现 | 角色仿真 |
| **IVIE** (ICCC 2026) | 神经符号双验证 | 门禁升级 |
| **CASPER** (UNC 2026) | 8 维角色深度 | ToM v2 |
| **CAE** (arXiv 2025) | 角色弧光嵌入 | G3 升级 |
| **CHARCO** (arXiv 2025) | 角色一致性基准 | 评估体系 |
| **StoryArcNet** (arXiv 2025) | 轨迹平滑度 | G3 升级 |
| **PNAS Sui Generis** (2025) | 情节多样性指标 | G12 |
| **EACL 2026** | 连贯性可计算 | 门禁理论 |

### 1.6 发挥的 Æsirian 独有优势

| 优势 | 如何发挥 |
|------|---------|
| **递归 ToM 引擎** | 角色信念可视化 + 戏剧张力自动检测 |
| **方法论注册表** | 每条建议标注来源（"来自 Campbell 英雄之旅"） |
| **可配置审计** | 按 genre 自动切换门禁维度 |
| **CHANGES 协议** | AI 必须声明本章改变了什么 |
| **风格指纹 L1-L4** | 用户文风学习 + 爆款对标 |
| **166 道门禁** | 代码级强制执行 |
| **时序知识图谱** | 节点/边 + 冲突检测 + 因果链 |

---

## 二、产品形态：三视图模型

### 2.1 灵感视图（默认）

```
┌─────────────────────────────────────────────────────────┐
│  ✦ Æsirian                                    [项目 v]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│     ┌─────────────────────────────────────────────┐     │
│     │                                             │     │
│     │  写下一个模糊的想法...                       │     │
│     │  比如："一个修复罪忆水晶的人"               │     │
│     │                                             │     │
│     │  [ 开始写作 → ]                             │     │
│     │                                             │     │
│     └─────────────────────────────────────────────┘     │
│                                                         │
│     最近项目：                                          │
│     ┌─────────────────────────────────────────────┐     │
│     │ 📖 洛阳星港                    第2章 85分   │     │
│     └─────────────────────────────────────────────┘     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**交互**：
- 输入框支持 Enter 快速开始
- 点击最近项目直接进入写作视图
- 右上角项目切换器可创建/切换项目

---

### 2.2 写作视图（核心）

```
┌─────────────────────────────────────────────────────────┐
│  ✦ 洛阳星港    [保存] [导出 ▼]        🔴 实时  85分    │
├─────────────────────────────────────────────────────────┤
│  ┌─ 章节 ──────────────────────┐  ┌─ 智能建议 ──────┐  │
│  │                              │  │                  │  │
│  │  第2章                       │  │  → 曹渊此时出现  │  │
│  │  ┌────────────────────────┐  │  │    制造意外相遇  │  │
│  │  │                        │  │  │    [来自英雄之旅]│  │
│  │  │  陈默把水晶接入读数仪  │  │  │                  │  │
│  │  │  七层加密逐层解开。    │  │  │  → 揭示水晶记忆  │  │
│  │  │  第五层时，他听到了    │  │  │    画面中的秘密  │  │
│  │  │  声音——不是通过扬声    │  │  │    [来自悬念理论]│  │
│  │  │  器，而是直接在颅骨    │  │  │                  │  │
│  │  │  里震动。              │  │  │  → 第三方势力    │  │
│  │  │                        │  │  │    争夺水晶      │  │
│  │  │  [继续输入...]         │  │  │    [来自冲突升级]│  │
│  │  │                        │  │  │                  │  │
│  │  └────────────────────────┘  │  │  [🔄 刷新建议]   │  │
│  │                              │  │                  │  │
│  │  [✨ AI 续写] [📋 审计]      │  └──────────────────┘  │
│  └──────────────────────────────┘                        │
│                                                         │
│  ┌─ 折叠面板 ────────────────────────────────────────┐  │
│  │  [角色] [世界观] [大纲] [审计] [风格] [历史]       │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**核心交互**：

| 操作 | 效果 |
|------|------|
| 输入文字 | 实时保存，每 30 秒自动保存 |
| 点击建议 | 建议文本插入光标位置 |
| `Ctrl+Enter` | 触发 AI 续写（基于上下文） |
| `Ctrl+/` | 唤出命令面板 |
| 点击 [角色] | 展开角色面板（心智网格） |
| 点击 [审计] | 展开审计面板（评分 + 提醒） |

---

### 2.3 审阅视图（按需）

```
┌─────────────────────────────────────────────────────────┐
│  审计报告 - 第2章                          [✕ 关闭]     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │                                                 │    │
│  │          本章评分                               │    │
│  │                                                 │    │
│  │            85 / 100                             │    │
│  │                                                 │    │
│  │     ✅ 通过 42    ⚠️ 提醒 3    ❌ 阻断 0       │    │
│  │                                                 │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ⚠️ 需要关注：                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  1. 对话比例偏低 (12%)                          │    │
│  │     建议：增加人物互动场景                       │    │
│  │     [来自: 网文节奏门禁 PRP-01]                 │    │
│  ├─────────────────────────────────────────────────┤    │
│  │  2. 第3段节奏过快                               │    │
│  │     建议：拆分为两个场景，增加过渡描写           │    │
│  │     [来自: 叙事连贯性门禁 NFR-04]               │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ✅ 表现良好：                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  ✓ 角色信念一致（陈默的行为符合其认知）          │    │
│  │  ✓ 无时间线矛盾                                  │    │
│  │  ✓ 世界观规则一致                                │    │
│  │  ✓ 伏笔设置合理                                  │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  [📊 查看详细报告]  [🔄 重新审计]                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 三、后端架构重设计

### 3.1 上下文工程系统（Context Engineering System）

**目标**：从"单次拼接"升级为"多层嵌套注入"（吸收 NovelAI + Morpheus）

#### 3.1.1 上下文层级定义

```python
# core/context/engine.py

class ContextLayer(Enum):
    PROJECT = 0      # 项目元信息（始终注入）
    CHARACTERS = 1   # 角色档案（始终注入）
    RECENT = 2       # 最近 N 章摘要（按相关性检索）
    EPISODIC = 3     # 情景记忆（Morpheus L2）
    DERIVED = 4      # 派生记忆 RUNTIME_STATE + OPEN_THREADS（Morpheus L3）
    USER = 5         # 用户当前输入（最高优先级）

@dataclass
class ContextConfig:
    max_tokens: int = 32000
    layers: dict[ContextLayer, bool] = field(default_factory=lambda: {
        ContextLayer.PROJECT: True,
        ContextLayer.CHARACTERS: True,
        ContextLayer.RECENT: True,
        ContextLayer.EPISODIC: True,
        ContextLayer.DERIVED: True,
        ContextLayer.USER: True,
    })
    recent_chapters: int = 3
    character_detail_level: str = "full"  # full / summary / names_only
    enable_retrieval: bool = True  # Morpheus L2 检索
```

#### 3.1.2 上下文组装器

```python
# core/context/assembler.py

class ContextAssembler:
    """多层上下文组装器——吸收 NovelAI 分层注入 + Morpheus 三层记忆"""
    
    def __init__(self, store: ProjectStore, config: ContextConfig = None):
        self.store = store
        self.config = config or ContextConfig()
    
    def assemble(self, project_id: str, user_input: str = "",
                 current_chapter: int = 0) -> str:
        """组装完整上下文——按层级优先级"""
        sections = []
        tokens_used = 0
        
        # L0: 项目元信息
        if self.config.layers[ContextLayer.PROJECT]:
            project = self.store.get_project(project_id)
            if project:
                section = self._format_project(project)
                tokens_used += self._count_tokens(section)
                sections.append(section)
        
        # L1: 角色档案
        if self.config.layers[ContextLayer.CHARACTERS]:
            characters = self.store.get_characters(project_id)
            section = self._format_characters(characters)
            if tokens_used + self._count_tokens(section) < self.config.max_tokens:
                tokens_used += self._count_tokens(section)
                sections.append(section)
        
        # L2: 最近章节摘要（按相关性检索）
        if self.config.layers[ContextLayer.RECENT]:
            chapters = self.store.get_chapters(project_id)
            # Morpheus L2: 根据当前场景关键词检索相关历史
            if self.config.enable_retrieval and user_input:
                relevant = self._retrieve_relevant(chapters, user_input)
                section = self._format_recent_chapters(relevant)
            else:
                recent = chapters[-self.config.recent_chapters:]
                section = self._format_recent_chapters(recent)
            if tokens_used + self._count_tokens(section) < self.config.max_tokens:
                tokens_used += self._count_tokens(section)
                sections.append(section)
        
        # L3: 情景记忆（Morpheus L2）
        if self.config.layers[ContextLayer.EPISODIC]:
            episodic = self._get_episodic_memory(project_id, current_chapter)
            if tokens_used + self._count_tokens(episodic) < self.config.max_tokens:
                tokens_used += self._count_tokens(episodic)
                sections.append(episodic)
        
        # L4: 派生记忆（Morpheus L3）
        if self.config.layers[ContextLayer.DERIVED]:
            derived = self._get_derived_memory(project_id)
            if tokens_used + self._count_tokens(derived) < self.config.max_tokens:
                tokens_used += self._count_tokens(derived)
                sections.append(derived)
        
        # L5: 用户输入（始终注入，最高优先级）
        if user_input:
            section = f"## 用户当前输入\n{user_input}"
            sections.append(section)
        
        return "\n\n".join(sections)
    
    def _retrieve_relevant(self, chapters: list[Chapter], query: str) -> list[Chapter]:
        """Morpheus L2: 按相关性检索历史章节"""
        # 简易实现：关键词匹配
        # 生产环境应使用向量检索
        keywords = set(query)
        scored = []
        for ch in chapters:
            score = sum(1 for kw in keywords if kw in ch.text[:500])
            if score > 0:
                scored.append((ch, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [ch for ch, _ in scored[:self.config.recent_chapters]]
    
    def _get_episodic_memory(self, project_id: str, chapter: int) -> str:
        """Morpheus L2: 情景记忆——章节摘要+状态变更"""
        # 从 AuditReport 中提取状态变更历史
        return f"## 情景记忆\n第{chapter}章状态"
    
    def _get_derived_memory(self, project_id: str) -> str:
        """Morpheus L3: 派生记忆——RUNTIME_STATE + OPEN_THREADS"""
        open_threads = self.store.get_open_foreshadowings(project_id)
        if not open_threads:
            return ""
        lines = ["## 派生记忆", "\n### 未闭合线索"]
        for t in open_threads[:10]:
            lines.append(f"- {t.description}（第{t.chapter_id}章埋下）")
        return "\n".join(lines)
    
    def _format_project(self, project: Project) -> str:
        return f"""## 故事设定
标题：{project.title}
类型：{project.genre}
前提：{project.premise}"""
    
    def _format_characters(self, characters: list[Character]) -> str:
        lines = ["## 角色档案"]
        for char in characters:
            beliefs = json.loads(char.beliefs_json) if char.beliefs_json else {}
            goals = json.loads(char.goals_json) if char.goals_json else []
            lines.append(f"\n### {char.name}（{char.role}）")
            if beliefs:
                lines.append("信念：")
                for prop, b in list(beliefs.items())[:5]:
                    if isinstance(b, dict):
                        lines.append(f"  - 相信「{prop}」= {b.get('value')} (置信度{b.get('confidence', 1.0):.0%})")
            if goals:
                lines.append("目标：")
                for g in goals[:3]:
                    lines.append(f"  - {g.get('description', g)}")
        return "\n".join(lines)
    
    def _format_recent_chapters(self, chapters: list[Chapter]) -> str:
        lines = ["## 最近章节"]
        for ch in chapters:
            summary = ch.text[:200] + "..." if len(ch.text) > 200 else ch.text
            lines.append(f"\n### 第{ch.number}章 {ch.title}")
            lines.append(summary)
        return "\n".join(lines)
    
    def _count_tokens(self, text: str) -> int:
        """简易 token 估算（中文约 1.5 字符/token）"""
        return len(text) // 2
```

---

### 3.2 大纲规划系统（Outline Planning System）

**目标**：从"无规划"升级为"递归分解 + 动态更新"（吸收 WriteHERE + GOAT + Dramatica + MICE）

#### 3.2.1 大纲数据结构

```python
# core/planning/outline.py

@dataclass
class OutlineNode:
    """大纲节点——支持递归嵌套"""
    id: str
    level: str  # "act" / "chapter" / "scene" / "beat"
    title: str
    description: str
    children: list["OutlineNode"] = field(default_factory=list)
    status: str = "planned"  # planned / writing / draft / revised / complete
    word_target: int = 0
    word_actual: int = 0
    methodology_source: str = ""  # 来自方法论注册表的标注
    
    # GOAT 故事值电荷
    story_value: str = "neutral"  # positive / negative / neutral
    story_charge: str = "none"  # positive_to_negative / negative_to_positive / none
    
    # Dramatica 四视角
    primary_pov: str = "objective"  # objective / main / impact / relationship
    
    # MICE 嵌套
    mice_type: str = ""  # milieu / idea / character / event
    mice_open_chapter: int = 0
    mice_close_chapter: int = 0
    
    # Freytag/Yorke 高潮位置
    climax_position: float = 0.0  # 0.0-1.0，0.625=Freytag，0.85=Yorke
    
@dataclass
class StoryOutline:
    """完整故事大纲"""
    project_id: str
    template: str  # "hero_journey" / "save_the_cat" / "three_act" / "story_circle"
    root: OutlineNode
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

#### 3.2.2 大纲生成器

```python
# core/planning/generator.py

class OutlineGenerator:
    """递归大纲生成器——吸收 WriteHERE + GOAT + Dramatica + MICE"""
    
    def __init__(self, llm_engine: LLMEngine, methodology_registry: MethodologyRegistry):
        self.llm = llm_engine
        self.methodology = methodology_registry
    
    def generate(self, premise: str, template: str = "three_act",
                 target_chapters: int = 30) -> StoryOutline:
        """从一句话前提生成完整大纲"""
        
        # 第一层：选择叙事框架
        template_config = self.methodology.get_template(template)
        
        # 第二层：生成宏观结构（幕/卷）
        macro = self._generate_macro_structure(premise, template_config)
        
        # 第三层：递归细化每个幕为章节
        for act in macro.children:
            chapters = self._generate_chapters_for_act(act, premise, target_chapters // len(macro.children))
            act.children = chapters
        
        # 第四层：标注 GOAT 故事值电荷
        self._annotate_story_values(macro)
        
        # 第五层：标注 Dramatica 视角
        self._annotate_povs(macro)
        
        # 第六层：标注 MICE 嵌套
        self._annotate_mice(macro)
        
        return StoryOutline(
            project_id="",
            template=template,
            root=macro,
        )
    
    def _annotate_story_values(self, node: OutlineNode):
        """GOAT: 为每个场景标注故事值电荷"""
        for child in node.children:
            # 根据描述判断故事值
            if any(kw in child.description for kw in ["胜利", "发现", "成长", "获得"]):
                child.story_value = "positive"
            elif any(kw in child.description for kw in ["失败", "损失", "打击", "失去"]):
                child.story_value = "negative"
            
            # 递归标注子节点
            self._annotate_story_values(child)
    
    def _annotate_povs(self, node: OutlineNode):
        """Dramatica: 为每个章节标注主视角"""
        povs = ["objective", "main", "impact", "relationship"]
        for i, child in enumerate(node.children):
            child.primary_pov = povs[i % 4]
            self._annotate_povs(child)
    
    def _annotate_mice(self, node: OutlineNode):
        """MICE: 为每个节点标注嵌套类型"""
        for child in node.children:
            if "世界" in child.description or "地点" in child.description:
                child.mice_type = "milieu"
            elif "问题" in child.description or "谜题" in child.description:
                child.mice_type = "idea"
            elif "成长" in child.description or "转变" in child.description:
                child.mice_type = "character"
            elif "事件" in child.description or "冲突" in child.description:
                child.mice_type = "event"
            self._annotate_mice(child)
```

---

### 3.3 风格引擎（Style Engine）

**目标**：从"无风格控制"升级为"学习用户文风 + 爆款对标"（吸收 AI-Novel-Prod + Novel-Engine）

#### 3.3.1 风格指纹提取

```python
# core/style/fingerprint.py

@dataclass
class StyleFingerprint:
    """风格指纹——L1-L4 四层量化"""
    # L1 词级
    function_word_spectrum: dict[str, float] = field(default_factory=dict)
    top_chars: list[tuple[str, float]] = field(default_factory=list)
    ttr: float = 0.0  # Type-Token Ratio
    
    # L2 句级
    mean_sentence_len: float = 0.0
    sentence_len_variance: float = 0.0
    punctuation_spectrum: dict[str, float] = field(default_factory=dict)
    
    # L3 篇章
    dialogue_ratio: float = 0.0
    paragraph_breath: float = 0.0
    sensory_channel_bias: dict[str, float] = field(default_factory=dict)
    
    # L4 叙事
    pov_preference: str = ""
    vocabulary_richness: float = 0.0
    syntactic_complexity: float = 0.0
    conflict_distribution: dict[str, float] = field(default_factory=dict)

class StyleExtractor:
    """风格指纹提取器——吸收 AI-Novel-Prod 的 StyleDNA"""
    
    def extract(self, text: str) -> StyleFingerprint:
        """从文本中提取风格指纹"""
        fp = StyleFingerprint()
        
        # L1: 词级统计
        fp.ttr = self._calc_ttr(text)
        fp.function_word_spectrum = self._calc_function_words(text)
        
        # L2: 句级统计
        sentences = self._split_sentences(text)
        lengths = [len(s) for s in sentences]
        fp.mean_sentence_len = sum(lengths) / max(len(lengths), 1)
        fp.sentence_len_variance = self._calc_variance(lengths)
        
        # L3: 篇章统计
        fp.dialogue_ratio = self._calc_dialogue_ratio(text)
        fp.sensory_channel_bias = self._calc_sensory_channels(text)
        
        # L4: 叙事统计
        fp.pov_preference = self._detect_pov(text)
        fp.vocabulary_richness = self._calc_vocab_richness(text)
        
        return fp
    
    def generate_style_prompt(self, fp: StyleFingerprint) -> str:
        """将风格指纹转换为生成指令"""
        instructions = []
        
        if fp.mean_sentence_len < 20:
            instructions.append("使用短句，节奏明快")
        elif fp.mean_sentence_len > 40:
            instructions.append("使用长句，节奏舒缓")
        
        if fp.dialogue_ratio > 0.4:
            instructions.append("对话驱动，增加人物互动")
        elif fp.dialogue_ratio < 0.1:
            instructions.append("叙述为主，减少对话")
        
        # 感官通道偏好
        top_sensory = sorted(fp.sensory_channel_bias.items(), key=lambda x: -x[1])[:2]
        if top_sensory:
            channels = "、".join([k for k, v in top_sensory if v > 0.1])
            if channels:
                instructions.append(f"侧重{channels}描写")
        
        return "风格要求：" + "；".join(instructions)
```

#### 3.3.2 Voice Profile（Novel-Engine 模式）

```python
# core/style/voice_profile.py

VOICE_INTERVIEW_QUESTIONS = [
    "你最喜欢的作家是谁？为什么？",
    "读一段你最喜欢的小说开头...",
    "你的句子通常偏短还是偏长？",
    "你喜欢用对话还是叙述推动故事？",
    "你的角色通常更内向还是外向？",
    "你偏好快节奏还是慢节奏？",
    "你常用第一人称还是第三人称？",
    "你的对话风格是直接的还是含蓄的？",
]

@dataclass
class VoiceProfile:
    """语音档案——通过引导式访谈捕获作者声音"""
    sentence_rhythm: str = ""  # "短句为主，偶尔长句"
    vocabulary_level: str = ""  # "通俗，偶尔文言"
    dialogue_style: str = ""  # "潜台词多，直接表达少"
    pacing: str = ""  # "快慢交替，紧张后必有缓冲"
    pov_preference: str = ""  # "第三人称限知"
    tone_preference: str = ""  # "冷静克制，偶有幽默"
    description_style: str = ""  # "感官细节，少用形容词"
    dialogue_ratio_target: float = 0.3

class VoiceProfileInterview:
    """引导式访谈生成 Voice Profile"""
    
    async def conduct_interview(self) -> VoiceProfile:
        """多轮对话收集作者偏好"""
        answers = []
        for q in VOICE_INTERVIEW_QUESTIONS:
            answer = await self._ask(q)
            answers.append(answer)
        
        # 使用 LLM 从回答中提取结构化 profile
        profile = await self._extract_profile(answers)
        return profile
    
    async def _extract_profile(self, answers: list[str]) -> VoiceProfile:
        """从访谈回答中提取结构化 Voice Profile"""
        prompt = f"""根据以下作者访谈回答，提取结构化的写作风格档案：

{chr(10).join(f"Q{i+1}: {a}" for i, a in enumerate(answers))}

输出 JSON：
{{"sentence_rhythm": "", "vocabulary_level": "", "dialogue_style": "", 
  "pacing": "", "pov_preference": "", "tone_preference": "", 
  "description_style": "", "dialogue_ratio_target": 0.3}}"""
        
        response = await self.llm.generate(prompt)
        # 解析并返回 VoiceProfile
        return VoiceProfile(**json.loads(response))
```

---

### 3.4 去 AI 味检测（InkOS 4 规则）

```python
# core/quality/ai_tell_detector.py

class AITellDetector:
    """去 AI 味检测——吸收 InkOS 的 4 条确定性规则"""
    
    HEDGE_WORDS = ["似乎", "可能", "或许", "大概", "某种程度上", "一定程度上", "在某种意义上"]
    TRANSITION_WORDS = ["然而", "不过", "与此同时", "然后", "接着", "因此", "所以"]
    
    def detect(self, text: str) -> list[dict]:
        """检测 AI 痕迹，返回问题列表"""
        issues = []
        
        # 规则 1: 段落均匀度
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if len(paragraphs) >= 3:
            lengths = [len(p) for p in paragraphs]
            mean = sum(lengths) / len(lengths)
            variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
            cv = (variance ** 0.5) / mean if mean > 0 else 0
            if cv < 0.15:
                issues.append({
                    "rule": "paragraph_uniformity",
                    "severity": "warn",
                    "message": f"段落长度过于均匀（变异系数 {cv:.2f}），建议增加长短变化",
                })
        
        # 规则 2: 模糊词密度
        hedge_count = sum(text.count(w) for w in self.HEDGE_WORDS)
        per_1000 = hedge_count / max(len(text) / 1000, 1)
        if per_1000 > 3:
            issues.append({
                "rule": "hedge_density",
                "severity": "warn",
                "message": f"模糊词密度过高（{per_1000:.1f}/千字），建议删除或替换",
            })
        
        # 规则 3: 公式化过渡
        for word in self.TRANSITION_WORDS:
            count = text.count(word)
            if count >= 3:
                issues.append({
                    "rule": "formulaic_transition",
                    "severity": "warn",
                    "message": f"过渡词「{word}」出现 {count} 次，建议替换或删减",
                })
        
        # 规则 4: 列表式结构
        sentences = re.split(r'[。！？\n]', text)
        openings = [s[:2] for s in sentences if len(s) > 3]
        for i in range(len(openings) - 2):
            if openings[i] == openings[i+1] == openings[i+2]:
                issues.append({
                    "rule": "list_structure",
                    "severity": "warn",
                    "message": f"连续 3 句以「{openings[i]}」开头，建议变化句式",
                })
        
        return issues
```

---

### 3.5 生成质量保障系统（Quality Assurance）

**目标**：从"100字门槛"升级为"多阶段生成 + 反馈循环"（吸收 Sudowrite + AnySpark）

#### 3.5.1 多阶段生成管线

```python
# core/generation/pipeline.py

class GenerationPipeline:
    """多阶段生成管线——吸收 Sudowrite 多变体 + AnySpark 8 阶段循环"""
    
    def __init__(self, llm_engine: LLMEngine, context_assembler: ContextAssembler,
                 style_extractor: StyleExtractor, gate_system: ConsistencyGateSystem):
        self.llm = llm_engine
        self.context = context_assembler
        self.style = style_extractor
        self.gates = gate_system
    
    def generate_with_quality(self, project_id: str, premise: str,
                               word_target: int = 500) -> GenerationResult:
        """带质量保障的生成——AnySpark 8 阶段循环"""
        
        # 阶段 1: 组装上下文
        ctx = self.context.assemble(project_id, premise)
        
        # 阶段 2: 获取风格指令
        project_text = self._get_project_text(project_id)
        if project_text:
            fp = self.style.extract(project_text)
            style_prompt = self.style.generate_style_prompt(fp)
        else:
            style_prompt = ""
        
        # 阶段 3-5: 生成→评估→修改（最多 3 轮循环）
        best_text = ""
        best_score = 0
        variants = []
        
        for attempt in range(3):
            # 生成 3 个变体
            for i in range(3):
                variant = self._generate_variant(
                    ctx, style_prompt, word_target, 
                    temperature=0.7 + i * 0.1
                )
                if variant:
                    variants.append(variant)
            
            # 评分
            scored = [(v, self._score_quality(v, project_id)) for v in variants]
            scored.sort(key=lambda x: x[1], reverse=True)
            
            if scored and scored[0][1] > best_score:
                best_text = scored[0][0]
                best_score = scored[0][1]
            
            # 如果分数 > 80，提前结束
            if best_score >= 80:
                break
            
            # 否则，基于反馈修改后重试
            feedback = self._generate_feedback(scored[0][0], project_id)
            ctx += f"\n\n## 修改建议\n{feedback}"
        
        return GenerationResult(
            text=best_text,
            score=best_score,
            variants=[v for v, s in scored],
            style_prompt=style_prompt,
        )
    
    def _score_quality(self, text: str, project_id: str) -> int:
        """质量评分（0-100）"""
        score = 100
        
        # 字数检查
        if len(text) < 100:
            score -= 30
        elif len(text) < 200:
            score -= 15
        
        # InkOS 去 AI 检测
        ai_issues = AITellDetector().detect(text)
        score -= len(ai_issues) * 5
        
        # 门禁检查
        gate_results = self.gates.pre_generation_check(text)
        for g in gate_results:
            if g.level == GateLevel.BLOCK:
                score -= 20
            elif g.level == GateLevel.WARN:
                score -= 10
        
        # 风格一致性（如果有历史文本）
        project_text = self._get_project_text(project_id)
        if project_text and len(project_text) > 500:
            fp_old = self.style.extract(project_text)
            fp_new = self.style.extract(text)
            style_diff = self._calc_style_diff(fp_old, fp_new)
            score -= int(style_diff * 20)
        
        return max(0, min(100, score))
```

---

## 四、门禁系统（18 道完整清单）

| ID | 名称 | 来源 | 优先级 |
|----|------|------|--------|
| G0 | CHANGES 协议 | Tianming | P0 |
| G1 | 事实一致性 | Æsirian | P0 |
| G2 | 信念一致性 | Æsirian ToM | P0 |
| G3 | 身份连续性 | Æsirian | P0 |
| G3+ | 轨迹平滑度 | CAE 论文 | P1 |
| G4 | 时间线一致性 | Æsirian | P0 |
| G5 | 空间一致性 | Æsirian | P0 |
| G6 | 因果链完整性 | Æsirian | P0 |
| G7 | 叙事节奏 | Æsirian | P0 |
| G7+ | 前 500 字钩子 | Netflix | P1 |
| G8 | 认知负荷 | Æsirian | P0 |
| G9 | 去 AI 4 规则 | InkOS | P0 |
| G10 | 现实效应 | Barthes | P1 |
| G11 | 控制幻觉 6 规则 | Storr | P1 |
| G12 | 微张力 5 问 | Maass | P1 |
| G13 | Show Don't Tell | 7 技法 | P1 |
| G14 | 视角切换 | Dramatica | P1 |
| G15 | MICE 嵌套 | Orson Scott Card | P1 |
| G16 | 场景电荷 | GOAT | P1 |
| G17 | 高潮位置 | Freytag/Yorke | P2 |
| G18 | 风格一致性 | StyleFingerprint | P1 |

---

## 五、前端架构重设计

### 5.1 组件结构

```
electron_ide/src/
├── App.tsx                    # 主应用壳（路由 + 全局状态）
├── stores/
│   ├── project-store.ts       # 项目状态
│   ├── editor-store.ts        # 编辑器状态
│   └── ui-store.ts            # UI 状态（面板开关/模式）
├── components/
│   ├── inspiration/           # 灵感视图
│   │   └── InspirationView.tsx
│   ├── writing/               # 写作视图（核心）
│   │   ├── WritingView.tsx
│   │   ├── Editor.tsx         # 富文本编辑器
│   │   ├── SuggestionPanel.tsx # 智能建议面板
│   │   └── AIContinueButton.tsx
│   ├── review/                # 审阅视图
│   │   ├── ReviewView.tsx
│   │   ├── ScoreCard.tsx
│   │   └── GateList.tsx
│   ├── panels/                # 折叠面板
│   │   ├── CharacterPanel.tsx  # 角色心智网格（Dramatica 四视角）
│   │   ├── WorldPanel.tsx      # 世界观 Wiki
│   │   ├── OutlinePanel.tsx    # 大纲面板（GOAT 电荷 + MICE）
│   │   ├── StylePanel.tsx      # 风格面板（Voice Profile + 指纹）
│   │   └── HistoryPanel.tsx    # 历史版本
│   └── shared/
│       ├── Toolbar.tsx
│       ├── StatusBar.tsx
│       └── GateBadge.tsx
└── hooks/
    ├── useAutoSave.ts
    ├── useSuggestions.ts
    └── useGateReport.ts
```

### 5.2 关键交互流程

#### 流程 1: 从灵感到写作

```
用户输入想法 → 点击"开始写作"
  ↓
系统调用 /api/generate-outline（生成大纲）
  ↓
进入写作视图，显示第 1 章编辑器
  ↓
用户输入文字 → 实时保存（debounce 2s）
  ↓
每 30 秒或段落结束后 → 自动刷新建议
  ↓
用户点击建议 → 插入编辑器
  ↓
用户按 Ctrl+Enter → AI 续写
```

#### 流程 2: AI 续写

```
用户按 Ctrl+Enter
  ↓
前端发送当前文本 + 上下文到 /api/ai-continue
  ↓
后端：
  1. ContextAssembler.assemble() → 多层上下文（NovelAI + Morpheus）
  2. StyleExtractor.extract() → 风格指令
  3. VoiceProfile → 作者声音
  4. GenerationPipeline.generate_with_quality() → 3 变体（AnySpark 循环）
  5. 返回最佳结果
  ↓
前端显示续写文本（差异高亮）
  ↓
用户选择：[采用] [修改] [重生成]
```

---

## 六、实施路线图（4 周）

### Week 1: 上下文工程 + 生成质量

| 任务 | 文件 | 验收 |
|------|------|------|
| ContextLayer 枚举 | `core/context/engine.py` | 单元测试通过 |
| ContextAssembler | `core/context/assembler.py` | 上下文组装正确 |
| Morpheus L2/L3 检索 | `core/context/assembler.py` | 相关性检索工作 |
| 多层注入 API | `bridge/api_server.py` | `/api/context` 返回分层上下文 |
| GenerationPipeline | `core/generation/pipeline.py` | 3 变体生成 + 评分 |
| 风格指纹提取 | `core/style/fingerprint.py` | 15+ 维度正确提取 |
| Voice Profile | `core/style/voice_profile.py` | 引导访谈 → 结构化 profile |
| InkOS 4 规则 | `core/quality/ai_tell_detector.py` | 4 类 AI 痕迹检测 |
| Netflix 5 秒钩子 | `core/consistency_gates/g7_hook.py` | 前 500 字冲突检测 |

### Week 2: 大纲规划 + 风格控制

| 任务 | 文件 | 验收 |
|------|------|------|
| OutlineNode 数据结构 | `core/planning/outline.py` | 递归嵌套 + GOAT/MICE/Dramatica 字段 |
| OutlineGenerator | `core/planning/generator.py` | 从前提生成 30 章大纲 |
| 大纲 API | `bridge/api_server.py` | `/api/generate-outline` 可用 |
| StyleExtractor → Prompt | `core/style/fingerprint.py` | 风格指令正确生成 |
| 风格绑定到生成 | `core/generation/pipeline.py` | 生成文本符合风格要求 |
| GOAT 故事值标注 | `core/planning/outline.py` | 场景电荷自动标注 |
| MICE 嵌套检查 | `core/consistency_gates/g15_mice.py` | LIFO 规则验证 |
| Dramatica 四视角 | `core/tom_engine/v2/throughlines.py` | 视角切换追踪 |

### Week 3: 前端重设计

| 任务 | 文件 | 验收 |
|------|------|------|
| 灵感视图 | `components/inspiration/` | 单输入框 + 开始按钮 |
| 写作视图 | `components/writing/` | 编辑器 + 建议面板 |
| 审阅视图 | `components/review/` | 评分 + 门禁列表 |
| 折叠面板 | `components/panels/` | 角色/大纲/世界观可展开 |
| 状态管理 | `stores/` | Zustand 三 store 就绪 |
| Barthes 现实效应 | `core/quality/reality_effect.py` | 抽象→具体建议 |
| Storr 控制幻觉 | `core/consistency_gates/g11_control.py` | 6 规则检查 |
| Maass 微张力 | `core/consistency_gates/g12_micro.py` | 段落级检测 |
| Show Don't Tell | `core/consistency_gates/g13_show_tell.py` | 7 技法检测 |

### Week 4: 集成测试 + 桌面打包

| 任务 | 文件 | 验收 |
|------|------|------|
| 端到端测试 | `tests/test_e2e.py` | 全流程通过 |
| Playwright 测试 | `tests/test_browser.py` | 19 项 UI 测试通过 |
| Electron 打包 | `electron-builder` | 安装包生成 |
| 一键验证脚本 | `verify-browser.ps1` | L1/L2/L3 全绿 |

---

## 七、验收标准

### 7.1 功能验收

- [ ] 用户能在 30 秒内从灵感到开始写作
- [ ] AI 续写字数 ≥ 300 字且符合上下文
- [ ] 建议带有方法论来源标注
- [ ] 心智网格可交互（点击角色看信念）
- [ ] 审计评分与门禁结果一致
- [ ] 风格一致性 ≥ 80%（同项目内）
- [ ] 去 AI 味检测 4 规则生效
- [ ] 大纲生成支持 GOAT/MICE/Dramatica

### 7.2 性能验收

- [ ] 上下文组装 < 500ms
- [ ] AI 续写响应 < 10s
- [ ] 建议刷新 < 3s
- [ ] 自动保存不阻塞输入

### 7.3 用户体验验收

- [ ] 新用户无需教程即可完成第一章
- [ ] 所有核心操作 ≤ 2 步
- [ ] 高级功能不干扰新手
- [ ] 专家模式可达全部功能

---

## 八、执行说明（给 opencode）

### 8.1 环境准备

```bash
cd <aesirian-repo-root>
pip install -r requirements.txt
```

### 8.2 执行顺序

严格按 Week 1 → Week 2 → Week 3 → Week 4 顺序执行。每周完成后运行测试，通过后再进入下周。

### 8.3 测试命令

```bash
# 单元测试
python -m pytest tests/ -v

# API 测试
python -m pytest tests/test_api_flows.py -v

# 浏览器测试（Windows only）
powershell -ExecutionPolicy Bypass -File verify-browser.ps1
```

### 8.4 关键依赖

```
sqlmodel>=0.0.14
fastapi>=0.100
uvicorn>=0.23
pydantic>=2.0
httpx>=0.28
```

---

> **本蓝图的核心理念：操作简洁 ≠ 功能简单。**
> 通过渐进披露和上下文感知，让新手觉得简单，让专家觉得强大。
> Æsirian 的世界级认知能力（ToM + 方法论 + 审计）是护城河——本蓝图让这些能力真正触达用户。
>
> **本蓝图已合并所有顶级项目精华、方法论、论文——可直接执行。**
