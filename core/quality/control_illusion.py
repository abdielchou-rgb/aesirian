"""Storr 控制幻觉 6 规则 — 读者大脑的 6 种叙事需求

Peter Storr 认为读者的大脑追求"控制幻觉"——对因果/模式的掌控感。
违反以下规则时，读者会感到困惑或失去代入。
"""
from __future__ import annotations

import re

# 规则映射：违反信号词
RULES = [
    # 规则1：因果解释延迟 — 事件后无因果说明
    {
        "rule": "delayed_causality",
        "message": "事件发生但缺少因果解释，读者大脑渴求为什么",
    },
    # 规则2：模式中断 — 打破已建立节奏无警示
    {
        "rule": "broken_pattern",
        "message": "叙事模式突然中断且无铺垫，读者失去控制感",
    },
    # 规则3：视角跳变
    {
        "rule": "pov_jump",
        "message": "同一场景内视角跳变，读者难以建立代入",
    },
    # 规则4：信息超载
    {
        "rule": "info_overload",
        "message": "短时间内信息密度过高，读者大脑拒绝吸收",
    },
    # 规则5：无回报
    {
        "rule": "no_payoff",
        "message": "铺垫未回收，读者大脑的期待落空",
    },
    # 规则6：细节缺失
    {
        "rule": "missing_concrete",
        "message": "关键场景缺具体细节，读者无法构建画面",
    },
]


class ControlIllusionDetector:
    """Storr 6 规则 — 启发式实现（可计算子集）"""

    POV_MARKERS_1 = ["我", "我们"]
    POV_MARKERS_3 = ["他", "她", "他们", "它"]

    def detect(self, text: str) -> list[dict]:
        issues: list[dict] = []
        if not text.strip():
            return issues

        # 规则 3: 视角跳变（同段落内第一/第三人称混用）
        for para in text.split("\n"):
            if len(para) < 40:
                continue
            has1 = any(m in para for m in self.POV_MARKERS_1)
            has3 = any(m in para for m in self.POV_MARKERS_3)
            if has1 and has3:
                issues.append({
                    "rule": "pov_jump",
                    "severity": "warn",
                    "message": "段落内第一/第三人称混用——读者代入感断裂，建议统一视角",
                })
                break

        # 规则 6: 关键场景缺具体细节（无感官词 + 无动作动词）
        paragraphs = [p for p in text.split("\n") if len(p.strip()) > 30]
        concrete_paras = 0
        for p in paragraphs:
            if any(w in p for w in ["看见", "听见", "闻到", "手指", "目光",
                                    "站起来", "走", "推开", "握住", "灯光", "气味"]):
                concrete_paras += 1
        if paragraphs and concrete_paras / len(paragraphs) < 0.5:
            issues.append({
                "rule": "missing_concrete",
                "severity": "warn",
                "message": f"仅 {concrete_paras}/{len(paragraphs)} 段含具体细节——"
                           f"关键场景需要可视化的动作与感官描写",
            })

        # 规则 5: 无回报（疑问句/悬念词但无任何回收信号）
        q_marks = text.count("？") + text.count("?")
        payoff_words = sum(text.count(w) for w in ["原来", "因为", "真相", "明白了",
                                                   "意识到", "发现"])
        if q_marks >= 2 and payoff_words == 0 and len(text) > 200:
            issues.append({
                "rule": "no_payoff",
                "severity": "warn",
                "message": f"有 {q_marks} 个疑问/悬念但无任何揭示——读者期待落空，"
                           f"建议在段末给一个小回收",
            })

        return issues