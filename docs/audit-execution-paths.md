# Æsirian 门禁/审计真实执行路径图

> 日期：2026-09-07 ｜ 依据：深度审计 `docs/aesirian-audit-20260907.md` §1.2 + 代码逐行核验
> 目的：作为产品文档、README、issue 讨论的**共同底稿**——回答"代码里到底跑的是哪套门禁"。
> 口径：任何"当前 N 道门禁"表述一律派生自 `core/wenjian/audit/gates/gate_registry_stats()`（P0-1 单一真源，注册 167 道）。

---

## 0. 一句话

**Æsirian 不存在"一个门禁系统"——存在五条互不相同的审计路径，各自有独立的输入、调用者与输出。** 文档宣传中"145+/166/167 门禁"各自指代其中不同路径，这是历次数字漂移的根因。

---

## 1. 五条真实路径总览

```
                       ┌────────────────────────────────────────────────────┐
   作者/前端            │                                                    │
   ├─ 提交章节 ────────►│ submit-chapter (api) → Orchestrator.submit_chapter  │
   ├─ 试算 /audit ─────►│ audit (api, dry_run) → Orchestrator.audit_draft     │
   ├─ AI 续写建议 ─────►│ generation.pipeline → pre_generation_check (G1-G5)  │
   └─ MCP analyze ─────►│ mcp_server_fast → AuditPipeline.run_full (文鉴167)  │
                        └────────────────────────────────────────────────────┘

   每条路径内部会经过下表若干"门禁系统"：
```

| 路径 | 门禁系统 | 实现位置 | 输入 | 输出 | 调用者 |
|---|---|---|---|---|---|
| **A 文鉴单章审计** | 167 道文鉴门禁（纯规则） | `core/wenjian/audit/pipeline.py::AuditPipeline.run_full/run_realtime` | 单章文本 + 推导 ctx（`_enrich_context`） | `AuditReport{overall_status, gates[]}` | MCP `analyze_chapter`、`tools/gate_verification/`、`/audit` 旧全量口径 |
| **B 生成前门禁** | G1-G5 一致性（事实/信念/身份/时间/空间） | `core/consistency_gates/__init__.py::ConsistencyGateSystem.pre_generation_check` | 单段建议文本 + `EntityExtractor.to_gate_context` 实体上下文 | `list[GateResult]`（BLOCK 即拒绝） | `/submit-chapter` 前置、`/audit` 前置、`generation/pipeline`、`Orchestrator.validate_generated_text` |
| **C 章后门禁** | G6-G10（因果/节奏/认知负荷/去AI/冷却） | 同一 ConsistencyGateSystem 的 `post_chapter_audit` | 提交文本 + plot_state/genre_contract/reader_context/matrix_state（P0-3 后由 `_gate_entity_context` 提供真实 reader/plot 入参） | `AuditReport{overall_score, results[]}` | `Orchestrator.submit_chapter`、`audit_draft`（dry_run 用临时实例，不污染） |
| **D 跨章一致性** | 4 类矛盾检测（含 P0-3 新增 CSN 数值矛盾） | `core/orchestrator.py::check_cross_chapter_consistency` | 当前章文本 + store 历史章文本 | `[{type, severity, detail}]` | `submit_chapter`、`audit_draft`（读历史章，只读不写） |
| **E 质量检测** | 5 大检测器（现实效应/控制幻觉/微张力/Show Don't Tell/InkOS 4 规则） | `core/quality/__init__.py::QualityInspector.run_all` | 单段文本 | `list[issue]` | `/api/quality`、`/audit`、`/submit-chapter` 响应附带 |

> **易混点**：A（文鉴 167）与 B/C（G1-G10 一致性门禁）是两套完全独立的实现，分属 `core/wenjian/` 与 `core/consistency_gates/`。README 里"文鉴门禁 167"指 A；user-guide 里"提交章节看 166/167 门禁"实际展示的是 **B+C+D+E 的组合结果**，不是 A。

---

## 2. 各路径数据流（详细）

### 路径 A — 文鉴单章审计（MCP / 门禁自证入口）

