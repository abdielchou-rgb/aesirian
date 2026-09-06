"""
Agent编排层 — review cycle + rollback

InkOS模式：write → assess → revise → reassess → (重试N次/取最优快照)

设计原则：
1. 每个写作步骤有一个"评审器"做独立检查
2. 评审不通过时（低于阈值），进入"修订循环"
3. 修订循环最多N次，每次取"最佳快照"
4. 如果所有修订都不满足阈值，回滚到上一章的状态
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AgentStep(Enum):
    PLAN = "plan"
    WRITE = "write"
    NORMALIZE = "normalize"
    ASSESS = "assess"
    REVISE = "revise"
    REASSESS = "reassess"
    COMMIT = "commit"
    ROLLBACK = "rollback"


class ReviewVerdict(Enum):
    PASS = "pass"  # 通过
    NEEDS_REVISION = "revise"  # 需要修订
    FAIL = "fail"  # 彻底失败→回滚


@dataclass
class ReviewResult:
    """评审结果"""

    step: AgentStep
    verdict: ReviewVerdict
    score: float  # 0.0-1.0
    issues: list[str] = field(default_factory=list)
    snapshot: Any = None  # 评审时的快照
    passed_checks: int = 0
    total_checks: int = 0


@dataclass
class ChapterSnapshot:
    """章节快照 — 用于回滚"""

    chapter: int
    text: str
    tom_state: Any = None  # ToM引擎快照
    kg_state: Any = None  # KG快照
    reader_state: Any = None  # 读者模型状态
    score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AgentPipeline:
    """
    Agent编排管线 — 带review cycle和rollback

    使用方式：
    pipeline = AgentPipeline(write_fn, assess_fn, revise_fn)
    result = pipeline.run(project_state)
    """

    def __init__(
        self,
        write_fn: Callable[..., Any] | None,
        assess_fn: Callable[..., Any] | None,
        revise_fn: Callable[..., Any] | None,
        max_retries: int = 3,
        pass_threshold: float = 0.85,  # InkOS: >=85分通过
        rollback_enabled: bool = True,
    ):
        self.write_fn = write_fn
        self.assess_fn = assess_fn
        self.revise_fn = revise_fn
        self.max_retries = max_retries
        self.pass_threshold = pass_threshold
        self.rollback_enabled = rollback_enabled
        self.history: list[ReviewResult] = []

    def run(self, context: dict) -> dict:
        """执行完整管线

        Returns:
            {"status": "committed"/"rolled_back",
             "text": "...",
             "reviews": [...],
             "best_score": 0.85}
        """
        self.history = []
        best_snapshot = None
        best_score = 0.0

        # ── Phase 1: 写 ──
        raw_text = self.write_fn(context) if self.write_fn else context.get("text", "")

        # ── Phase 2: 标准化 ──
        if self.callback("normalize"):
            raw_text = self._normalize(raw_text, context)

        # ── Phase 3: 评审循环 ──
        current_text = raw_text
        for attempt in range(self.max_retries + 1):
            # 评估
            result = self._assess(current_text, context, attempt)
            self.history.append(result)

            # 保存最佳快照
            if result.score > best_score:
                best_score = result.score
                best_snapshot = ChapterSnapshot(
                    chapter=context.get("chapter", 0),
                    text=current_text,
                    score=result.score,
                )

            # 判定
            if result.verdict == ReviewVerdict.PASS:
                return {
                    "status": "committed",
                    "text": current_text,
                    "reviews": [
                        r.to_dict() if hasattr(r, "to_dict") else str(r) for r in self.history
                    ],
                    "best_score": best_score,
                    "attempts": attempt,
                }

            if result.verdict == ReviewVerdict.FAIL or attempt >= self.max_retries:
                # 回滚到最佳快照
                if best_snapshot and self.rollback_enabled:
                    return {
                        "status": "rolled_back",
                        "text": best_snapshot.text,
                        "reviews": [str(r) for r in self.history],
                        "best_score": best_score,
                        "rollback_reason": f"经过{attempt + 1}次修订仍未达标(最后得分{result.score:.2f})",
                        "attempts": attempt + 1,
                    }
                # 无回滚选项时返回最后一次结果
                return {
                    "status": "best_effort",
                    "text": current_text,
                    "reviews": [str(r) for r in self.history],
                    "best_score": best_score,
                    "attempts": attempt + 1,
                }

            # 评审未通过则进入修订循环
            current_text = self._revise(current_text, result, context, attempt)

        # 不应到达这里
        return {"status": "unknown", "text": current_text, "reviews": [], "best_score": 0.0}

    def _assess(self, text: str, context: dict, attempt: int) -> ReviewResult:
        """执行评审"""
        if self.assess_fn:
            return self.assess_fn(text, context, attempt)

        # 默认评审：给一个基础分
        word_count = len(text)
        score = min(1.0, word_count / 500)
        return ReviewResult(
            step=AgentStep.ASSESS,
            verdict=ReviewVerdict.PASS
            if score >= self.pass_threshold
            else ReviewVerdict.NEEDS_REVISION,
            score=score,
            issues=[] if score >= self.pass_threshold else ["文本长度不足"],
        )

    def _revise(self, text: str, result: ReviewResult, context: dict, attempt: int) -> str:
        """执行修订"""
        if self.revise_fn:
            return self.revise_fn(text, result, context, attempt)
        return text

    def _normalize(self, text: str, context: dict) -> str:
        """标准化文本长度"""
        target_min = context.get("target_min_words", 500)
        # 如果太短，填充；太长，截断
        word_count = len(text)
        if word_count < target_min:
            # 不做自动填充，交给revise
            pass
        return text

    def callback(self, step_name: str) -> bool:
        """检查步骤是否可用"""
        return True

    def get_summary(self) -> dict:
        """获取管线摘要"""
        if not self.history:
            return {"status": "no_runs"}
        last = self.history[-1]
        return {
            "total_attempts": len(self.history),
            "final_verdict": last.verdict.value,
            "best_score": max(r.score for r in self.history),
            "issues": self.history[-1].issues if self.history else [],
        }
