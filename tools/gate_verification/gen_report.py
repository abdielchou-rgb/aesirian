"""M2-3 门禁命中报告生成器 — 从 temp/m2_scan_results.json 生成 docs/gate-verification-report.md

用法: python tools/gate_verification/gen_report.py
"""
import json, os, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_JSON = os.path.join(ROOT, "temp", "m2_scan_results.json")
REPORT_MD = os.path.join(ROOT, "docs", "gate-verification-report.md")

R = json.load(open(RESULTS_JSON, encoding="utf-8"))
m = R["metrics"]
samples = R["samples"]
base = R["baseline"]

FAMILY_CN = {"S1": "人工植入", "S2": "AI历史输出", "S3": "边界"}

# ── 归类：净命中/零命中
zero = set(m["zero_delta_samples"])
# 语义特异 gate（在净命中中最有解释力的），按家族统计
semantic_ids = ["DLG-01","LANG-04","TPE-01","GDA-04","MTS-01","MTS-02","ROE-01","ROE-05",
                "SCQ-05","PRC-01","WNM-01","BRK-04B","MCO-01","STR-01","SPN-04","APL-01",
                "MRD-01","ARC-08","CTP-01"]
family_gate_hits = {}   # family -> {gate_id: cnt}
for s in samples:
    fam = family_gate_hits.setdefault(s["family"], {})
    for g in s["delta_gates"]:
        fam[g] = fam.get(g, 0) + 1

lines = []
A = lines.append
A("# 门禁命中报告（Gate Verification Report）")
A("")
A(f"- 生成时间：{R['meta']['scan_time']}")
A(f"- 门禁总数：{R['meta']['gates_registered']}（audit 全量）")
A(f"- 样本库：{R['meta']['samples_total']} 例（S1 人工植入 / S2 AI 历史输出 / S3 边界）")
A(f"- 体裁 Profile：{R['meta']['genres']} / {R['meta']['platform']}")
A("- 扫描入口：`AuditPipeline.run_full`（与线上 `analyze_chapter` 同一入口、同一裸上下文）")
A("")
A("## 1. 结论速览（回答 Feynman 之问）")
A("")
A("167 门禁在当前接入方式下**能拦住的**是结构/节奏/对话层缺陷；**拦不住的**恰恰是 AI 最常犯、作者最痛的一致性矛盾（时间/身份/空间/事实/称谓）。")
A("")
A("| 指标 | 数值 | 红线/说明 |")
A("|---|---|---|")
A(f"| 命中率 Recall（raw） | {m['recall']:.0%}（{m['hit_samples']}/{m['samples_total']}） | ≥3 类真实错误被 BLOCK ✓ |")
A(f"| **净命中率（去基线噪声）** | **{m['net_recall']:.0%}**（{m['net_hit_samples']}/{m['samples_total']}） | 样本产生干净文本没有的门禁信号 |")
A(f"| 误报率 FP（干净文本 BLOCK） | {m['fp_blocks_on_clean']}/166 = {m['fp_blocks_on_clean']/166:.1%} | ≤5% ✓（但见 §4 上下文饥饿） |")
A(f"| 零净命中样本 | {len(zero)}/32 | 这些错误类型当前完全无覆盖 |")
A(f"| SKIP 覆盖率 | 均值 {m['avg_skipped_per_sample']}/166 门禁跳过 | 进度/跨章门禁因无历史章节而 SKIP |")
A("")
A("## 2. 样本库构成")
A("")
A("| 族 | 例数 | 构造来源 |")
A("|---|---|---|")
A("| S1 人工植入 | 16 | 以《洛阳星港》第 1 章为基底改写：时间/身份/空间/事实矛盾、重复信息、情感直给、对话海、无冲突开场、章末平收、逻辑断裂、被动句、视角漂移、填充词、大纲式转述 |")
A("| S2 AI 历史输出 | 6 | 从 `tests/write_chapter_example.py` 第 2 章《因果》及生成文本特征抽取：前情复述、连续对话、意象重复、结尾说明化、信息倾倒、情感词高频、修饰语堆叠 |")
A("| S3 边界 | 10 | 空/超短/占位符/纯对话/超长单段/无标点/引号错乱/称谓漂移/全角异常/设定外物品 |")
A("")
A("样本明细数据：`tools/gate_verification/samples/m2_samples.json`；扫描明细：`temp/m2_scan_results.json`")
A("")
A("## 3. 问题一：哪些门禁真的拦住了错？（→ 保）")
A("")
A("口径：净命中 = 样本命中且干净第 1 章基线未命中（或同 gate 由 warn 升级为 block）。以下门禁对至少 1 例植入缺陷产生净信号：")
A("")
A("| 门禁 | 净命中例数 | 拦住的缺陷样本 |")
A("|---|---|---|")
gate_desc = {
    "DLG-01": ("对话无动作", ["S1-07","S1-15","S3-04","S3-07"]),
    "LANG-04": ("被动句/总结式叙述", ["S1-13"]),
    "TPE-01": ("情感词直给", ["S2-07"]),
    "GDA-04": ("超长单段无悬念间隔", ["S3-05"]),
    "MTS-01/MTS-02": ("微张力缺失", ["S3-05"]),
    "ROE-01": ("节奏异常", ["S3-05"]),
    "ROE-05": ("情绪词重复", ["S2-07"]),
    "SCQ-05": ("反应链异常", ["S2-07"]),
    "PRC-01": ("过程缺失", ["S2-07"]),
    "WNM-01": ("无语境叙述", ["S3-04","S3-05"]),
    "BRK-04B": ("段落钩子缺失", ["S3-04","S3-05"]),
    "MCO-01": ("单段信息过载", ["S3-04","S3-05"]),
    "STR-01": ("场景张力不足", ["S1-08","S1-12","S1-13","S1-15","S1-16","S3-02","S3-03"]),
    "SPN-04": ("悬念缺乏", ["S1-08","S1-12","S2-01","S2-05","S2-06","S2-08"]),
    "APL-01": ("前500字无冲突", ["S1-08","S1-12","S1-13","S1-15","S1-16"]),
    "MRD-01": ("语速/节奏", ["S1-08","S1-13","S1-16","S3-02","S3-05"]),
    "ARC-08": ("欲望-行动链", ["S1-08","S1-12","S1-13","S1-15","S1-16"]),
    "CTP-01": ("场景类型缺失", ["S1-08","S1-13","S1-16","S3-03","S3-06"]),
}
for gid in semantic_ids:
    if gid not in gate_desc:
        continue
    key = gid.split("/")[0]
    fams = []
    for fam in ("S1","S2","S3"):
        c = family_gate_hits.get(fam, {}).get(gid, 0)
        if c:
            fams.append(f"{fam}:{c}")
    desc, ex = gate_desc[gid]
    A(f"| {gid} | {len(ex)} | {desc}（例：{', '.join(ex[:4])}） |")
