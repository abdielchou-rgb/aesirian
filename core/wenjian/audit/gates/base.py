"""Base gate class for all 38 story gates."""

from abc import ABC, abstractmethod
from wenjian.models import GateResult, GateSeverity


class BaseGate(ABC):
    """Base class for all gates."""

    @property
    @abstractmethod
    def gate_id(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def severity(self) -> GateSeverity: ...

    def pass_result(self, message: str = "", details: dict = None) -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            name=self.name,
            severity=self.severity,
            passed=True,
            message=message or "通过",
            details=details or {},
        )

    def fail_result(self, message: str = "", details: dict = None, score: float = None) -> GateResult:
        return GateResult(
            gate_id=self.gate_id,
            name=self.name,
            severity=self.severity,
            passed=False,
            message=message,
            details=details or {},
            score=score,
        )