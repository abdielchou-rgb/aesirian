"""Barthes 现实效应检测 — 细节 > 抽象

理论：具体可感的细节（"细节的符号"）让读者相信世界的真实。
检测：抽象概括词密度 vs 感官/具体名词密度，输出具体化建议。
"""
from __future__ import annotations

import re

ABSTRACT_NOUNS = ["命运", "人生", "爱情", "意义", "情感", "内心", "世界",
                  "一切", "事情", "某种", "感觉", "情绪", "灵魂", "岁月",
                  "回忆", "希望", "绝望", "孤独", "自由", "真相"]
VAGUE_ADJ = ["美好", "美丽", "深刻", "复杂", "微妙", "强烈", "模糊",
             "淡淡的", "深深的", "一种说不出的"]
SENSORY_HINTS = ["味道", "气味", "声音", "光线", "温度", "触感", "色彩",
                 "手指", "掌心", "视线", "呼吸", "心跳", "风", "雨",
                 "灰尘", "灯光", "月光", "摩擦", "滑动", "光泽"]


class RealityEffectDetector:
    """Barthes 现实效应 — 抽象 vs 具体比例"""

    def detect(self, text: str) -> list[dict]:
        issues: list[dict] = []
        if not text.strip():
            return issues

        abstract_count = sum(text.count(w) for w in ABSTRACT_NOUNS)
        vague_count = sum(text.count(w) for w in VAGUE_ADJ)
        sensory_count = sum(text.count(w) for w in SENSORY_HINTS)
        per_1000 = len(text) / 1000

        # 抽象词密度过高
        abs_density = abstract_count / max(per_1000, 1)
        if abs_density > 2.5:
            issues.append({
                "rule": "abstract_overload",
                "severity": "warn",
                "message": f"抽象名词密度过高（{abs_density:.1f}/千字），建议替换为具体场景细节",
            })

        # 抽象 > 具体且两者都不足 → 缺乏"现实效应"
        if abstract_count > sensory_count and abstract_count >= 2:
            issues.append({
                "rule": "lacks_reality_effect",
                "severity": "warn",
                "message": f"抽象描述({abstract_count}处)多于感官细节({sensory_count}处)——"
                           f"加入具体可感的细节，让读者看见世界",
            })

        # 模糊形容词堆叠
        if vague_count >= 3:
            issues.append({
                "rule": "vague_adjectives",
                "severity": "warn",
                "message": f"模糊形容词出现 {vague_count} 次（美好/深刻/某种…），"
                           f"建议用动作和感官细节替代",
            })

        return issues