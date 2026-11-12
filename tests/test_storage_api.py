from __future__ import annotations

from fastapi.testclient import TestClient

from cloudops_inspector.api import create_app
from cloudops_inspector.storage import Store


def test_store_roundtrip(tmp_path, run_report):
    store = Store(tmp_path / "inspector.db")
    store.save_run(run_report)

    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == run_report.run_id
    assert store.counts()["runs"] == 1

    detail = store.get_run(run_report.run_id)
    assert detail is not None
    assert detail["score"] == run_report.score
    assert len(detail["results"]) == len(run_report.hosts[0].results)


def test_api(tmp_path, run_report):
    db = tmp_path / "inspector.db"
    Store(db).save_run(run_report)
    client = TestClient(create_app(db))

    assert client.get("/health").status_code == 200
    runs = client.get("/api/v1/runs").json()["runs"]
    assert len(runs) == 1

    detail = client.get(f"/api/v1/runs/{run_report.run_id}")
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run_report.run_id

    assert client.get("/api/v1/runs/not-found").status_code == 404
    checks = client.get("/api/v1/checks").json()
    assert checks["total"] == 22
    metrics = client.get("/metrics")
    assert "cloudops_inspector_runs_total 1" in metrics.text
    assert "cloudops_inspector_last_run_timestamp_seconds" in metrics.text
    assert f"cloudops_inspector_last_score {run_report.score}" in metrics.text
