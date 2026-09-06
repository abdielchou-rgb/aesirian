# 同行代码吸收参考笔记

## Tianming —— 6道门禁 + 15维快照

### 核心模式：CHANGES 声明系统
- AI生成每个章节时必须在末尾附加结构化JSON变更声明
- 支持4种格式：XML块、`---CHANGES---`标记、`### CHANGES`头、尾部JSON
- 12个顶层字段：CharacterStateChanges, ConflictProgress, NewPlotPoints, ForeshadowingActions, LocationStateChanges, FactionStateChanges, TimeProgression, CharacterMovements, ItemTransfers, SecretRevealChanges, PledgeConstraintChanges, DeadlineConstraintChanges

### 6道门禁管线
1. **协议验证** — 找到CHANGES区域→修复JSON→验证12个字段全部存在→检测伪造ID
2. **ShortId引用验证** — 所有实体ID须在账本中存在（9种实体类型）
3. **一致性检查(V1-V6)** — 伏笔不能回收后重新埋设、冲突状态须顺序推进、角色升级不能倒退、移动轨迹连续性、物品持有者匹配、同一对角色不能同时是盟友和敌人
4. **未知实体检测** — 扫描正文中未在账本的实体名，区分功能和背景实体
5. **描述一致性** — 发色/性格/特征比对
6. **世界观硬约束** — 检查"不能/不可/禁止"规则是否被违反

### 15维快照
CharacterStates, ConflictProgress, ForeshadowingStatus, PlotPoints, CharacterDescriptions, LocationDescriptions, WorldRuleConstraints, LocationStates, FactionStates, Timeline, CharacterLocations, ItemStates, SecretStates, PledgeStates, DeadlineStates

### 上下文组装
- 33,000字符预算硬上限
- 5-6个数据加载任务并发执行
- 超出预算时降级（完整→缩写版本）
- 实体过滤：卷级只包含卷引用的实体，章节级增加临近章节钩子(-3到+2)
- 依赖树：模板→世界观→角色→势力→地点→情节

### 实体引用系统
- 13字符ShortId格式 `[A-Z][0-9A-Z]{12}`
- ShortIdFieldRegistry定义18个字段路径映射9种实体类型
- 伪造ID检测：>=5个且>=80%为伪造则硬否决

---

## SAGA —— 知识图谱模式

### 图结构
- 严格5节点标签：Character, Location, Event, Item, Chapter（子类型通过category属性存储）
- 18种关系类型：ALLIES_WITH, RIVALS_WITH, CONFLICTS_WITH, LOVES, FAMILY_OF, MENTORS, PROTECTS, TRUSTS, DISTRUSTS, BETRAYS, FEARS, SEEKS, LOCATED_AT, SERVES, DEPENDS_ON, OWES, DECEIVES, MANIPULATES
- 标签归一化：Person/Creature→Character, Place/City→Location, Object/Artifact→Item, Scene/PlotPoint→Event

### 写入模式
- 角色通过 `MERGE (c:Character {name: $name})` 确保幂等
- world元素通过 `MERGE (w:{label} {id: $id})`
- 关系目标不存在时创建为 `is_provisional=true` 的临时节点

### 矛盾检测
- 30对硬编码矛盾特质（introverted↔extroverted等）
- 角色特质比对 + 情节停滞检测（字数<1500/无新事件/无新关系）+ 关系验证

### 图修复
- 临时节点生命周期：创建→丰富化（LLM推断属性）→毕业（置信度>=0.75且年龄>=1章）
- 重复合并：Levenshtein相似度+嵌入余弦相似度+共现检查
- 孤立节点清理：超过3章且无关系的临时节点

### 场景级上下文
6个组件：场景角色轮廓+KG事实+摘要+前几幕+位置上下文+语义搜索

---

## InkOS —— 37维审计 + 去AI味 + 时序记忆

### 37维审计
- 动态构建：起始于genre配置+书级附加维度+总是启用维度32/33
- 衍生模式条件激活不同维度集
- 输出：AuditResult { passed, issues[], summary, overallScore }
- Issue: { severity: critical|warning|info, category, description, suggestion, repairScope }

### 去AI味检测（纯规则无LLM）
1. **段落均匀度** — 段落长度变异系数<0.15标记
2. **模糊词密度** — >3/千字标记
3. **公式化过渡** — 同个过渡词>=3次标记
4. **列表式结构** — 连续3句同样开头标记

### 时序记忆（SQLite）
- facts表：subject, predicate, object, valid_from_chapter, valid_until_chapter
- hooks表：hook_id, start_chapter, type, status, last_advanced_chapter, expected_payoff
- 查询：getCurrentFacts(), getFactsAt(subject, chapter), getFactHistory(subject)

### 状态模式
- Zod验证4个JSON文件：manifest.json, current_state.json, hooks.json, chapter_summaries.json
- 不可变状态归约器：`applyRuntimeStateDelta()` 克隆快照→验证→应用操作→再验证
- RuntimeStateDelta：{ chapter, currentStatePatch, hookOps, newHookCandidates, chapterSummary }

### 10-agent管线
Plan→Write→Normalize→Review Cycle(assess→revise→reassess)→Hook Promotion→Persistence→Notification
评分>=85且通过检查才能通过，最多重试次数后取最佳快照

---

## 对我们架构的关键启发

1. **Tianming的CHANGES声明系统** — 强制AI告知它改变了什么，比我们自行从文本中提取更可靠
2. **Tianming的预算管理** — 33000字符硬上限+降级策略，适合我们长篇小说上下文管理
3. **SAGA的临时节点生命周期** — provisonal→enrich→graduate，适合我们角色的涌现式创建
4. **SAGA的图修复(共现检查)** — 避免合并不应合并的实体
5. **InkOS的37维审计动态构建** — 按类型和模式激活不同维度，非全量维度
6. **InkOS的去AI味规则检测** — 纯确定性算法，零LLM成本
7. **InkOS的不可变状态归约器** — Zod验证+clone+apply+revalidate模式