A("")
A("**判读**：真正有区分度的拦截集中在「对话动作穿插（DLG-01）」「被动/大纲式叙述（LANG-04/STR-01/MRD-01/CTP-01）」「开场无冲突（APL-01/SPN-04/G3-01）」「节奏异常（GDA-04/MTS/ROE-01）」四类。")
A("")
A("## 4. 问题二：哪些门禁从没拦住错 / 是纯噪音？（→ 裁/改候选）")
A("")
A("### 4.1 上下文饥饿误 BLOCK（应改为 SKIP 或补推导）")
A("")
A("| 门禁 | 现象 | 建议 |")
A("|---|---|---|")
A("| PLE-02 | 干净第 1 章被判「连续压抑 9 章」BLOCK；`gap_densities[-1] > 3` 时把单章 gap 信号数当作跨章压抑章数 | 无历史章上下文时 SKIP，或改由跨章情绪曲线驱动 |")
A("| G3-01 | 未提供 `first_conflict_position` 时默认 99999 → 几乎对所有纯文本 BLOCK（含干净文本） | 缺事件标注时 SKIP；接入 EntityExtractor/LLM 冲突锚点后再启用 |")
A("")
A("这两项导致干净文本 FP=1.2%（≤5% 红线内），但属于「测量噪音」而非真实缺陷拦截，会污染 Recall。")
A("")
A("### 4.2 装饰性门禁候选（基线噪音高、净区分度低）")
A("")
A("以下门禁在干净第 1 章也命中（BRK-03 短章、BRK-01B 段落无钩、QLT-04 节奏单一、DLG-02/DLG-03/DLG-06 对话、NEU-01/02/03、ARC-02/03/07、STR-03/06 等 24 条 warn），植入样本与基线响应几乎一致 → 对缺陷无区分度：")
A("")
A("> 短章主题：BRK-03、STR-06、QLT-04、BRK-01B\n> 情绪/钩子主题：NEU-01、NEU-02、NEU-03、ARC-02、ARC-03、ARC-07、CTP-02、SCQ-04\n> 对话主题（基线即命中，无净增量）：DLG-02、DLG-03、DLG-06、DLG-07、INR-01\n> 悬念主题（基线即命中）：SPN-02、QLT-05、DRM-01\n> 其他：PRP-02（第1章首钩 543 字 vs 150 规则，对短章/样张误报）、LANG-01（MRU 0/5 无锚点）")
A("")
A("候选处理：并入「仅当章长 ≥2000 字或提供跨章字段时启用」，或降为 info 级。**（本报告只列名，不执行——M4/V1.2 再动）**")
A("")
A("## 5. 问题三：哪些错误类型 167 门禁完全没覆盖？（→ 新增候选）")
A("")
A("以下 12 例植入缺陷**零净命中**——门禁把缺陷文本当「正常」放过：")
A("")
A("| 错误类型 | 样本 | 说明 |")
A("|---|---|---|")
A("| 时间线矛盾 | S1-01 / S1-11 | 「修了十一年→二十一年」、时长同一句摇摆，无门禁响应 |")
A("| 身份/对话者错位 | S1-02 | 角色台词互换、开价者错位 |")
A("| 空间矛盾 | S1-03 | 同一场景楼层 A-3 / B-7 混用 |")
A("| 事实/设定矛盾 | S1-04 | 协议编号前后不一致 |")
A("| 称谓漂移 | S3-08 | 主角名陈默→林默，全文替换后无感知 |")
A("| 重复信息 | S1-05 | 后段整句复述前段设定 |")
A("| 情感直给+过度解释 | S1-06 | 情绪全说破 + 长篇心理解释（TPE-01 只查高频词，未覆盖解释段） |")
A("| 逻辑断裂 | S1-10 | 明确拒绝后立刻照做、无动机转变 |")
A("| 视角漂移 | S1-14 | 限知视角下写出他人内心 |")
A("| 章末平收 | S1-09 | 强悬念铺垫被平收 |")
A("| 意象重复 | S2-04 | 同一章内同意象 3 次无新信息 |")
A("")
A("**根因**：一致性矛盾（SVT/IIT/DDT/CLM 等门禁）的入参依赖跨章事实/事件字段（`facts/events/identity_changes`），纯章节文本下 pipeline 未推导这些字段 → 门禁缺参即跳过/宽松通过；`EntityExtractor.to_gate_context` 已产出 `facts/identity_changes/movements` 但**未接回 AuditPipeline**。")
A("")
A("**新增候选（对 V1.2 有价值，M4 立项）**：")
A("1. 一致性桥接门禁：把 `EntityExtractor` 的 facts/identity_changes 注入 audit ctx，新增 `CSN-xx`（Character Setting Novelty）类对时间/空间/称谓做同段或跨章一致性校验；")
A("2. 重复信息门禁：n-gram/实体三元组同章去重检测（S1-05/S2-04）；")
A("3. 视角门禁：第三人称限知视角下出现非 POV 角色内心词库（恐惧/决定/其实他心里）触发 WARN（S1-14）；")
A("4. 动机门禁：拒绝→行动的反转需 1 个中间动机句（S1-10），可由规则或 LLM judge 提供。")
A("")
A("## 6. SKIP 覆盖率说明")
A("")
A("单章纯文本扫描均值 46/166 门禁 SKIP（进度门禁依赖章节历史、跨章事件与角色状态）。SKIP 不等同 PASS：报告中所有统计均已剔除 SKIP；**不可把 SKIP 误读为「门禁通过了」**。真实产品路径（`orchestrator.pre_generation_check` → consistency gates）不在本次 167 全量扫描范围，本报告只覆盖 AuditPipeline 单章接入形态。")
A("")
A("## 7. 附录：32 样本逐例净命中")
A("")
A("| 样本 | 族 | 缺陷 | 净命中门禁（delta） | BLOCK | WARN |")
A("|---|---|---|---|---|---|")
for s in samples:
    dg = ", ".join(s["delta_gates"]) if s["delta_gates"] else "—"
    A(f"| {s['id']} | {FAMILY_CN[s['family']]} | {s['flaw_type']} | {dg[:80]} | {s['delta_block']} | {s['delta_warn']} |")
A("")
A("---")
A("> 本报告只测量、不重构。裁/增/改门禁属 M4 / V1.2，避免「边测边改」污染基线。")

with open(REPORT_MD, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("written:", REPORT_MD, f"({len(lines)} lines)")
