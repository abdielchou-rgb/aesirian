# Æsirian 深度理解、审计与优化报告

- 日期：2026-09-07
- 范围：`D:\Claude\projects\aesirian`（main 分支，工作树干净）
- 性质：只读深度分析；本报告不包含任何代码改动
- 验证：`pytest` 109 passed（2:58，5 warnings，需离线环境变量）、`ruff` 全绿、`mypy core/` 全绿

> 注意：报告中引用的 `docs/internal/` 文件是**有意未入库（gitignore）的内部自证文档**，仅作审计依据引用，不构成提交风险。

---

## 1. 项目理解：它是什么

Æsirian 是一台「ToM 驱动的 人类 × AI 长篇小说协作引擎」，核心目标是维护「作者意图 → 文本 → 读者体验」三层结构，把 AI 从续写器变成守约的协作者。真正有产品价值的机制包括：

- **四卡提案 + diff 接受**：AI 提出改动（diff），作者接受才落地，永不静默重写（CHANGES 协议）；
- **递归理论心智（ToM）**：角色信念 / 目标 / 罗生门视角状态的运行时演化；
- **知识图谱（KG）**：章节快照、伏笔、世界观节点；
- **读者模型 / 冷却矩阵 / 风格指纹**：沉浸水平、爽点密度、作者语言指纹；
- **门禁与质量检测**：详见审计部分——宣传口径与真实路径并不一致。

### 1.1 工程事实

| 维度 | 事实 |
| --- | --- |
| 规模 | 约 136 个 `.py` / 约 3.17 万行源码 |
| 时间线 | 10 个 commit 全部落在 2026-09-06，0.2.0 单日收敛发布 |
| 测试 | 109 passed（2:58，5 warnings），CI 矩阵 Python 3.10/3.11/3.12 |
| 静态检查 | ruff 全量通过；mypy `core/` 全量通过（自认约 600 项补注债，列为 P1） |
| 存储 | SQLite + SQLModel；alembic 仅 1 个初始 migration |
| 自我认知 | `docs/internal/` 下 27 份内部自审文档（含门禁自证报告），全部 gitignore 未入库 |

### 1.2 真实架构（与文档宣传的对应关系）

文档宣传的四件大事，对应四条互不相同、且没有一条完全按宣传口径执行的路径：

1. 「145+/166/167 道文鉴门禁」→ 单章、零项目上下文的 `AuditPipeline`（纯规则审计）；
2. 「一致性门禁」→ 完全独立的另一套 **G1-G10**（`core/consistency_gates/`）；
3. 「跨章一致性」→ 第三个实现 `check_cross_chapter_consistency`（每次提交 O(n²) 全量扫历史章）；
4. 「质量检测」→ `core/quality` 五类检测，与上面三套均不同。

结论：与其说是一个引擎，不如说是四个彼此只部分打通的世界：`core/`（Python 研究式引擎）、`bridge/`（FastAPI 40+ 端点）、`electron_ide/ + pwa/`（React 壳 + 74KB 静态重型 UI）、`mcp_server_fast.py`（10 个 FastMCP 工具，旧 `mcp_server.py` 已标 deprecated 但仍存活）。

---

## 2. 深度审计

### 2.1 S1：产品真实性（宣传与运行不一致）

#### 2.1.1 门禁数字四处漂移

| 出处 | 数字 | 实际跑的是什么 |
| --- | --- | --- |
| [README.md](README.md:22) / :30 | 145+ | 文鉴「门禁族」宣传 |
| [user-guide.md](docs/user-guide.md:24) / :50 | 166 | 「提交章节后查看」的宣传 |
| [api_server.py](bridge/api_server.py:1063) | 166 | 实际是 G1-G5 `pre_generation_check` + G6-G10 + quality |
| [attribution.md](docs/attribution.md:21) | 167 | 文鉴自研门禁数 |
| [mcp_server_fast.py](mcp_server_fast.py:98) | 167 | 单文本 `AuditPipeline` |
| [wenjian-methodology-v2.md](core/wenjian/craft/wenjian-methodology-v2.md:14) | 145 | 文鉴方法论设计稿 |

