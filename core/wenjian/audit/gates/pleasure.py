from __future__ import annotations

"""爽点工程门禁 — 中国网文最核心技术。

爽点 = 让读者产生正向情绪冲击的叙事单元。
不是"转折"，是"让人爽的转折"。

爽点类型：
  - 打脸爽：被看不起 → 展现实力 → 众人震惊
  - 升级爽：突破 → 新能力 → 碾压
  - 奇遇爽：捡宝 → 传承 → 机遇
  - 逆袭爽：绝境 → 反击 → 翻盘
  - 情感爽：误会 → 化解 → 升温
  - 装逼爽：低调 → 不经意展现实力 → 众人惊叹
"""

from wenjian.models import GateSeverity

from .base import BaseGate


class PLE01_PleasurePointDensity(BaseGate):
    """每章爽点密度门禁。"""

    gate_id = "PLE-01"
    name = "爽点密度门禁"
    description = "每章至少 1 个爽点，每 3 章至少 1 个高潮爽点"
    severity = GateSeverity.WARN

    def evaluate(self, pleasure_count: int, climax_count: int, chapter_index: int) -> GateResult:
        issues = []
        if pleasure_count < 1:
            issues.append(f"本章 {pleasure_count} 个爽点，需要至少 1 个")
        if chapter_index % 3 == 0 and climax_count < 1:
            issues.append(f"这是第 {chapter_index} 章，已连续 3 章应有 1 个高潮爽点")
        if issues:
            return self.fail_result(
                message="；".join(issues),
                details={"pleasure": pleasure_count, "climax": climax_count},
            )
        return self.pass_result(details={"pleasure": pleasure_count, "climax": climax_count})


class PLE02_SuppressionRelease(BaseGate):
    """压抑/释放比例门禁。"""

    gate_id = "PLE-02"
    name = "压抑释放比门禁"
    description = "连续压抑不超过 3 章，压抑:释放 ≈ 3:1"
    severity = GateSeverity.BLOCK

    def evaluate(self, consecutive_suppression: int, suppression_ratio: float) -> GateResult:
        if consecutive_suppression > 3:
            return self.fail_result(
                message=f"连续压抑 {consecutive_suppression} 章，超过 3 章上限。读者需要释放点。",
                details={"consecutive_suppression": consecutive_suppression},
            )
        if suppression_ratio > 5 and consecutive_suppression >= 2:
            return self.fail_result(
                message=f"压抑/释放比 {suppression_ratio:.1f}，建议控制在 3:1 以内",
                details={"ratio": round(suppression_ratio, 1)},
            )
        return self.pass_result(
            details={"suppression": consecutive_suppression, "ratio": round(suppression_ratio, 1)}
        )


class PLE03_FaceSlapStructure(BaseGate):
    """打脸爽结构门禁：轻视 → 展现实力 → 震惊"""

    gate_id = "PLE-03"
    name = "打脸结构门禁"
    description = "打脸爽需要完整的三段结构：被轻视→展现→震惊"
    severity = GateSeverity.WARN

    def evaluate(self, has_disdain: bool, has_show: bool, has_shock: bool) -> GateResult:
        missing = []
        if not has_disdain:
            missing.append("轻视铺垫")
        if not has_show:
            missing.append("实力展现")
        if not has_shock:
            missing.append("震惊反应")
        if missing:
            return self.fail_result(
                message=f"打脸结构不完整，缺少：{'、'.join(missing)}",
                details={"stages": {"disdain": has_disdain, "show": has_show, "shock": has_shock}},
            )
        return self.pass_result()


class PLE04_UpgradeChain(BaseGate):
    """升级节奏门禁。"""

    gate_id = "PLE-04"
    name = "升级节奏门禁"
    description = "每次升级后应有新能力展示；升级间隔不宜过长"
    severity = GateSeverity.WARN

    def evaluate(
        self, chapters_since_last_upgrade: int, has_showcase: bool, genre: str = "xianxia_modern"
    ) -> GateResult:
        max_interval = {"xianxia_modern": 5, "xianxia_traditional": 8, "xuanhuan": 5}.get(genre, 7)
        if chapters_since_last_upgrade > max_interval:
            return self.fail_result(
                message=f"距上次升级已 {chapters_since_last_upgrade} 章（{genre} 建议 {max_interval} 章内）",
                details={"interval": chapters_since_last_upgrade, "max": max_interval},
            )
        if chapters_since_last_upgrade <= 2 and not has_showcase:
            return self.fail_result(
                message="升级后没有展示新能力，读者感受不到变强",
                details={"has_showcase": False},
            )
        return self.pass_result(
            details={"interval": chapters_since_last_upgrade, "has_showcase": has_showcase}
        )


class PLE05_ShowingOff(BaseGate):
    """装逼打脸结构门禁。"""

    gate_id = "PLE-05"
    name = "装逼结构门禁"
    description = "装逼爽需要：低调入场→不经意展现→众人惊叹"
    severity = GateSeverity.WARN

    def evaluate(self, has_lowkey: bool, has_casual_show: bool, has_amazement: bool) -> GateResult:
        missing = []
        if not has_lowkey:
            missing.append("低调入场")
        if not has_casual_show:
            missing.append("不经意展现")
        if not has_amazement:
            missing.append("众人惊叹")
        if missing:
            return self.fail_result(
                message=f"装逼结构不完整，缺少：{'、'.join(missing)}",
                details={
                    "stages": {
                        "lowkey": has_lowkey,
                        "casual_show": has_casual_show,
                        "amazement": has_amazement,
                    }
                },
            )
        return self.pass_result()


class PLE06_PayoffRatio(BaseGate):
    """铺垫/回收比门禁。"""

    gate_id = "PLE-06"
    name = "铺垫回收比门禁"
    description = "每个爽点需要足够的铺垫支撑，铺垫与回收比例应合理"
    severity = GateSeverity.WARN

    def evaluate(self, setup_chapters: int, payoff_intensity: int) -> GateResult:
        if setup_chapters >= 10 and payoff_intensity < 3:
            return self.fail_result(
                message=f"铺垫了 {setup_chapters} 章，但爽点强度仅 {payoff_intensity}/5，读者会觉得雷声大雨点小",
                details={"setup": setup_chapters, "payoff": payoff_intensity},
            )
        return self.pass_result(details={"setup": setup_chapters, "payoff": payoff_intensity})
