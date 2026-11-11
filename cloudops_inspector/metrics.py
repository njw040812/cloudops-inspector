"""Prometheus text exposition."""

from __future__ import annotations

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
        for status in ("ok", "warn", "crit", "error", "skip"):
            lines.append(
                f'cloudops_inspector_last_checks{{status="{status}"}} {latest[status]}'
            )
    return "\n".join(lines) + "\n"