数字自相矛盾，且不可核验：没有一处能从代码 registry 推导出宣传数字。

#### 2.1.2 审计端点有隐式写入副作用

[api_server.py](bridge/api_server.py:1059) 的 `/project/{id}/audit` 流程：

1. `pre_generation_check`（G1-G5，喂 `EntityExtractor.to_gate_context` 的实体上下文）；
2. **若没有 BLOCK，直接调用 `orch.submit_chapter(...)`** —— 即“审一段建议文本”会静默落库、推进章节号、触发 ToM/KG 更新；
3. BLOCK 分支的分数是临时拼凑的 `max(0, 100 - 20/10 × block)`。

风险：用户在探索建议文本时可能不知不觉写入章节，无法区分“试算”与“提交”。

#### 2.1.3 旗舰一致性门禁缺项目上下文、被硬编码掏空

[orchestrator.py](core/orchestrator.py:604) `submit_chapter` 只跑 G6-G10，且传入硬编码空上下文（[orchestrator.py](core/orchestrator.py:658)）：

- `plot_state={"open_threads": ...}`（仅开线程事件，无完整剧情状态）；
- `genre_contract={"required_scenes": []}`（永远空）；
- `reader_context={"new_characters": 0, "new_locations": 0, "pov_switches": 0}`（永远 0）。

内部自证报告 [gate-verification-report.md](docs/internal/gate-verification-report.md:86) 自己承认：

- 时间 / 空间 / 身份 / 事实 / 称谓类矛盾 **0/12 检出**；
- 根因（第 98 行）：一致性门禁的入参依赖跨章 `facts/events/identity_changes`，单章文本路径未推导这些字段，门禁缺参即跳过/宽松通过；
- `EntityExtractor.to_gate_context` 已产出这些字段，但**从未接回 AuditPipeline**；
- 报告第 101 行给出方向：新增 `CSN-xx`（Character Setting Novelty）一致性桥接门禁。

#### 2.1.4 文鉴 dispatcher 是上帝函数

[pipeline.py](core/wenjian/audit/pipeline.py:250) 的 `safe_eval`：

- 约 143 个 `if gid == ...` / `startswith` 分支；
- 混入硬编码实参：`NFR-03==""`、`RSM-01==('主角', True, False)`、`ARC-02==("生存","成长",0)` 等；
- gate catalog 定义与 dispatcher 分支两处维护，新增门禁需同时触碰两处，极易漂移。

### 2.2 S2：工程收敛度

#### 2.2.1 新旧双轨并存

- 旧 `llm_engine.py`（requests）仍在 [api_server.py](bridge/api_server.py:32)、orchestrator、`generation/pipeline.py`、`planning/generator.py`、`style/voice_profile.py` 中使用；文件头自注计划 V1.2 由 `pydantic_ai_engine` 接管后移除（[llm_engine.py](core/llm_engine.py:6)）；
- `mcp_server.py` 已标 deprecated 但仍存在于仓库与引用中；
- 四卡存在 REST（`electron_ide/public/review.html`）与 MCP（`pwa/four_cards.html`）两套前端；
- Distiller 双轨：顶层 `distill/` 为空，实现在 `pwa/distill/`。

#### 2.2.2 持久化契约自相矛盾

`_persist_character_state` 的 docstring 声称“角色在 characters 表中以角色名为 id（add_character(name, name) 约定）”（[orchestrator.py](core/orchestrator.py:708)），但：

- 真实 `add_character` 用 `id=uuid4().hex[:12]`（[store.py](core/persistence/store.py:294)）；
- 表主键是 `str id`（[models.py](core/persistence/models.py:62)）；
- docstring、实现、schema 三者不一致；`_persist_character_state` 只能按 name 反查再回写，同名角色会互相覆盖。

其他持久化问题：

