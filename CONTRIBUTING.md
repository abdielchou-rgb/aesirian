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

`.github/workflows/ci.yml` 三个 job 均为**硬性全量 gate**：

1. **test job**：pytest × Python 3.10/3.11/3.12 + `tools/compat_matrix_check.py`。
2. **ruff job（全量）**：`ruff check core bridge tools tests mcp_server.py mcp_server_fast.py`。
   - select 已剔除 T20(print)/PTH(pathlib)（项目既有风格），并忽略 E501/E402/F403
     （长字符串/顶层 sys.path 延迟导入/registry 星号再导出）——细节见 `pyproject.toml`。
   - 静态检查只装 ruff，不装 torch —— 不要写需要 torch 导入的顶层语句。
3. **mypy job（core/ 全量）**：`mypy core/ --ignore-missing-imports`。
   - 基线 = strict_optional + 已注解代码全量严格检查；untyped def / 隐式 Optional / Any 返回为 legacy 豁免。
   - **新增/修改已注解代码不要引入新的 mypy 错误**；全量 untyped 补注（~600 项）列为 P1 技术债。
   - 库类型局限（pydantic-ai `Agent(output_type=...)`、SQLModel 映射列 `.desc()`、logfire stub）允许窄域
     `# type: ignore[<code>]` + 一行理由。

## 提交规范

- 用 Conventional Commits：`feat:` / `fix:` / `docs:` / `chore:` / `refactor:` / `test:`。
- 一个 PR 解决一个问题；PR 描述说明改动动机与验证方式。
- 不要提交：`*.db`、`node_modules`、`release*/`、`docs/internal/` 等（见 `.gitignore`）。
- 不要向公开仓加入任何第三方源码副本；借鉴请记录到 `docs/attribution.md`。

## 代码风格

- `ruff`：line-length 100；`mypy`：strict（`disallow_untyped_defs` 等见 `pyproject.toml`）。
- 中文文档/注释与代码混排时保持简洁；面向社区的新增说明用中文（与现有文档一致）。
