#!/usr/bin/env python3
"""
m4_analyze_traces.py — M4 验收核算脚本（AI 模拟/真人 trace 通用）

读取 four_cards.html 前端 localStorage 导出的 trace JSON 文件（数组，事件形如
{"op": ..., "ts": "<ISO8601>", "detail": {...}}），逐份统计并输出 JSON。

统计口径（与 docs/m3-human-recruit-and-run-guide.md 对齐）：
- diff 决策数 / accept / reject 分布   ：op == "rule" 的事件，detail.diff_id + detail.action
- 编辑触发联动次数与成功率             ：op == "edit_four_cards" 且 detail.args.decisions 缺失或为空、
                                         且 detail.args.edit.field != "none" 的事件计为“提案型编辑”；
                                         若其之后（到下一提案型编辑或文件末尾前）出现 >=1 条 rule 决策，
                                         视为该次编辑派生的提案被作者处理（联动成功）。
- 平均单提案决策耗时(ms)               ：相邻两次 rule 事件 ts 间隔的均值（等价于真人连续两次
                                         提交决策之间的间隔，含阅读/判断时间；单次决策则记 0）。
- 事件总数 / op 分布                   ：按事件 op 字段计数。

用法：
    python m4_analyze_traces.py --traces <a.json> [<b.json> ...] [--output <out.json>]

说明：文件为纯 Python 标准库实现，不改动工程内任何既有代码。
"""

import argparse
import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path


def parse_iso(ts: str):
    """解析 ISO8601 时间串为可求差的 datetime（统一换算 UTC）。"""
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_proposal_edit(ev: dict) -> bool:
    """判断 edit_four_cards 事件是否为“编辑产生提案”型（区别于 rule 内部的决策写回）。"""
    if ev.get("op") != "edit_four_cards":
        return False
    d = ev.get("detail") or {}
    args = d.get("args") or {}
    decisions = args.get("decisions")
    if decisions:
        return False  # 决策型写回：携带 decisions
    field = ((args.get("edit") or {}).get("field") or "").lower()
    return field != "none"


def analyze_one(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        events = json.load(f)
    if not isinstance(events, list):
        raise TypeError(f"{path} 顶层不是 JSON 数组")

    total = len(events)
    op_dist = OrderedDict(sorted(Counter(e.get("op") for e in events).items()))

    rules = [e for e in events if e.get("op") == "rule"]
    dec_count = len(rules)
    actions = Counter((r.get("detail") or {}).get("action") for r in rules)
    accept = actions.get("accept", 0)
    reject = actions.get("reject", 0)

    # 相邻 rule 决策间隔（ms）→ 平均单提案决策耗时
    intervals_ms = []
    prev = None
    for r in rules:
        cur = parse_iso(r["ts"])
        if prev is not None:
            intervals_ms.append((cur - prev).total_seconds() * 1000.0)
        prev = cur
    mean_decision_ms = round(sum(intervals_ms) / len(intervals_ms), 1) if intervals_ms else 0.0

    # 编辑联动：提案型编辑事件按 ts 排序，窗口内是否出现后续 rule 决策
    edits = [e for e in events if is_proposal_edit(e)]
    edits.sort(key=lambda e: parse_iso(e["ts"]))
    rules_ts = [parse_iso(r["ts"]) for r in rules]
    handled = 0
    for i, ed in enumerate(edits):
        t0 = parse_iso(ed["ts"])
        t1 = parse_iso(edits[i + 1]["ts"]) if i + 1 < len(edits) else None
        for rt in rules_ts:
            if rt > t0 and (t1 is None or rt < t1):
                handled += 1
                break
    proposals = len(edits)
    success_rate = round(handled / proposals * 100.0, 1) if proposals else None

    return {
        "name": path.stem,
        "path": str(path),
        "events": total,
        "op_distribution": dict(op_dist),
        "rule_decisions": {"count": dec_count, "accept": accept, "reject": reject},
        "mean_decision_ms": mean_decision_ms,
        "edit_links": {"proposals": proposals, "handled": handled, "success_rate": success_rate},
    }


def summarize(results: list) -> dict:
    tot_dec = sum(r["rule_decisions"]["count"] for r in results)
    tot_acc = sum(r["rule_decisions"]["accept"] for r in results)
    tot_rej = sum(r["rule_decisions"]["reject"] for r in results)
    ms_means = [r["mean_decision_ms"] for r in results if r["rule_decisions"]["count"] >= 1]
    sr = [
        r["edit_links"]["success_rate"]
        for r in results
        if r["edit_links"]["success_rate"] is not None
    ]
    return {
        "authors": len(results),
        "total_decisions": tot_dec,
        "total_accept": tot_acc,
        "total_reject": tot_rej,
        "accept_ratio": round(tot_acc / tot_dec * 100.0, 1) if tot_dec else None,
        "mean_decision_ms_avg": round(sum(ms_means) / len(ms_means), 1) if ms_means else None,
        "edit_success_rate_avg": round(sum(sr) / len(sr), 1) if sr else None,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="M4 trace 核算脚本（读 trace JSON → 统计 → 输出 JSON）"
    )
    ap.add_argument("--traces", nargs="+", required=True, help="trace JSON 文件列表")
    ap.add_argument("--output", default="", help="输出 JSON 路径；缺省打印到 stdout")
    args = ap.parse_args(argv)

    results = []
    for p in args.traces:
        fp = Path(p)
        if not fp.exists():
            print(
                json.dumps({"error": f"trace 文件不存在: {fp}"}, ensure_ascii=False),
                file=sys.stderr,
            )
            sys.exit(2)
        results.append(analyze_one(fp))

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_trace": results,
        "summary": summarize(results),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"written: {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
