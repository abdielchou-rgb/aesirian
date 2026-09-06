"""示例 gate 插件：中文被动语态滥用检测"""
import re


class PassiveVoiceGate:
    PASSIVE_MARKERS = ("被", "受到", "遭受", "得以")

    def check(self, text: str, context: dict | None = None) -> dict:
        count = sum(text.count(m) for m in self.PASSIVE_MARKERS)
        density = count / max(len(text) / 100, 1)
        if density > 3.0:
            return {
                "level": "WARN",
                "message": f"被动语态密度过高（每百字 {density:.1f} 次），叙事易显疏离",
                "suggestion": "改写为主语主动出击的句式",
            }
        return {"level": "PASS", "message": f"被动语态密度正常（{density:.1f}/百字）"}