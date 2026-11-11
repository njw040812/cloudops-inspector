"""Rule loading and threshold helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from .models import Status

DEFAULT_RULES = Path(__file__).resolve().parents[1] / "rules" / "default.yml"


class RuleSet:
    def __init__(self, checks: Dict[str, Dict[str, Any]]):
        self.checks = checks

    @classmethod
    def load(cls, path: Optional[Union[str, Path]] = None) -> "RuleSet":
        source = Path(path) if path else DEFAULT_RULES
        data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        checks = data.get("checks", {})
        if not isinstance(checks, dict):
            raise ValueError("rules.checks must be a mapping")
        return cls(checks)

    def get(self, check_id: str) -> Dict[str, Any]:
        return self.checks.get(check_id, {}) or {}

    def enabled(self, check_id: str) -> bool:
        return bool(self.get(check_id).get("enabled", True))

    def enabled_ids(self) -> list:
        return [check_id for check_id in self.checks if self.enabled(check_id)]


def threshold_status(value: float, rule: Dict[str, Any], higher_is_worse: bool = True) -> Status:
    warn = rule.get("warn")
    crit = rule.get("crit")
    if higher_is_worse:
        if crit is not None and value >= float(crit):
            return Status.CRIT
        if warn is not None and value >= float(warn):
            return Status.WARN
    else:
        if crit is not None and value <= float(crit):
            return Status.CRIT
        if warn is not None and value <= float(warn):
            return Status.WARN
    return Status.OK


def expected_status(
    actual: str,
    expected: str,
    rule: Optional[Dict[str, Any]] = None,
) -> Status:
    rule = rule or {}
    if actual.strip().lower() == expected.strip().lower():
        return Status.OK
    severity = str(rule.get("severity", "warn")).lower()
    return Status.CRIT if severity == "crit" else Status.WARN
