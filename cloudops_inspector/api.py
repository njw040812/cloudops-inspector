"""FastAPI app for run history and Prometheus metrics."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI, HTTPException, Response

from .checks.builtin import CHECKS
from .metrics import render_metrics
from .storage import Store


def create_app(db_path: Union[str, Path] = "data/inspector.db") -> FastAPI:
    store = Store(db_path)

    app = FastAPI(
        title="CloudOps Inspector",
        description="Linux/Docker baseline inspection history and metrics",
        version="0.1.0",
    )
    app.state.store = store

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "runs": store.counts().get("runs", 0)}

    @app.get("/api/v1/checks")
    def checks() -> dict:
        return {
            "total": len(CHECKS),
            "checks": [
                {"id": check.id, "name": check.name, "category": check.category}
                for check in CHECKS
            ],
        }

    @app.get("/api/v1/runs")
    def list_runs(limit: int = 20) -> dict:
        return {"runs": store.list_runs(limit)}

    @app.get("/api/v1/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return run

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(render_metrics(store), media_type="text/plain; version=0.0.4")

    return app
