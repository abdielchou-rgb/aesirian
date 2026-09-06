# 顶层遗留代码存档（0.2.0 公开仓）

以下三份文件是 0.2.0 收敛前的**顶层遗留/旧版副本**，于公开开源时归档于此，
供 git 历史与代码演进追溯。**任何新代码不得引用它们**：

| 文件 | 说明 | 现行替代 |
|---|---|---|
| `__init__.py` | 早期 ToM 引擎 v1 快照（递归理论心智） | `core/tom_engine/` |
| `orchestrator.py` | 重构前的内存版 Orchestrator（约 331 行，无持久化/观测） | `core/orchestrator.py` |
| `nsef.py` | NSEF 叙事状态交换格式的旧副本（校验语义过严：强制要求未闭合线索） | `bridge/nsef.py` |

> 顶层 `nsef.py` 与 `orchestrator.py` 曾互为引用但均无活引用方；现行代码统一从
> `core/orchestrator.py` 出发，经 `bridge/` 路径解析 `nsef` 模块（见 `core/orchestrator.py:42-43`）。
> 若确需删除，本目录可直接移除（git 历史仍可追溯）。
