# Attribution & 版权来源声明

> 日期：2026-09-06 ｜ 对象：Æsirian 公开开源仓（0.2.0）
> 本仓以 **Apache-2.0** 授权（见根 LICENSE）。本文件说明代码/文本中所受外部启发、参考的第三方项目与来源，
> 以及哪些内容**未纳入**本仓。除下述声明外，本仓不含第三方代码副本。

---

## 1. 声明总则

- Æsirian 的核心引擎（ToM、文鉴门禁、四卡审查、一致性门禁等）为**本项目自研实现（原创代码）**。
- 若干设计受公开方法论/开源项目**启发**，启发不等于复制：本仓未包含被启发项目的源码文件。
- 公开开源前，曾完整参考的三个第三方仓库（见 §2）已**物理移出本仓**，仅在本机备份供研究，不随仓分发。

---

## 2. 第三方项目借鉴表（均未纳入本仓）

| 借鉴对象 | 出处 / 许可证 | 借鉴了什么 | 本项目形态 |
|---|---|---|---|
| InkOS（完整性写作系统） | 公开仓库；**AGPL-3.0**；未纳入本仓 | 「37 维审计 + 去 AI 味规则检测 + 时序记忆」的审计思想与维度动态构建思路 | 自研文鉴门禁（`core/wenjian/`，167 道门禁，`wenjian-methodology-v2.md` 记录设计）；仅思想启发，无代码复用 |
| Novel OS（叙事操作系统） | 公开仓库；未纳入本仓 | 规划模板 / 审计管线组织方式 | 自研 `core/craft/planner-templates/` 与门禁验证工具链；archive 内副本已移出 |
| Tianming（天明天命，私有一审参考） | 私有参考代码；未纳入本仓 | 「6 道门禁 + 15 维快照 + CHANGES 结构化变更声明」的分层门禁与变更协议思路 | 自研 `core/consistency_gates/` 与 CHANGES 协议（`core/changes_protocol.py`）；自研实现 |

> 补充说明：`reference_notes/absorbed_patterns.md` 是开发期对上述系统架构的**中文要点笔记**（原创概述性文字），
> 不含任何第三方代码片段，仅作为借鉴点留档；完整第三方源码不随本仓分发。

---

## 3. 方法论 / 出版物来源（文鉴门禁与写作引擎的理论根骨）

`core/wenjian/` 门禁系统与 `core/craft/` 方法论文档所参考的公开理论框架如下。**文中仅作观点引用与原创演绎，
未复制原文大段文字。**

| 框架 / 作者 | 出处 | 应用位置 |
|---|---|---|
| Shawn Coyne — Story Grid | Coyne, S. (2015). *The Story Grid* | 场景价值翻转（SVT）门禁 |
| Lisa Cron — Wired for Story | Cron, L. (2012). *Wired for Story* | 触点工程（TPE）、感官细节门禁 |
| John Truby — The Anatomy of Story | Truby, J. (2007). *The Anatomy of Story* | 角色弧线（ARC）、对手观、22 步 |
| Robert McKee — Story | McKee, R. (1997). *Story* | 三层冲突（CLM）门禁 |
| Donald Maass — 微张力 / The Fire in Fiction | Maass, D. (2010). *The Fire in Fiction* | 微观张力（MTS）门禁 |
| Blake Snyder — Save the Cat | Snyder, B. (2005). *Save the Cat* | 15 节拍表、阅读预备（PRP）、黄金三章 |
| 网文大师技法（中文网文行业经验） | 行业公开经验总结（断章/注水比/钩子散布/升级节奏/付费章节检测等） | 二次屏幕（NFR）、爽点工程（PLE）、黄金三章（G3）、断章（BRK）门禁 |
| Dramatica / 三幕·七点·英雄之旅 等结构模板 | 行业公开叙事结构理论 | `core/craft/planner-templates/` |

## 4. 文本与示例数据

| 内容 | 版权 | 说明 |
|---|---|---|
| 《洛阳星港》正文（含 `examples/luoyang/ch1.txt`） | **作者自创文本，版权归作者所有** | 仅作示例/演示数据随仓分发；Apache-2.0 仅覆盖代码，不覆盖该示例文本 |
| `pwa/demo/demo_luoyang_project.json`、`pwa/traces/` | 同上（由示例正文派生的演示/轨迹数据） | four_cards「加载演示」入口依赖 |

## 5. 使用建议

- 若你计划将 Æsirian 与 AGPL/GPL 代码合并或二次分发，请先咨询法律意见——本仓的 Apache-2.0 不与 AGPL 兼容混用。
- 若对本声明有任何遗漏或你认为存在未标注的借鉴，欢迎提 issue 更正。
