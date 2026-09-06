# Changelog

本项目采用 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 语义与 [SemVer](https://semver.org/lang/zh-CN/) 版本号。

## [0.2.0] - 2026-09-06

### 公开开源版（首个公开 tag）

- **Apache-2.0 公开开源**：`docs/attribution.md` 记录第三方借鉴与示例文本版权边界；第三方参考副本一律不入仓。
- **工程地基**：git 历史干净化、`.gitignore` / `.gitattributes`（LF 归一）、`CHANGELOG`、`README`、`CONTRIBUTING`。
- 顶层遗留旧代码归档至 `archive/legacy_top_level/`（旧版 `__init__.py`/`orchestrator.py`/`nsef.py` 均为死代码）。

### Added

- **NSEF（Narrative State Exchange Format）**：叙事状态打包/导入入口（`bridge/nsef.py`），供外部把故事种子交付给引擎。
- **文鉴（WenJian）145+ 一致性门禁**：场景价值翻转/激励事件/欲望双轨/冲突层次/触点工程/黄金三章/断章/爽点/微观张力等门禁族（`core/wenjian/`）。
- **四卡双向联动审查（Four-Card Review）**：人物小传/框架/章节/试样故事四视图同屏，AI 改动以 diff 提案浮出、作者批准才落地（铁律：永不静默改写）；`pwa/four_cards.html` + `demo_luoyang_project.json` 演示。
- **FastMCP 多传输 MCP server**（stdio/SSE/HTTP，CORS-open），取代旧 stdio-only server。
- **M2 门禁自证工具集**：`tools/gate_verification/`（样本库、全量门禁扫描、报告生成）。
- **CI**：GitHub Actions 三 Python 版本（3.10/3.11/3.12）测试矩阵 + ruff/mypy 变更文件增量 gate + 兼容矩阵校验。

### Changed

- 版本号 0.1.0 → 0.2.0（`pyproject.toml`、`electron_ide/package.json`、运行时可观测版本戳）。
- 示例正文独立为 `examples/luoyang/ch1.txt`；`tools/seed_demo_data.py` 默认不覆盖 curated 演示 JSON（`--force` 重新生成），无数据库环境下可自举。
- `forward_derive`：拒绝退化（空）的 LLM 结构化输出，自动回落到规则路径，保证四卡结构始终可用。
- **ruff 工程源码全量清零并切全量 CI gate**（select 剔除 T20/PTH、忽略 E501/E402/F403，见 pyproject）。
- **mypy core/ 全量清零并切全量 CI gate**（strict_optional + 已注解代码全量；untyped 补注列 P1）。
- 修复：`pydantic_ai_engine` 缺失 `track_llm_call`/`trace_chapter_generation` 导入（潜在 NameError）；`get_recommendations` 双分支返回类型不一致；动态插件加载 None 防护。

### Fixed

- 修复测试/收集在离线环境卡死问题（HF Hub 下载超时）：CI 与本地均设 `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE`，NER 无模型时快速降级到正则路径。

---

## [0.2.1] - 2026-09-07 深度审计修复（P0-P3 十三项）

> 依据：`docs/aesirian-audit-20260907.md` 深度审计。累计新增 **+55 测试**（109 → 164 passed），全量 ruff/mypy 绿。

### P0 产品真实性

- **门禁单一真源 registry**（P0-1）：`core/wenjian/audit/gates` 新增 `GATE_CATALOG`（含每门禁 params schema）、`GATE_TOTAL=167`、`gate_registry_stats()`；README/user-guide/API docstring/前端的历史手写数字（145+/166/167）全部对齐或改为 registry 派生——消除数字漂移，测试强制"文档数字==registry"。
- **`/audit` 默认 analysis-only**（P0-2）：新增 `AuditRequest{commit:bool}`，默认 dry_run 不落库不推进章节号（修复"审建议文本静默写入章节"）；`commit=true` 保留旧提交语义并标 deprecated；`orchestrator.audit_draft()` 用临时 gates 实例隔离副作用。
- **一致性桥 CSN**（P0-3）：新增 `core/csn_consistency.py`（中文数词归一化 + 数值事实扫描 + 跨章数值矛盾比对），修复"时间/年龄矛盾 0/12 检出"——"修了十一年→二十一年"、"三十岁→四十五岁"现在可 BLOCK；G6-G10 收到真实 reader_context（不再硬编码 0）。
- **真实执行路径图**（P0-4）：`docs/audit-execution-paths.md` 厘清文鉴167 / G1-G5 / G6-G10 / 跨章 / 质量五套系统的输入输出与调用者。

### P1 工程收敛

- **死门禁治理**（P1-5）：23 道注册却无 dispatcher 分支的门禁（STC-01..22 + RVI-06）从"静默假 PASS"改为显式跨章 SKIPPED + schema 自动绑定（提供 style_baseline 时真跑）；`safe_eval` 尾部静默 `pass_result` 移除。
- **退役旧 llm_engine / mcp_server**（P1-6）：生产调用方全部迁移到 `pydantic_ai_engine`（LLMEngineCompat 统一单例）；旧模块 import 即 DeprecationWarning；`LLMSuggestion` 提升为统一类型。
- **测试离线固化**（P1-7）：conftest 顶层设 HF offline env；新增 `sample_ch1_text` fixture 消除对运行端点的依赖。

### P2 数据与性能

- **chapters 复合唯一 + 幂等 upsert**（P2-8）：`(project_id, number)` 唯一约束；重复提交同章号覆盖而非插入幽灵章节；提交时落盘实体摘要，跨章一致性增量比对（消除 O(n²) 全量重提取）。
- **characters 唯一 + alembic 002 + 真实库迁移工具**（P2-9）：`(project_id, name)` 唯一约束 + `store.add_character` 幂等 upsert；`tools/migrate_p2_9.py` 交付（备份+幂等补索引，重复角色前置检查）——真实库 schema 由 create_all 生成，请显式运行该工具迁移，不自动改动。
- **runtime cache 版本化失效**（P2-10）：`store.project_revision()` 轻量指纹 + `_get_or_load_project` 命中时校验——外部写入者改库后自动丢弃陈旧缓存重载。

### P3 门禁科学 + 产品闭环

- **门禁降噪 + 精度回归**（P3-11）：23 道装饰性门禁在短章（<2000字）失败降为 INFO（不拉高报告状态），长章保留完整语义；PLE-02/G3-01 上下文饥饿误 BLOCK 治理为 SKIPPED——干净《洛阳星港》ch1 从 2 BLOCK → **0 BLOCK**；新增 `test_gate_precision_regression.py` 作 CI 精度回归门禁。
- **diff 决策遥测 + provenance 视图**（P3-12）：`apply_diff` 记录进程内决策日志；`four_cards_stats` MCP 工具暴露接受率/来源→去向分布；`four_cards.html` 新增"决策统计"面板与已裁决 provenance 列表（永不静默改写的可追溯层）。

### 已知遗留

- 真人作者 trace 回收（M3-3/6）仍是唯一硬阻塞；真人数据回收后跑 `tools/m4_analyze_traces.py` 重算覆盖 M4 报告。
- `tools/migrate_p2_9.py` 未在本机 `aesirian.db` 执行（保守），请在备份后显式运行以启用唯一约束。
- 门禁巨石（safe_eval 143 分支）已用死门禁检测 + schema 兜底治理，未做全量表驱动重写（P1-5 增量）。

---

## [0.1.0] - 内部里程碑快照（公开开源前，未发布 tag）

内部开发期里程碑的能力基线（以下均经 109 项 pytest 验证，未公开分发）：

### Core 引擎

- **ToM 引擎**：递归理论心智——角色信念/目标/秘密建模、戏剧张力检测（信念冲突/戏剧反讽/递归错位/秘密暴露风险/目标冲突）、冷却矩阵。
- **知识图谱（Knowledge Graph）**：角色/地点/事件/物品/章节节点 + 关系网络。
- **一致性门禁**：跨章一致性（事实矛盾/身份突变/信念冲突）自动检测；CHANGES 结构化变更协议。
- **读者模型（Reader Model）**：沉浸度/认知负荷预测，给作者"该缓缓"的建议。
- **方法论文档注册表**：30+ 叙事方法论驱动发散/评价/约束/审计策略选择（Campbell、Field、Truby、McKee、Maass、Coyne 等）。
- **规划与生成**：一句话前提 → 递归生成幕/章大纲（三幕/英雄之旅/救猫咪/故事圈等模板）；多变体章节生成 + 质量评分 + 反馈再生成。
- **风格系统**：六维风格指纹（虚词/词汇/句长/标点/对话/感官）、风格比对与市场。
- **叙事原子/发散**：假设推演（克隆式，不污染主线）、碎片发散多条世界线。
- **审校引擎（Review）**：`core/review/` 与四视图审查页（`bridge/review_server.py`，端口 8766）。

### 交互与工程

- **Core REST API**：`bridge/api_server.py`（FastAPI，项目/章节/角色/审计/导入导出，端口 8765）。
- **Electron IDE**（`electron_ide/`，React + Zustand + tiptap）双模式写作环境。
- **PWA Dashboard** 与四卡审查页（`pwa/`）。
- 旧 stdio MCP server（`mcp_server.py`，已标记 deprecated，仅测试兼容引用）。
- SQLite 持久化 + Alembic 迁移；结构化日志与可观测性。
- `tools/compat_matrix_check.py` 守护 M1-2 沙箱修复的 7 处跨版本兼容点。

---

[0.2.0]: #0.2.0---2026-09-06
[0.1.0]: #0.1.0---内部里程碑快照公开开源前未发布-tag
