"""Data models shared by checks, reports, storage and API."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


class Status(str, Enum):
    OK = "ok"
    WARN = "warn"
    CRIT = "crit"
    ERROR = "error"
    SKIP = "skip"

    @property
    def penalty(self) -> int:
        return {
            Status.OK: 0,
            Status.WARN: 3,
            Status.CRIT: 10,
            Status.ERROR: 5,
            Status.SKIP: 0,
        }[self]


@dataclass
class CheckResult:
    check_id: str
    name: str
    category: str
    status: Status
    summary: str
    value: Optional[float] = None
    unit: str = ""
    details: List[str] = field(default_factory=list)
    remediation: str = ""
    command: str = ""
    duration_ms: float = 0.0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "category": self.category,
            "status": self.status.value,
            "summary": self.summary,
            "value": self.value,
            "unit": self.unit,
            "details": self.details,
            "remediation": self.remediation,
            "command": self.command,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
        }


@dataclass
class HostReport:
    host: str
    address: str
    started_at: datetime
    finished_at: datetime
    results: List[CheckResult] = field(default_factory=list)

    @property
    def counts(self) -> Dict[str, int]:
        counts = {status.value: 0 for status in Status}
        for result in self.results:
            counts[result.status.value] += 1
        return counts

    @property
    def score(self) -> int:
        penalty = sum(result.status.penalty for result in self.results)
        return max(0, 100 - penalty)

    @property
    def duration_ms(self) -> float:
        return (self.finished_at - self.started_at).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "address": self.address,
            "started_at": iso(self.started_at),
            "finished_at": iso(self.finished_at),
            "duration_ms": round(self.duration_ms, 2),
            "score": self.score,
            "counts": self.counts,
            "results": [result.to_dict() for result in self.results],
        }


@dataclass
class RunReport:
    run_id: str
    started_at: datetime
    finished_at: datetime
    hosts: List[HostReport] = field(default_factory=list)
    inventory_path: str = ""

    @classmethod
    def new(cls, inventory_path: str = "") -> "RunReport":
        return cls(
            run_id=str(uuid.uuid4()),
            started_at=utcnow(),
            finished_at=utcnow(),
            inventory_path=inventory_path,
        )

    @property
    def counts(self) -> Dict[str, int]:
        counts = {status.value: 0 for status in Status}
        for host in self.hosts:
            for key, value in host.counts.items():
                counts[key] += value
        return counts

    @property
    def score(self) -> int:
        if not self.hosts:
            return 0
        return round(sum(host.score for host in self.hosts) / len(self.hosts))

    @property
    def duration_ms(self) -> float:
        return (self.finished_at - self.started_at).total_seconds() * 1000

    def finalize(self) -> "RunReport":
        self.finished_at = utcnow()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": iso(self.started_at),
            "finished_at": iso(self.finished_at),
            "duration_ms": round(self.duration_ms, 2),
            "inventory_path": self.inventory_path,
            "score": self.score,
            "counts": self.counts,
            "hosts": [host.to_dict() for host in self.hosts],
        }
