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

### Fixed

- 修复测试/收集在离线环境卡死问题（HF Hub 下载超时）：CI 与本地均设 `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE`，NER 无模型时快速降级到正则路径。

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
