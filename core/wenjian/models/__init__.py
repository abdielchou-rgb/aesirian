"""文鉴 Models — 审计结果模型 + LLM 供应商接口。"""

# ── 审计模型 ──
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ── 注册 LLM 供应商 ──
from . import anthropic, base, ollama, openai


class GateSeverity(str, Enum):  # noqa: UP042  # StrEnum 需 3.11+，CI 矩阵含 3.10
    BLOCK = "block"
    WARN = "warn"
    INFO = "info"  # P3-11: 装饰性门禁降级位——对缺陷无区分度的门禁，失败不拉高报告状态
    PASS = "pass"


@dataclass
class GateResult:
    gate_id: str
    name: str
    severity: GateSeverity
    passed: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
    skipped: bool = False  # 结构门禁缺跨章数据时跳过（不计入失败）

    def to_dict(self) -> dict:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "severity": self.severity.value,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
            "score": self.score,
            "skipped": self.skipped,
        }


@dataclass
class Scene:
    id: str
    text: str
    chapter: str = ""
    entry_value: dict[str, str] | None = None
    exit_value: dict[str, str] | None = None


@dataclass
class AuditReport:
    report_id: str
    gate_results: list[GateResult] = field(default_factory=list)
    overall_status: str = "pass"

    def add(self, result: GateResult):
        self.gate_results.append(result)
        # P3-11: INFO 级失败（装饰性门禁降噪）不改变报告状态——仅记录供参考，
        # 不把"对缺陷无区分度的基线噪音"误判为全章告警/拦截。
        if result.severity == GateSeverity.INFO:
            return
        if result.severity == GateSeverity.BLOCK and result.passed is False:
            self.overall_status = "block"
        elif (
            result.severity == GateSeverity.WARN
            and result.passed is False
            and self.overall_status != "block"
        ):
            self.overall_status = "warn"

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "overall_status": self.overall_status,
            "gates": [r.to_dict() for r in self.gate_results],
        }


VALUE_PAIRS = [
    ("生", "死"),
    ("爱", "恨"),
    ("信任", "背叛"),
    ("希望", "绝望"),
    ("自由", "束缚"),
    ("正义", "不公"),
    ("真相", "谎言"),
    ("力量", "无力"),
    ("圆满", "残缺"),
    ("归属", "孤立"),
    ("荣耀", "耻辱"),
    ("勇敢", "怯懦"),
    ("清醒", "幻觉"),
    ("和解", "决裂"),
]
