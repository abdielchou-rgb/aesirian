"""M2-2 全量门禁扫描器 — 对样本库逐例跑 167 门禁并输出命中明细。

用法: python tools/gate_verification/scan_gates.py
产物:
  - temp/m2_scan_results.json   (逐样本×逐门禁明细)
  - docs/gate-verification-report.md  (Markdown 报告)
"""

import datetime
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, ROOT)

from wenjian.audit.gates import ALL_GATES
from wenjian.audit.pipeline import AuditPipeline

SAMPLES_JSON = os.path.join(ROOT, "tools", "gate_verification", "samples", "m2_samples.json")
RESULTS_JSON = os.path.join(ROOT, "temp", "m2_scan_results.json")
REPORT_MD = os.path.join(ROOT, "docs", "internal", "gate-verification-report.md")
GENRE = "suspense"
PLATFORM = "webnovel"

# 基线干净文本（洛阳星港第1章 707 字）作为 FP 对照
with open(os.path.join(ROOT, "examples", "luoyang", "ch1.txt"), encoding="utf-8") as _f:
    BASELINE_TEXT = _f.read().strip()


def scan_text(text: str, chapter_index: int = 0) -> list:
    p = AuditPipeline(genre_id=GENRE, platform=PLATFORM)
    ctx = {
        "chapter_text": text,
        "chapter_index": chapter_index,
        "chapter_number": chapter_index + 1,
        "platform": PLATFORM,
        "genre_id": GENRE,
    }
    rep = p.run_full(ctx)
    return [
        {
            "gate_id": r.gate_id,
            "name": r.name,
            "severity": r.severity.value,
            "passed": bool(r.passed),
            "skipped": bool(r.skipped),
            "message": r.message[:200],
        }
        for r in rep.gate_results
    ]


def _active_hits(results: list) -> list:
    """有效命中 = block/warn 失败（排除 info 降噪与 skipped）。"""
    return [r for r in results if not r["passed"] and not r["skipped"] and r["severity"] in ("block", "warn")]


def summary(results: list) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r["passed"] and not r["skipped"])
    skipped = sum(1 for r in results if r["skipped"])
    blocked = sum(
        1 for r in results if not r["passed"] and not r["skipped"] and r["severity"] == "block"
    )
    # P3-11: info 级（装饰门禁降噪）不计入 warned——它不是缺陷特异信号
    warned = sum(
        1 for r in results if not r["passed"] and not r["skipped"] and r["severity"] == "warn"
    )
    active = total - skipped
    return {
        "total": total,
        "passed": passed,
        "skipped": skipped,
        "blocked": blocked,
        "warned": warned,
        "active": active,
    }


def main():
    with open(SAMPLES_JSON, encoding="utf-8") as _f:
        samples = json.load(_f)
    print(f"samples: {len(samples)} | gates: {len(ALL_GATES)}")

    # 1) 干净基线（FP 参考）
    baseline = scan_text(BASELINE_TEXT, 0)
    base_summ = summary(baseline)

    # 2) 基线噪声门禁集合（干净文本亦命中 → 非缺陷特异）
    base_hit_ids = {r["gate_id"] for r in _active_hits(baseline)}
    base_hit_by_id = {r["gate_id"]: r for r in _active_hits(baseline)}

    # 3) 逐样本扫描（净新增 = 样本命中 - 基线命中）
    scanned = []
    t0 = time.time()
    for i, s in enumerate(samples, 1):
        res = scan_text(s["text"], 0)
        summ = summary(res)
        hit_gates = _active_hits(res)
        delta = []
        for r in hit_gates:
            if r["gate_id"] in base_hit_ids:
                # 基线也命中：仅当严重度升级（warn→block）才算净增量信号
                b = base_hit_by_id[r["gate_id"]]
                if r["severity"] != "block" or b["severity"] == "block":
                    continue
            delta.append(r["gate_id"])
        scanned.append(
            {
                "id": s["id"],
                "family": s["family"],
                "flaw_type": s["flaw_type"],
                "title": s["title"],
                "note": s["note"],
                "summary": summ,
                "hit_gates": [r["gate_id"] for r in hit_gates],
                "delta_gates": delta,
                "delta_block": sum(
                    1 for r in hit_gates if r["gate_id"] in delta and r["severity"] == "block"
                ),
                "delta_warn": sum(
                    1 for r in hit_gates if r["gate_id"] in delta and r["severity"] == "warn"
                ),
                "results": res,
            }
        )
        if i % 8 == 0:
            print(f"  scanned {i}/{len(samples)} elapsed={time.time() - t0:.1f}s")

    # 4) 净新增命中样本数 / 特异性门禁统计
    net_hit_samples = [x for x in scanned if x["delta_block"] + x["delta_warn"] > 0]
    net_recall = len(net_hit_samples) / len(scanned)
    delta_stats = {}
    for x in scanned:
        for gid in x["delta_gates"]:
            delta_stats[gid] = delta_stats.get(gid, 0) + 1

    # 5) 汇总指标
    hit_samples = [x for x in scanned if x["summary"]["blocked"] + x["summary"]["warned"] > 0]
    recall = len(hit_samples) / len(scanned)
    fp_blocks = base_summ["blocked"]

    # 单门禁有效率: 每个 gate 在 S1/S2 植入样本中命中数（BLOCK/WARN）
    gate_stats = dict.fromkeys(ALL_GATES, 0)
    for x in scanned:
        for gid in x["hit_gates"]:
            gate_stats[gid] += 1
    useful_gates = {gid: c for gid, c in gate_stats.items() if c > 0 and gid != "SKIPPED"}
    specific_gates = dict(delta_stats)

    # 记录 SKIP 覆盖: 各样本平均 skipped 门禁数
    avg_skipped = round(sum(x["summary"]["skipped"] for x in scanned) / len(scanned), 1)

    result = {
        "meta": {
            "genres": GENRE,
            "platform": PLATFORM,
            "gates_registered": len(ALL_GATES),
            "samples_total": len(samples),
            "scan_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "baseline": {
            "text": BASELINE_TEXT[:40],
            "summary": base_summ,
            "baseline_hits": _active_hits(baseline),
        },
        "metrics": {
            "recall": round(recall, 4),
            "hit_samples": len(hit_samples),
            "net_recall": round(net_recall, 4),
            "net_hit_samples": len(net_hit_samples),
            "samples_total": len(scanned),
            "fp_blocks_on_clean": fp_blocks,
            "avg_skipped_per_sample": avg_skipped,
            "useful_gates_count": len(useful_gates),
            "useful_gates_top": sorted(useful_gates.items(), key=lambda kv: -kv[1])[:40],
            "specific_gates_top": sorted(specific_gates.items(), key=lambda kv: -kv[1])[:30],
            "zero_delta_samples": [
                x["id"] for x in scanned if x["delta_block"] + x["delta_warn"] == 0
            ],
        },
        "samples": scanned,
    }
    os.makedirs(os.path.dirname(RESULTS_JSON), exist_ok=True)
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("results written:", RESULTS_JSON)
    print(
        f"recall={result['metrics']['recall']} | hit={hit_samples.__len__()}/{len(scanned)} | fp_block={fp_blocks} | useful_gates={len(useful_gates)} | avg_skip={avg_skipped}"
    )


if __name__ == "__main__":
    main()
