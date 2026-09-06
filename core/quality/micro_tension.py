"""Maass 微张力 5 问 — 段落级质量检验

Maass 在《Writing the Breakout Novel》提出微张力：
读者不是被宏大的情节抓住，而是被每一句的"微微拉紧"抓住。
5 问检验法转化为段落级检测。
"""
from __future__ import annotations

import re

# 张力信号词（制造"微微拉紧"的词汇）
TENSION_VERBS = ["攥紧", "屏住", "僵住", "咬住", "颤抖", "盯住", "警觉",
                 "犹豫", "退缩", "心跳", "屏息", "危险", "威胁", "异常",
                 "不对劲", "猛然", "骤然", "瞬间", "突然"]
# 张力平淡信号
FLAT_MARKERS = ["平静", "安详", "如常", "一如既往", "没什么", "一切都好",
                "平淡", "正常"]


class MicroTensionDetector:
    """Maass 微张力 — 段落级 5 问：什么变了/什么危险/什么异常/什么悬而未决"""

    def detect(self, text: str) -> list[dict]:
        issues: list[dict] = []
        if not text.strip():
            return issues

        paragraphs = [p for p in text.split("\n") if len(p.strip()) > 30]
        tension_count = sum(text.count(w) for w in TENSION_VERBS)
        flat_count = sum(text.count(w) for w in FLAT_MARKERS)
        per_para = tension_count / max(len(paragraphs), 1)

        # 每段平均张力 < 0.5 → 段落平淡（需 ≥3 个长段）
        if per_para < 0.5 and len(paragraphs) >= 3:
            issues.append({
                "rule": "paragraph_tension_deficit",
                "severity": "warn",
                "message": f"平均每段张力信号仅 {per_para:.2f} 个——"
                           f"在每个场景或段落埋一个微张力的细节（异常、危险、未决）",
            })

        # 张力与平淡混同（自我抵消）—— 无长段限制，短文本也检测
        if tension_count == 0 and flat_count >= 2:
            issues.append({
                "rule": "tension_flat",
                "severity": "warn",
                "message": "通篇无张力信号且反复强调如常或平静——"
                           "叙事失去推进的微张力，读者没有继续读的钩子",
            })

        # 连续段落无任何张力（段落级检查）
        flat_paras = []
        for i, p in enumerate(paragraphs):
            if not any(w in p for w in TENSION_VERBS):
                flat_paras.append(i + 1)
        if len(flat_paras) >= 4:
            issues.append({
                "rule": "consecutive_flat_paragraphs",
                "severity": "warn",
                "message": f"第 {flat_paras[0]}-{flat_paras[-1]} 段连续无微张力，"
                           f"建议在其中插入一个异常/未决细节",
            })

        return issues