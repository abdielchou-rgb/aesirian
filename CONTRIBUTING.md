# Contributing

感谢你考虑为 Æsirian 贡献代码。先读 [README](README.md) 与 [docs/attribution.md](docs/attribution.md)
（第三方借鉴与示例文本版权边界），再按下面约定提 PR。

## 开发环境

```bash
python -m pip install -r requirements.txt   # 或 uv sync
# 无网络/未缓存 HF 模型时：
#   export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
#   (PowerShell: $env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1")
```

源码在仓库根直接运行（`pytest` 从根收集 `tests/`），**不需要 editable 安装**。

## 测试

- 全量：`python -m pytest tests/ -q`（预期 **109 passed**）。
- L3 浏览器用例（`tests/l3_browser_test.py`）需 Windows + Electron，CI 不跑；改动 Electron/PWA 时请本机自跑。
- 涉及门禁/审计/示例正文路径的改动，检查 `tools/seed_demo_data.py --force` 仍可无 DB 自举。

## CI 语义（重要）

`.github/workflows/ci.yml`：

1. **test job**：pytest × Python 3.10/3.11/3.12 + `tools/compat_matrix_check.py` —— 硬性绿。
2. **ruff / mypy job**：当前为「变更文件增量 gate」：
   - 只对 PR 相对 `main` 改动的 Python 文件跑（`git diff origin/main...HEAD`）。
   - 全仓存量债（工程目录 ~1900 项 lint、`core/` ~410 项 mypy）**故意不为绿**，治理计划在 0.2.1
     清零后把 gate 切为全量。**新增代码请不要引入新的 lint/类型问题**；
     若你改动的文件本身带存量债，尽量顺手清理其所在函数/附近行，减少整体债务。
   - 静态检查只装 ruff/mypy，不装 torch —— 不要写需要 torch 导入的顶层语句。

## 提交规范

- 用 Conventional Commits：`feat:` / `fix:` / `docs:` / `chore:` / `refactor:` / `test:`。
- 一个 PR 解决一个问题；PR 描述说明改动动机与验证方式。
- 不要提交：`*.db`、`node_modules`、`release*/`、`docs/internal/` 等（见 `.gitignore`）。
- 不要向公开仓加入任何第三方源码副本；借鉴请记录到 `docs/attribution.md`。

## 代码风格

- `ruff`：line-length 100；`mypy`：strict（`disallow_untyped_defs` 等见 `pyproject.toml`）。
- 中文文档/注释与代码混排时保持简洁；面向社区的新增说明用中文（与现有文档一致）。
