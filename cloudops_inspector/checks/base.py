"""Check abstraction and small helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..executor import CommandResult
from ..models import CheckResult, Status


class Check(ABC):
    id: str
    name: str
    category: str
    command: str
    remediation: str = ""
    optional: bool = False

    def result(
        self,
        status: Status,
        summary: str,
        result: Optional[CommandResult] = None,
        value: Optional[float] = None,
        unit: str = "",
        details: Optional[List[str]] = None,
        error: str = "",
    ) -> CheckResult:
        return CheckResult(
            check_id=self.id,
            name=self.name,
            category=self.category,
            status=status,
            summary=summary,
            value=value,
            unit=unit,
            details=details or [],
            remediation=self.remediation,
            command=self.command,
            duration_ms=result.elapsed_ms if result else 0.0,
            error=error or (result.error if result else ""),
        )

    def error(self, result: CommandResult, message: str) -> CheckResult:
        return self.result(
            Status.ERROR,
            message,
            result=result,
            error=result.error or result.stderr.strip()[:300],
        )

    def skip(self, result: CommandResult, message: str) -> CheckResult:
        return self.result(Status.SKIP, message, result=result)

    def threshold(
        self,
        value: float,
        rule: Dict[str, Any],
        unit: str,
        summary_prefix: str,
        result: Optional[CommandResult] = None,
        details: Optional[List[str]] = None,
    ) -> CheckResult:
        from ..rules import threshold_status

        status = threshold_status(value, rule)
        return self.result(
            status,
            f"{summary_prefix}: {value:.2f}{unit}",
            result=result,
            value=round(value, 2),
            unit=unit,
            details=details,
        )

    @abstractmethod
    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        """Turn a command result into a structured check result."""
