"""Prometheus text exposition."""

from __future__ import annotations

from datetime import datetime

from .storage import Store


def render_metrics(store: Store) -> str:
    latest = store.latest()
    totals = store.counts()
    lines = [
        "# HELP cloudops_inspector_runs_total Total inspection runs stored",
        "# TYPE cloudops_inspector_runs_total counter",
        f"cloudops_inspector_runs_total {totals.get('runs', 0)}",
    ]
    if latest:
        lines += [
            "# HELP cloudops_inspector_last_score Score of the latest run (0-100)",
            "# TYPE cloudops_inspector_last_score gauge",
            f"cloudops_inspector_last_score {latest['score']}",
            "# HELP cloudops_inspector_last_duration_ms Duration of the latest run",
            "# TYPE cloudops_inspector_last_duration_ms gauge",
            f"cloudops_inspector_last_duration_ms {latest['duration_ms']}",
        ]
        try:
            timestamp = datetime.fromisoformat(latest["started_at"]).timestamp()
        except (KeyError, TypeError, ValueError):
            timestamp = None
        if timestamp is not None:
            lines += [
                "# HELP cloudops_inspector_last_run_timestamp_seconds Unix time of the latest run",
                "# TYPE cloudops_inspector_last_run_timestamp_seconds gauge",
                f"cloudops_inspector_last_run_timestamp_seconds {timestamp:.0f}",
            ]
        lines += [
            "# HELP cloudops_inspector_last_checks Number of checks by status in the latest run",
            "# TYPE cloudops_inspector_last_checks gauge",
        ]
        for status in ("ok", "warn", "crit", "error", "skip"):
            lines.append(
                f'cloudops_inspector_last_checks{{status="{status}"}} {latest[status]}'
            )
    return "\n".join(lines) + "\n"