- 运行时状态（ToM 信念 / KG 世界观节点）只活在 `_runtime_cache`（[orchestrator.py](core/orchestrator.py:127)），提交后才回写，进程重启前无版本/迁移保护；
- alembic 只有 1 个初始 migration（[001_initial.py](alembic/versions/001_initial.py)），models 无对应真实迁移链；
- 大量 JSON/Text blob 列（[models.py](core/persistence/models.py:135) / :169 / :170 / :185），JSON 与 `json.dumps` 字符串混用，反序列化散落 reader 侧；
- 盘上存在 3 个 `.db`（含 `test_aesirian_old.db` 遗留），全部 gitignore。

#### 2.2.3 安全与运维小事

- 两个服务 CORS 均 `allow_origins=["*"]`（[api_server.py](bridge/api_server.py:37)、[review_server.py](bridge/review_server.py:28)）——本地工具可接受，但公开发布前应收敛；
- 密钥接入方式正确：全部走环境变量（DEEPSEEK/OPENAI/ZHIPU/ANTHROPIC/GOOGLE），无硬编码密钥。

### 2.3 S3：产品与测试差距

- 蓝图承诺“写作 IDE”，但 [App.tsx](electron_ide/src/App.tsx:1) 只有 23 行，真正 UI 是约 74KB 静态 [dashboard.html](electron_ide/public/dashboard.html)；
- [pre_gates/__init__.py](core/wenjian/audit/pre_gates/__init__.py:15) 基类存在 `raise NotImplementedError` 空抽象，无后续跟踪；
- 测试需手动设置 `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1`（[README.md](README.md:52) 有记录但未脚本化），否则会进入 HuggingFace 挂死；
- 测试依赖 `/chapter-1-sample` 端点与共享样例，独立性与离线可复现性偏弱。

---

## 3. 网上顶级思考（2025-2026 主线）

### 3.1 HCI / 用户研究共识：控制点与归属感 > 一致性技术

