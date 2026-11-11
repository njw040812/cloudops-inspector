"""SQLite persistence for inspection runs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .models import RunReport


class Store:
    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    inventory_path TEXT,
                    score INTEGER NOT NULL,
                    duration_ms REAL NOT NULL,
                    ok INTEGER NOT NULL,
                    warn INTEGER NOT NULL,
                    crit INTEGER NOT NULL,
                    error INTEGER NOT NULL,
                    skip INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS results (
                    run_id TEXT NOT NULL,
                    host TEXT NOT NULL,
                    address TEXT NOT NULL,
                    check_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    value REAL,
                    unit TEXT,
                    summary TEXT,
                    details TEXT,
                    remediation TEXT,
                    PRIMARY KEY (run_id, host, check_id)
                );
                CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
                CREATE INDEX IF NOT EXISTS idx_results_status ON results(status);
                """
            )

    def save_run(self, run: RunReport) -> None:
        counts = run.counts
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO runs
                (run_id, started_at, finished_at, inventory_path, score, duration_ms,
                 ok, warn, crit, error, skip)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.started_at.isoformat(),
                    run.finished_at.isoformat(),
                    run.inventory_path,
                    run.score,
                    round(run.duration_ms, 2),
                    counts["ok"],
                    counts["warn"],
                    counts["crit"],
                    counts["error"],
                    counts["skip"],
                ),
            )
            rows = []
            for host in run.hosts:
                for result in host.results:
                    rows.append(
                        (
                            run.run_id,
                            host.host,
                            host.address,
                            result.check_id,
                            result.name,
                            result.category,
                            result.status.value,
                            result.value,
                            result.unit,
                            result.summary,
                            json.dumps(result.details, ensure_ascii=False),
                            result.remediation,
                        )
                    )
            connection.executemany(
                """
                INSERT OR REPLACE INTO results
                (run_id, host, address, check_id, name, category, status, value, unit,
                 summary, details, remediation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (max(1, limit),)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            run = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run is None:
                return None
            results = connection.execute(
                "SELECT * FROM results WHERE run_id = ? ORDER BY host, category, name",
                (run_id,),
            ).fetchall()
        payload = dict(run)
        payload["results"] = []
        for row in results:
            item = dict(row)
            item["details"] = json.loads(item["details"] or "[]")
            payload["results"].append(item)
        return payload

    def counts(self) -> Dict[str, int]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS runs,
                       COALESCE(SUM(ok), 0) AS ok,
                       COALESCE(SUM(warn), 0) AS warn,
                       COALESCE(SUM(crit), 0) AS crit,
                       COALESCE(SUM(error), 0) AS error,
                       COALESCE(SUM(skip), 0) AS skip
                FROM runs
                """
            ).fetchone()
        return dict(row) if row else {}

    def latest(self) -> Optional[Dict[str, Any]]:
        runs = self.list_runs(1)
        return runs[0] if runs else None
