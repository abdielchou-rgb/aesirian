"""多阶段生成管线 — Sudowrite 多变体 + AnySpark 生成→评估→修改循环

阶段: 组装上下文 → 风格指令 → N 变体生成（温度扰动）
      → 质量评分（字数 + InkOS 去AI + 门禁）→ 达标提前返回
      → 未达标吸收反馈进入下一轮（最多 3 轮）
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.context.assembler import ContextAssembler
from core.context.engine import ContextConfig
from core.pydantic_ai_engine import get_llm_engine
from core.quality.ai_tell_detector import AITellDetector


@dataclass
class GenerationResult:
    text: str = ""
    score: int = 0
    variants: list = field(default_factory=list)  # [(text, score)]
    rounds: int = 0
    style_prompt: str = ""
    context_tokens: int = 0
    llm_used: bool = False


class GenerationPipeline:
    """带质量循环的多变体生成器"""

    def __init__(self, store, config: ContextConfig | None = None):
        self.store = store
        self.assembler = ContextAssembler(store, config)
        self.detector = AITellDetector()
        self.llm = get_llm_engine()

    # ─── 主入口 ───

    def generate_with_quality(
        self,
        project_id: str,
        instruction: str,
        word_target: int = 500,
        rounds: int = 2,
        variants_per_round: int = 3,
    ) -> GenerationResult:
        instruction = instruction.strip()
        if not instruction:
            return GenerationResult()

        # 阶段 1: 上下文组装
        ac = self.assembler.assemble(project_id, instruction)

        # 阶段 2: 风格指令（来自项目已写文本的 VoiceProfile 近似）
        style_prompt = ""
        project_text = self._get_project_text(project_id)
        if project_text:
            from core.style.voice_profile import VoiceProfileInterview

            vp = VoiceProfileInterview().extract_from_text(project_text)
            style_prompt = vp.to_prompt()

        # 阶段 3-5: 变体循环
        best_text, best_score = "", 0
        all_variants: list[tuple[str, int]] = []
        feedback = ""

        for round_idx in range(max(1, rounds)):
            if not self.llm.available():
                break
            for i in range(max(1, variants_per_round)):
                temp = 0.7 + i * 0.15
                ctx_block = ac.text if round_idx == 0 else ac.text + f"\n\n## 修改建议\n{feedback}"
                variant = self.llm.generate_variant(
                    ctx_block,
                    ("\n\n" + style_prompt if style_prompt else "")
                    + f"\n\n## 本次写作指令\n{instruction}",
                    word_target=word_target,
                    temperature=temp,
                )
                if not variant:
                    continue
                score = self._score_quality(variant, project_id)
                all_variants.append((variant, score))
                if score > best_score:
                    best_text, best_score = variant, score

            if best_score >= 80 or not all_variants:
                break
            # 吸收最佳变体的问题，生成修改建议进入下一轮
            feedback = self._build_feedback(all_variants[-variants_per_round:])

        all_variants.sort(key=lambda x: x[1], reverse=True)
        return GenerationResult(
            text=best_text,
            score=best_score,
            variants=[{"text": t[:80] + "…", "score": s} for t, s in all_variants[:5]],
            rounds=round_idx + 1 if all_variants else 0,
            style_prompt=style_prompt,
            context_tokens=ac.total_tokens,
            llm_used=bool(all_variants),
        )

    # ─── 评分 ───

    def _score_quality(self, text: str, project_id: str) -> int:
        score = 100

        # 字数
        if len(text) < 100:
            score -= 30
        elif len(text) < 200:
            score -= 15

        # InkOS 去 AI 检测
        issues = self.detector.detect(text)
        score -= len(issues) * 5

        # 门禁检查（预生成 G1-G5）
        try:
            from core.consistency_gates import GateLevel
            from core.entity_extractor import EntityExtractor

            project = self._get_project_runtime(project_id)
            if project:
                ctx = EntityExtractor.to_gate_context(text)
                results = project.gates.pre_generation_check(
                    text,
                    context={
                        "facts": ctx["facts"],
                        "char_actions": ctx["char_actions"],
                        "identity_changes": ctx["identity_changes"],
                        "events": ctx["events"],
                        "movements": ctx["movements"],
                    },
                )
                for g in results:
                    if g.level == GateLevel.BLOCK:
                        score -= 20
                    elif g.level == GateLevel.WARN:
                        score -= 10
        except Exception:
            pass

        # 风格一致性：对话占比与句长偏移
        project_text = self._get_project_text(project_id)
        if project_text and len(project_text) > 500:
            diff = self._style_diff(project_text, text)
            score -= int(diff * 20)

        return max(0, min(100, score))

    @staticmethod
    def _style_diff(a: str, b: str) -> float:
        """0-1 简易风格偏移（平均句长差归一 + 对话占比差）"""
        import re as _re

        def stats(t):
            sents = [s for s in _re.split(r"[。！？]", t) if len(s.strip()) > 2]
            avg = sum(len(s) for s in sents) / max(len(sents), 1)
            dl = sum(1 for ln in t.splitlines() if any(m in ln for m in '「」""'))
            lines = max(len([ln for ln in t.splitlines() if ln.strip()]), 1)
            return avg, dl / lines

        avg_a, dl_a = stats(a)
        avg_b, dl_b = stats(b)
        d1 = min(abs(avg_a - avg_b) / 30, 1)
        d2 = min(abs(dl_a - dl_b) * 2, 1)
        return (d1 + d2) / 2

    def _build_feedback(self, variants: list[tuple[str, int]]) -> str:
        """从变体常见问题生成下轮修改建议"""
        best = max(variants, key=lambda x: x[1])[0] if variants else ""
        issues = self.detector.detect(best) if best else []
        lines = [
            f"上一轮最佳得分 {max(s for _, s in variants) if variants else 0}，以下问题需修正：",
            *[f"- [{iss['rule']}] {iss['message']}" for iss in issues],
        ]
        if not issues:
            lines.append("- 增加感官细节与句式长短变化，避免均匀段落")
        return "\n".join(lines)

    # ─── 数据访问 ───

    def _get_project_text(self, project_id: str) -> str:
        chapters = self.store.get_chapters(project_id)
        return "\n\n".join(ch.text for ch in chapters) if chapters else ""

    def _get_project_runtime(self, project_id: str):
        try:
            from core.orchestrator import Orchestrator

            return Orchestrator(store=self.store).get_project(project_id)
        except Exception:
            return None
