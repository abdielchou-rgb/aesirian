"""文鉴门禁组 — 写作技巧与平台适配门禁。"""

from __future__ import annotations
import re
from .base import BaseGate
from wenjian.models import GateResult, GateSeverity

class CTP01_SceneObjective(BaseGate):
    gate_id = "CTP-01"
    name = "场景叙事功能门禁"
    description = "每个场景应该推动剧情、深化角色或揭示信息"
    severity = GateSeverity.WARN
    def evaluate(self, advance_plot: bool, deepen_char: bool, reveal_info: bool) -> GateResult:
        if not advance_plot and not deepen_char and not reveal_info:
            return self.fail_result(message="场景没有推动剧情、深化角色或揭示信息")
        return self.pass_result()

class CTP02_SubtextInScene(BaseGate):
    gate_id = "CTP-02"
    name = "场景潜台词门禁"
    description = "好的场景存在表面剧情和深层意图的双层结构"
    severity = GateSeverity.WARN
    def evaluate(self, surface_text: str = "", subconscious_hints: int = 0) -> GateResult:
        if subconscious_hints < 1:
            return self.fail_result(message="场景缺少潜台词")
        return self.pass_result()

class CTB01_CausalityChain(BaseGate):
    gate_id = "CTB-01"
    name = "因果链连续性门禁"
    description = "上一章结尾的张力应在下一章开头得到回应"
    severity = GateSeverity.WARN
    def evaluate(self, chapters_analyzed: int = 0, broken_chains: int = 0) -> GateResult:
        if chapters_analyzed > 1 and broken_chains > 0:
            return self.fail_result(message=f"{broken_chains} 处因果链断裂")
        return self.pass_result()

class CTB02_PayoffTracking(BaseGate):
    gate_id = "CTB-02"
    name = "伏笔回收追踪门禁"
    description = "所有引入的悬念/伏笔应该在合理篇幅内被回收"
    severity = GateSeverity.BLOCK
    def evaluate(self, open_loops: int = 0, chapters_since_intro: int = 0) -> GateResult:
        if open_loops > 3 and chapters_since_intro > 10:
            return self.fail_result(message=f"仍有 {open_loops} 个伏笔未回收")
        return self.pass_result()

class PRC01_ShowDontTell(BaseGate):
    gate_id = "PRC-01"
    name = "展示非告诉门禁"
    description = "用情绪名词代替实体触点是新人最常见的写作问题"
    severity = GateSeverity.WARN
    def evaluate(self, emotion_words: int = 0, touchpoints: int = 0) -> GateResult:
        if touchpoints == 0 and emotion_words > 0:
            return self.fail_result(message="只有情绪标签没有实体触点")
        if touchpoints > 0 and emotion_words / max(touchpoints, 1) > 2:
            return self.fail_result(message=f"情绪词（{emotion_words}）远多于触点（{touchpoints}）")
        return self.pass_result()

class PRC02_PacingVariety(BaseGate):
    gate_id = "PRC-02"
    name = "节奏变化门禁"
    description = "好的叙事有快慢交替"
    severity = GateSeverity.BLOCK
    def evaluate(self, gap_densities: list = None) -> GateResult:
        if gap_densities is None or len(gap_densities) < 3:
            return self.pass_result()
        if sum(1 for g in gap_densities if g > 4) > 0 and sum(1 for g in gap_densities if g < 1) == 0:
            return self.fail_result(message="全是高强度场景缺乏缓冲")
        if sum(1 for g in gap_densities if g < 1) > 0 and sum(1 for g in gap_densities if g > 4) == 0:
            return self.fail_result(message="节奏一直偏缓需要加入高强度场景")
        return self.pass_result()

class MCO01_EventDensity(BaseGate):
    gate_id = "MCO-01"
    name = "事件密度门禁"
    description = "每 1000 字至少发生一个有意义的叙事事件"
    severity = GateSeverity.WARN
    def evaluate(self, events: int = 0, char_count: int = 0) -> GateResult:
        if char_count < 300: return self.pass_result(message="文本太短")
        expected = max(1, char_count // 1000)
        if events < expected:
            return self.fail_result(message=f"事件密度不足（{events} 个/{char_count} 字，建议 {expected}+）")
        return self.pass_result()

class MCO02_SceneTransition(BaseGate):
    gate_id = "MCO-02"
    name = "场景转换清晰度门禁"
    description = "场景/时空跳跃不能让读者困惑"
    severity = GateSeverity.WARN
    def evaluate(self, abrupt_transitions: int = 0, total_transitions: int = 0) -> GateResult:
        if total_transitions > 0 and abrupt_transitions / total_transitions > 0.3:
            return self.fail_result(message=f"场景转换中有 {abrupt_transitions}/{total_transitions} 处过于突兀")
        return self.pass_result()

class APL01_OpeningHook(BaseGate):
    gate_id = "APL-01"
    name = "开篇钩子强度门禁"
    description = "前 500 字必须有吸引读者继续读下去的理由"
    severity = GateSeverity.BLOCK
    def evaluate(self, hook_position: int = 99999, first_500_events: int = 0) -> GateResult:
        if hook_position > 500 and first_500_events < 1:
            return self.fail_result(message="前 500 字没有冲突/悬念/钩子")
        return self.pass_result()

class APL02_EndingResolution(BaseGate):
    gate_id = "APL-02"
    name = "章节结尾门禁"
    description = "章节最后 200 字必须提供收束感或翻页动力"
    severity = GateSeverity.BLOCK
    def evaluate(self, has_closure: bool = False, has_hook: bool = False) -> GateResult:
        if not has_closure and not has_hook:
            return self.fail_result(message="章节结尾既无收束也无钩子")
        return self.pass_result()

class MRD01_SentenceVariety(BaseGate):
    gate_id = "MRD-01"
    name = "句式多样性门禁"
    description = "段落中的句子长度应有变化"
    severity = GateSeverity.WARN
    def evaluate(self, avg_sentence_len: float = 0, variety_score: float = 1.0) -> GateResult:
        if avg_sentence_len > 0 and variety_score < 0.3:
            return self.fail_result(message=f"句子长度变化不足（{variety_score}）")
        return self.pass_result()

class MRD02_ParagraphLength(BaseGate):
    gate_id = "MRD-02"
    name = "段落长度门禁"
    description = "网文段落不应过长"
    severity = GateSeverity.WARN
    def evaluate(self, avg_para_len: float = 0, very_long_paras: int = 0) -> GateResult:
        if very_long_paras > 3:
            return self.fail_result(message=f"发现 {very_long_paras} 个超长段落")
        return self.pass_result()

class INR01_NarrativeFocus(BaseGate):
    gate_id = "INR-01"
    name = "叙事焦点门禁"
    description = "每章应围绕不超过 3 个叙事线程展开"
    severity = GateSeverity.WARN
    def evaluate(self, active_threads: int = 1) -> GateResult:
        if active_threads > 3:
            return self.fail_result(message=f"章节有 {active_threads} 个活跃叙事线程")
        return self.pass_result()