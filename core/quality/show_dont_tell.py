"""Show Don't Tell 7 技法检测 — 具体化写作建议

将抽象的"告诉"转化为"展示"：用动作、感官、对话、细节让读者自行得出结论。
"""
from __future__ import annotations

import re

# 情绪"告诉"词 → 需要改为"展示"
TELL_EMOTIONS = {
    "他很生气": "生气",
    "她很难过": "难过",
    "他害怕": "害怕",
    "她很开心": "开心",
    "他紧张": "紧张",
    "她惊讶": "惊讶",
    "他愤怒": "愤怒",
    "她伤心": "伤心",
    "他很累": "疲惫",
    "她很失望": "失望",
    "他震惊": "震惊",
}
TELL_PATTERNS = [
    (r"他(很|非常|特别|极其)?(生气|愤怒|恼火)", "愤怒"),
    (r"她(很|非常|特别|极其)?(难过|伤心|悲伤)", "悲伤"),
    (r"他(很|非常|特别|极其)?(害怕|恐惧|紧张)", "恐惧"),
    (r"她(很|非常|特别|极其)?(开心|高兴|快乐)", "快乐"),
    (r"他(很|非常|特别|极其)?(疲惫|累|疲倦)", "疲惫"),
    (r"她(很|非常|特别|极其)?(失望|沮丧|灰心)", "失望"),
]
# 替代技法：动作/生理信号
SHOW_SIGNALS = {
    "愤怒": ["攥紧", "青筋", "拍桌", "摔", "咬紧", "涨红", "瞪着"],
    "悲伤": ["眼眶", "哽咽", "低头", "沉默", "攥着衣角", "眼泪"],
    "恐惧": ["颤抖", "后退", "屏住", "冷汗", "瞳孔", "苍白"],
    "快乐": ["笑", "眯起", "轻快", "哼着", "眼睛亮"],
    "疲惫": ["揉", "撑着", "哈欠", "沉重", "靠"],
    "失望": ["摇头", "垂下", "叹气", "别过脸"],
}


class ShowDontTellDetector:
    """Show Don't Tell — 7 技法中的情绪展示检测"""

    def detect(self, text: str) -> list[dict]:
        issues: list[dict] = []
        if not text.strip():
            return issues

        for pattern, emotion in TELL_PATTERNS:
            matches = re.findall(pattern, text)
            if not matches:
                continue
            signals = SHOW_SIGNALS.get(emotion, [])
            # 若情绪旁有生理/动作信号 → 已展示，不算违规
            has_show = sum(text.count(s) for s in signals) > 0
            if not has_show:
                issues.append({
                    "rule": f"telling_{emotion}",
                    "severity": "warn",
                    "message": f"直接告诉读者情绪（{emotion} × {len(matches)}），"
                               f"改用身体信号展示：如「{'/'.join(signals[:3])}」",
                })

        # 通用：抽象情绪词堆叠且无具体行为
        total_tells = sum(len(re.findall(p, text)) for p, _ in TELL_PATTERNS)
        action_verbs = sum(text.count(w) for w in
                           ["推", "拉", "握", "站", "走", "蹲", "抬头", "低头",
                            "抓起", "放下", "转身", "靠近", "后退"])
        if total_tells >= 3 and action_verbs == 0:
            issues.append({
                "rule": "emotion_tell_overload",
                "severity": "warn",
                "message": f"情绪描述 {total_tells} 处但无任何动作——全段在说情绪，"
                           f"让角色做出来",
            })

        return issues