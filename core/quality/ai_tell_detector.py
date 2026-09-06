"""去 AI 味检测 — InkOS 4 条确定性规则

规则 1: 段落均匀度（变异系数 < 0.15 报警）
规则 2: 模糊词密度（> 3/千字报警）
规则 3: 公式化过渡词（单词 ≥ 3 次报警）
规则 4: 列表式结构（连续 3 句同头报警）
"""

from __future__ import annotations

import re


class AITellDetector:
    HEDGE_WORDS = ["似乎", "可能", "或许", "大概", "某种程度上", "一定程度上", "在某种意义上"]
    TRANSITION_WORDS = ["然而", "不过", "与此同时", "然后", "接着", "因此", "所以"]

    def detect(self, text: str) -> list[dict]:
        issues: list[dict] = []
        if not text.strip():
            return issues

        # 规则 1: 段落均匀度
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if len(paragraphs) >= 3:
            lengths = [len(p) for p in paragraphs]
            mean = sum(lengths) / len(lengths)
            variance = sum((ln - mean) ** 2 for ln in lengths) / len(lengths)
            cv = (variance**0.5) / mean if mean > 0 else 0
            if cv < 0.15:
                issues.append(
                    {
                        "rule": "paragraph_uniformity",
                        "severity": "warn",
                        "message": f"段落长度过于均匀（变异系数 {cv:.2f}），建议增加长短变化",
                    }
                )

        # 规则 2: 模糊词密度
        hedge_count = sum(text.count(w) for w in self.HEDGE_WORDS)
        per_1000 = hedge_count / max(len(text) / 1000, 1)
        if per_1000 > 3:
            issues.append(
                {
                    "rule": "hedge_density",
                    "severity": "warn",
                    "message": f"模糊词密度过高（{per_1000:.1f}/千字），建议删除或替换",
                }
            )

        # 规则 3: 公式化过渡
        for word in self.TRANSITION_WORDS:
            count = text.count(word)
            if count >= 3:
                issues.append(
                    {
                        "rule": "formulaic_transition",
                        "severity": "warn",
                        "message": f"过渡词「{word}」出现 {count} 次，建议替换或删减",
                    }
                )

        # 规则 4: 列表式结构
        sentences = re.split(r"[。！？\n]", text)
        openings = [s[:2] for s in sentences if len(s) > 3]
        issues.extend(
            {
                "rule": "list_structure",
                "severity": "warn",
                "message": f"连续 3 句以「{openings[i]}」开头，建议变化句式",
            }
            for i in range(len(openings) - 2)
            if openings[i] == openings[i + 1] == openings[i + 2]
        )

        return issues
