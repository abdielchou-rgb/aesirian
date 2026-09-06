# Æsirian — ToM-driven Human-AI Collaborative Fiction Engine

> 一个理解叙事的 AI 写作伙伴——在你需要时给你建议，不需要时安静陪伴。
> Æsirian 不只生成文本：它维护「作者意图 / 文本事实 / 读者体验」三重视角，
> 用理论心智（ToM）、一致性门禁与方法论注册表，把 AI 写作从"续写器"变成"可信的创作协作者"。

[![CI](https://img.shields.io/github/actions/workflow/status/abdielchou-rgb/aesirian/ci.yml?branch=main&label=CI&logo=github)](https://github.com/abdielchou-rgb/aesirian/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](pyproject.toml)

> 状态：CI badge 指向 `abdielchou-rgb/aesirian` 的 GitHub Actions；首个 commit 推送后 badge 生效。

## 这是什么

Æsirian 是一个**长篇叙事的 AI 协作写作引擎**。核心主张：叙事是
「作者意图 → 文本介质 → 读者体验」三极之间的全息协同；系统不替代任何一极，而是：

1. **保障协同的完整性** —— 一致性门禁 + 知识图谱，信息不丢失、不扭曲；
2. **降低协同的认知成本** —— 读者模型 + ToM 可视化，作者不被无关复杂度淹没；
3. **保留涌现与惊喜** —— 门禁区分「OOC 错误」与「弧光突变」，前者阻断、后者标记。

引擎含一个**自研的「文鉴」规则审计系统（145+ 门禁族）**、一套**递归理论心智（ToM）**
以及 30+ **方法论驱动的策略注册表**——不依赖云端模型也能给出结构化反馈，接上 LLM key 后自动增强。

## 核心能力

| 能力 | 说明 |
|---|---|
| 🧠 ToM 引擎 | 角色信念/目标/秘密建模，戏剧张力检测（信念冲突/反讽/递归错位/秘密暴露风险/目标冲突） |
| 🛡️ 文鉴门禁（145+） | 场景价值翻转、黄金三章、断章、爽点、触点工程、跨章一致性等，纯规则可离线 |
| 🔁 四卡双向联动 | 人物/框架/章节/试样四视图同屏，AI 改动以 diff 提案浮出，作者批准才落地（永不静默改写） |
| 📚 方法论注册表 | Campbell/Truby/McKee/Maass/Coyne 等 30+ 框架驱动发散、评价与审计 |
| 🗺️ 知识图谱 | 角色/地点/事件/物品/章节实体与关系，跨章一致性检查底座 |
| 👁️ 读者模型 | 沉浸度/认知负荷预测，告诉你"读者这里该喘口气了" |
| 🎨 风格指纹 | 六维风格雷达 + 比对与市场（虚词/词汇/句长/标点/对话/感官） |
| ⚡ 发散与推演 | 假设推演（克隆式不污染主线）、碎片发散多条世界线 |
| 🔌 多传输接入 | FastAPI REST + FastMCP（stdio/SSE/HTTP）+ Electron IDE + PWA 四卡页 |

## 快速开始（5 步）

要求：**Python 3.11+**（CI 覆盖 3.10/3.11/3.12，源码在仓库根运行、无需 editable 安装）。

```bash
# 1) 克隆
git clone <your-aesirian-remote-url>
cd aesirian

# 2) 安装依赖（含 torch/transformers 体积较大；仅跑核心可跳过 NER 相关再装）
python -m pip install -r requirements.txt

# 3) 无网络/未缓存模型时，测试环境变量（避免收集时去 HF Hub 拉模型卡死）：
#    Windows PowerShell: $env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"
#    bash: export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

# 4) 跑测试（109 项；L3 浏览器用例需 Windows + Electron 独立运行）
python -m pytest tests/ -q

# 5) （可选）生成/校验演示种子 —— 无数据库也能自举（--force 用 examples 正文重新生成）
python tools/seed_demo_data.py            # demo JSON 已随仓带 curated 版本，默认不覆盖
python tools/seed_demo_data.py --force    # 强制用 examples/luoyang/ch1.txt 重新生成
```

### 可选：接入 LLM 增强

任一环境变量：`DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ZHIPU_API_KEY` / `ANTHROPIC_API_KEY`，
或设 `OLLAMA_HOST` 用本地模型。无 key 时引擎自动降级为纯规则路径（门禁/ToM/读者模型永远可用）。

## 启动（四条路径）

| # | 启动什么 | 命令 | 访问 |
|---|---|---|---|
| 1 | **Core REST API**（FastAPI） | `python -m uvicorn bridge.api_server:app --host 127.0.0.1 --port 8765` | http://127.0.0.1:8765/docs |
| 2 | **Review 审查页**（四视图） | `python -m bridge.review_server` | http://127.0.0.1:8766 |
| 3 | **MCP server**（stdio/SSE/HTTP） | `python mcp_server_fast.py --transport http --port 8765`（或 `stdio`/`sse`） | HTTP 模式 MCP endpoint 在 8765（CORS-open，供本地 UI 调用）；`claude mcp add aesirian -- python mcp_server_fast.py --transport stdio` |
| 4 | **Electron IDE** | `cd electron_ide && npm install && npm run electron:dev` | 桌面窗口 |

> 说明：API 与 MCP HTTP 默认都用 8765——**同一时刻只启动其一**；Review 页固定 8766。
> 四卡演示页 `pwa/four_cards.html` 依赖 HTTP MCP 模式下的 demo 工具与 `pwa/demo/demo_luoyang_project.json`。

## 仓库结构

```
├── core/                 # 引擎（Python）：wenjian 门禁审计、tom_engine、knowledge_graph、
│                         #   consistency_gates、reader_model、four_cards+diff_engine、
│                         #   generation/planning、review、context、quality、style、strategies、persistence
├── bridge/               # 接入层：api_server(FastAPI)、review_server/review_api、nsef(NSEF 格式)
├── pwa/                  # 静态 PWA：dashboard、four_cards.html（四卡审查演示）
├── electron_ide/         # 桌面 IDE（React + Electron + Vite）
├── tools/                # seed_demo_data、gate_verification(M2 门禁自证工具集)、compat_matrix_check
├── tests/                # pytest 套件（109）+ L3 浏览器用例（独立运行）
├── plugins/              # 审计插件（叹号密度 / 被动语态检测）
├── examples/luoyang/     # 《洛阳星港》示例正文（作者自创，版权归作者；Apache 仅覆盖代码）
├── docs/                 # 用户指南、快速开始、蓝图、Attribution
│   ├── user-guide.md     # 功能与用法详解
│   ├── windows-quickstart.md
│   ├── engineering-blueprint-final.md / aesirian-v3-strategy.md   # 架构与战略公开文档
│   └── attribution.md    # 第三方借鉴 / 方法论出处 / 版权声明（必读）
├── mcp_server_fast.py    # FastMCP 多传输入口（stdio/SSE/HTTP）
├── Makefile / tox.ini    # 开发任务与 tox 矩阵
└── .github/workflows/ci.yml  # pytest × 3.10/3.11/3.12 + ruff/mypy 增量 gate
```

## 测试与质量

- `python -m pytest tests/ -q` → **109 passed**（`tests/l3_browser_test.py` 需 Windows+Electron，独立运行）。
- CI（GitHub Actions）三个硬性全量 gate：pytest × 3.10/3.11/3.12 矩阵 + `tools/compat_matrix_check.py` + `ruff check core bridge tools tests mcp_server*.py` 全量 + `mypy core/ --ignore-missing-imports` 全量。
- ruff select 剔除 T20/PTH（既有风格）并忽略 E501/E402/F403；mypy 基线 strict_optional + 已注解代码全量严格（untyped 补注列为 P1）——细节见 `pyproject.toml` 与 `CONTRIBUTING.md`。

## 示例与演示数据

- 《洛阳星港》第 1 章正文：`examples/luoyang/ch1.txt`（作者自创，版权归作者所有；仅作示例）。
- `pwa/demo/demo_luoyang_project.json`：curated 四卡演示资产（`seed_demo_data.py` 默认不覆盖，`--force` 可重生成）。
- 门禁自证样本：`tools/gate_verification/samples/`。

## 已知边界（Known gaps · 0.2.0）

- **真人内测数据回收中**：M3 真人写作循环走 0.2.x 迭代，与开源不互斥。
- **Windows 桌面安装包**：`Æsirian Setup 0.2.0.exe` 已随 GitHub Release 附赠（NSIS，x64，真机启动烟测通过）；L3 浏览器回归（Playwright）与多机型待 0.2.x 补跑。
- **mypy 全量 strict 补注**（core ~600 项）与 ruff 的 T20/PTH 风格迁移列为 P1 技术债；ruff/mypy 已启用**全量 CI gate**，新增代码被强制保持干净。

## 参与贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)：提交规范、测试要求、CI 语义。

## License

代码 **Apache-2.0**（见 [LICENSE](LICENSE)）；示例文本《洛阳星港》版权归作者所有（见 [docs/attribution.md](docs/attribution.md)）。
