"""四视图审查（review）模块 — 过渡状态（M1-5 · engineering-plan-v11.md）

⚠️ TRANSITIONAL — four-cards 命名收敛过渡标注
    产品概念已收敛：对外（UI/API/文档）统一使用「four_cards」概念名，
    对应实现为 core/four_cards.py + core/diff_engine.py（MCP 锚 + 提案制），
    v1.1 主界面为 pwa/four_cards.html（MCP 版），决策依据见
    docs/four-cards-naming-decision.md。
    本模块（REST 四视图 SyncEngine）保留仅为兼容既有桥接
    （bridge/review_api.py、bridge/review_server.py、electron_ide review.html）
    与既有测试（tests/test_review_engine.py），不作为 v1.1 对外界面演进，
    也不得新增双轨消费方；最终迁移 / 移除由 M3 后（V1.2）决策记录裁定。

提供：四视图状态模型（review/models.py）、双向同步引擎（sync_engine.py）、
审查会话存储（store.py）。设计上不依赖 Orchestrator，由 api_server 层负责
将 ProjectStore 数据适配为四视图状态并注入。
"""