```
输入: text
  → AuditPipeline._enrich_context(text)        # 推导 hook/触点数/情感/鸿沟等 ~20 个字段
  → AuditPipeline.run_full(ctx)                 # 遍历 GATE_CATALOG 全部 167 门禁
       ├─ 结构门禁缺跨章字段 → SKIPPED (passed=True, skipped=True)
       ├─ 进度门禁章节不足 → SKIPPED
       └─ 其余 → safe_eval(gate, ctx)           # 143 分支 gid 分发（P1-5 待表驱动化）
  → AuditReport{overall_status, gates[]}
输出: pass/warn/block 分级结果
```

### 路径 B — 生成前门禁 G1-G5（提交/续写网关）

```
输入: text + EntityExtractor.to_gate_context(text)
      {facts, char_actions, identity_changes, events, movements}
  → ConsistencyGateSystem.pre_generation_check(text, ctx)
      G1 fact / G2 belief / G3 identity / G4 timeline / G5 spatial
  → list[GateResult]      # 任一 BLOCK → 拒绝提交/显示
```

### 路径 C — 章后门禁 G6-G10（提交链）

```
输入: text
  → Orchestrator._gate_entity_context(text)      # P0-3: 真实 reader_context/plot_extra
  → ConsistencyGateSystem.post_chapter_audit(text, plot_state, genre_contract,
       reader_context, matrix_state)
      G6 causal / G7 rhythm / G8 cognitive / G9 deai / G10 cooldown
  → AuditReport{overall_score, results[]}
```

### 路径 D — 跨章一致性（每次提交）

```
输入: current_text
  → store.get_chapters(project_id)               # 历史章
  → _extract_entities(current_text) + 各历史章   # 实体提取（regex 优先 / transformers 回退）
  → 四类检测:
      1 fact_contradiction        (数字事实 subject+predicate 值不同)
      2 identity_shift_unexplained(身份变化无解释)
      3 belief_contradiction      (文本否定既有信念)
      4 csn_numeric_contradiction (P0-3: 中文数词归一化跨章比对, BLOCK)
  → [{type, severity, detail, current_chapter, conflict_chapter}]
```

### 路径 E — 质量检测（聚合）

```
输入: text → QualityInspector.run_all(text)
  → reality_effect + control_illusion + micro_tension + show_dont_tell + inkos 规则
输出: list[issue]
```

---

## 3. 前端 / API 实际消费哪些路径

| 入口 | 方法 | 内部路径 | dry_run 语义 |
|---|---|---|---|
| `POST /project/{id}/submit-chapter` | **提交** | B（预检）→ C+D（提交链）→ E（响应附带） | 否（真实落库） |
| `POST /project/{id}/audit` | **试算** | B（预检）→ C（临时实例）+ D（只读）→ E | **是**（P0-2 后默认不落库；`commit=true` 走提交并标 deprecated） |
| `POST /project/{id}/validate` | 生成校验 | B（G1-G5） | 否 |
| `POST /api/quality` | 质量 | E | 否 |
| MCP `analyze_chapter` | 单章全量 | A | 否 |
| `POST /api/generate-with-quality` | 续写带质检 | B + E | 否 |
| `tools/gate_verification/` | 门禁自证 | A | 否 |

---

## 4. 已知口径速查（给文档/issue 作者）

| 你要表达的东西 | 正确的说法 | 别再说 |
|---|---|---|
| 文鉴规则审计系统 | 「文鉴门禁（registry 单一真源，167 道）」 | 「145+」「166」 |
| 提交章节后作者看到的门禁 | 「一致性门禁 G1-G10 + 跨章一致性 + 质量检测」 | 「166 道门禁」 |
| MCP/全量单章审计 | 「全量文鉴门禁」 | 硬编码数字 |
| 设计稿基线 | 「V2 设计基线 145 + STC 风格一致性 22 = 167」 | 把 145 当当前数 |

---

> 维护说明：本文档随代码演进更新。若你改动任一"门禁系统"的输入/输出/调用者，请同步本图。
> 门禁总数以 `wenjian.audit.gates.GATE_CATALOG` 为准；一致性测试在 `tests/test_gate_registry_consistency.py`。
