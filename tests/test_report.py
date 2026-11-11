from __future__ import annotations

import json

from cloudops_inspector.report import render_html, render_markdown, write_reports


def test_render_html(run_report):
    html = render_html(run_report)
    assert "CloudOps Inspector" in html
    assert "centos9" in html
    assert "内存使用率" in html
    assert "badge" in html


def test_render_markdown(run_report):
    markdown = render_markdown(run_report)
    assert "# CloudOps Inspector" in markdown
    assert "| 检查项 |" in markdown
    assert "centos9" in markdown


def test_write_reports(tmp_path, run_report):
    paths = write_reports(run_report, tmp_path)
    assert paths["html"].exists()
    assert paths["markdown"].exists()
    assert paths["json"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["run_id"] == run_report.run_id
    assert payload["hosts"][0]["host"] == "centos9"