「Where Do I 'Add the Egg?'」（University of Toronto, 2025，[arXiv 2509.15440](https://ar5iv.labs.arxiv.org/html/2509.15440)）通过 n=18 访谈得出：

- tool / agentic / magic 三种界面隐喻会塑造作者“在哪一步期待控制”；
- 归属感分为 stylistic / conceptual / effort 三型；
- 提供 provenance（改动溯源）能显著提升作者的 agency 与 ownership。

相关证据：Lee et al. 2022「写得越少，归属越弱」；TombWriter（ACM 2026）提出“ownership without voice”——作者有归属却无表达渠道。结论：**作者要的是能拒绝、能追溯、能回滚，而不是更多自动拦截**。Æsirian 的「四卡 + diff 接受 + 版本化」恰好踩中行业级需求，是最值得加注的资产。

### 3.2 学界范式：显式世界状态追踪 vs 递归/层级规划

2025 年的长篇小说生成研究集中在两大主线，**不存在“166 条启发式清单”流派**：

| 方法 | 核心机制 |
| --- | --- |
| SCORE | 符号逻辑动态状态追踪 + 上下文摘要纠错循环（[arXiv 2503.23512](https://ar5iv.labs.arxiv.org/html/2503.23512v1)） |
| DOME | 五阶段写作 + 动态层级大纲 + 时间知识图谱记忆 |
| WriteHERE | 递归任务分解，检索/推理/写作三类子任务自适应编排（Schmidhuber 团队，[EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1254/)） |
| FactTrack | 大纲内时间感知状态追踪 |
| GENOME | 多智能体 + 神经符号模拟 + 记忆演化 |
| MetaTron | 实体/记忆追踪 + 经典戏剧单元 + 人在环 |

启示：有效系统把少数高信号状态引擎做深，门禁应服务于真实事实类别，而不是横向堆维度。

### 3.3 商用工具现实：长期记忆必须作者可见可控

- **NovelAI**：Memory / Author's Note / Lorebook（激活键触发）+ context 拼装顺序可视化——把“长期记忆”做成作者可编辑的层；
- **Sudowrite**：Story Bible / Canvas / beat 级大纲，强调工具感而非对话感；其作者调研（引用 Gotham Ghostwriters 2025 调查：60% 认为提升质量、87% 认为提升效率）显示“切换自 ChatGPT”的核心动机是缺少创作专用工作流；
- **Anthropic / OpenAI**：长文实践收敛到“外部化 canon + 长上下文 + 自我反思/评估循环”（OpenAI 的 20 小时写作代理属公开演示，近似描述）；
- **开源生态**：`phase-fiction-skill`（中文，阶段链 + 文件系统记忆，[GitHub](https://github.com/nanzhipro/phase-fiction-skill)）、`lore-weave`（canon 校验必须来自已写文本、按世界隔离记忆）、`novel-bot`（filesystem as memory）、StoryDaemon（实体随故事演化）。

社区共识：**文本/事件即状态**，用磁盘文件或版本化事件承载中间态，而不是把中间态塞进不可审计的 JSON blob。

### 3.4 中国网文产业语境（方向性判断）

日更节奏下，追读率 / 章末钩子 / 断章是第一指标；平台侧工具（公开报道方向）走“作者工作台 + 设定素材库 + 合规预检”路线，全自动生成未成主流。B 端产品的有效信号是“设卡检查 + 辅助写作 + 作者控制”，而非“一键产文”。

---

## 4. 全面优化方案

### P0：产品真实性（3-5 天，零重写）

1. **单一真源门禁 registry**：建含真实可运行集合与 params schema 的 registry，README/MCP/API docstring 的数字全部派生自 registry；加测试断言“文档数字 == registry 实际数”。
2. **`/audit` 默认 analysis-only**：`dry_run` 语义，显式 `commit=true` 才写库；旧行为加 deprecated 警告。
3. **一致性桥**：把 `EntityExtractor` 的 `facts/identity_changes/movements` 注入 `AuditPipeline` 与 `post_chapter_audit`；用真实 KG/reader/plot 状态替换 G6-G10 硬编码空上下文（落实内部 M2 报告第 101 行的 CSN 建议）。
4. **真实执行路径图**：文鉴单章审计、G1-G5、G6-G10、cross-chapter、quality 各自的输入输出与调用者，作为产品与文档的共同底稿。

验收：数字 == registry、audit 不写库、植入矛盾可被检出。

### P1：工程收敛

5. `safe_eval` 表驱动化：registry dataclass + 每门禁独立单测 + “registry 有而 dispatcher 无”的死门禁检测。
6. 按项目自注的 V1.2 计划退役旧 `llm_engine.py` 与 `mcp_server.py`：shim import 即告警，加单测断言无人再 import。
7. `conftest.py` 统一设置 HF offline env；sample 章节改为 fixture，去掉对 `/chapter-1-sample` 的运行依赖。

### P2：数据与性能

8. `chapters` 增加 `(project_id, number)` 唯一约束与索引；cross-chapter 改为“每章提交时增量抽取实体摘要落盘”，消除每次提交 O(n²) 全量扫描。
9. alembic 出真实 baseline，再补迁移：character 主键 uuid + `(project_id, name)` 唯一索引，与 store 实现一致，消除 docstring/代码矛盾；热 JSON blob 拆独立查询表。
10. `_runtime_cache` 改为 per-project 版本号 + 提交后确定性失效；明确同名角色策略。

### P3：门禁科学与产品闭环

11. 按内部自证报告做门禁降噪：STR/APL/MRD/KFTC/ARC 等高误报类降为 info；优先把 12 类一致性矛盾做进 CSN；`tools/gate_verification` 精度回归进 CI。
12. 埋点“diff 接受率 / 回滚率”做周级门禁调参；前端补 provenance 视图（每条改动来自哪张卡、哪一章、是否被接受）。

---

## 5. 验证记录

- `pytest tests/ -q`：**109 passed，2:58，5 warnings**（需 `HF_HUB_OFFLINE=1` + `TRANSFORMERS_OFFLINE=1`）；
- `ruff check core bridge tools tests mcp_server*.py`：全部通过；
- `mypy core/ --ignore-missing-imports`：通过；
- 未启动完整 Web 服务 / Electron 桌面端（分析模式未做 UI 运行验证）；
- 本报告不包含任何代码改动，工作树保持干净。
