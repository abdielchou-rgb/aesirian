"""M2 门禁验证扫描原型 — 干净文本基线探测。
用法: python tools/gate_verification/proto_scan.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "core"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from wenjian.audit.pipeline import AuditPipeline
from wenjian.audit.gates import ALL_GATES

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
TEXT = open(os.path.join(BASE, "examples", "luoyang", "ch1.txt"), encoding="utf-8").read()

def run_one(ctx):
    p = AuditPipeline(genre_id="suspense", platform="webnovel")
    rep = p.run_full(ctx)
    return rep, p

def summarize(rep):
    tot = len(rep.gate_results)
    passed = sum(1 for r in rep.gate_results if r.passed and not r.skipped)
    skipped = sum(1 for r in rep.gate_results if r.skipped)
    blocked = sum(1 for r in rep.gate_results if not r.passed and not r.skipped and r.severity.value == "block")
    warned = sum(1 for r in rep.gate_results if not r.passed and not r.skipped and r.severity.value == "warn")
    return {"total": tot, "passed": passed, "skipped": skipped, "blocked": blocked, "warned": warned}

if __name__ == "__main__":
    ctx = {
        "chapter_text": TEXT,
        "chapter_index": 0,
        "chapter_number": 1,
        "platform": "webnovel",
        "genre_id": "suspense",
    }
    rep, p = run_one(ctx)
    print("n_gates_registered:", len(ALL_GATES))
    print("summary:", json.dumps(summarize(rep), ensure_ascii=False))
    print("--- 非 PASS 明细 ---")
    for r in rep.gate_results:
        if not r.passed and not r.skipped:
            print(f"[{r.severity.value}] {r.gate_id}: {r.message[:120]}")
