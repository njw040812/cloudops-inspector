"""HTML/Markdown/JSON report rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import RunReport, Status

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
STATUS_LABELS = {
    Status.OK.value: "正常",
    Status.WARN.value: "警告",
    Status.CRIT.value: "严重",
    Status.ERROR.value: "执行失败",
    Status.SKIP.value: "跳过",
}


def render_html(run: RunReport) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html.j2")
    return template.render(run=run, labels=STATUS_LABELS)


def render_markdown(run: RunReport) -> str:
    counts = run.counts
    lines = [
        "# CloudOps Inspector 巡检报告",
        "",
        f"- Run ID: `{run.run_id}`",
        f"- 开始时间: {run.started_at.isoformat()}",
        f"- 耗时: {run.duration_ms:.0f} ms",
        f"- 主机数: {len(run.hosts)}",
        f"- 总分: **{run.score}/100**",
        f"- 统计: OK {counts['ok']} / WARN {counts['warn']} / CRIT {counts['crit']} / ERROR {counts['error']} / SKIP {counts['skip']}",
        "",
    ]
    for host in run.hosts:
        lines += [
            f"## {host.host} (`{host.address}`)",
            "",
            f"- 评分: **{host.score}/100**",
            f"- 统计: OK {host.counts['ok']} / WARN {host.counts['warn']} / CRIT {host.counts['crit']} / ERROR {host.counts['error']} / SKIP {host.counts['skip']}",
            "",
            "| 检查项 | 状态 | 数值 | 摘要 |",
            "|--------|------|------|------|",
        ]
        for result in host.results:
            value = "" if result.value is None else f"{result.value:g}{result.unit}"
            status = STATUS_LABELS.get(result.status.value, result.status.value)
            lines.append(f"| {result.name} | {status} | {value} | {result.summary} |")
        details = [result for result in host.results if result.details and result.status in (Status.WARN, Status.CRIT, Status.ERROR)]
        if details:
            lines += ["", "**需要关注：**"]
            for result in details:
                lines.append(f"- {result.name}: " + "; ".join(result.details[:5]))
                if result.remediation:
                    lines.append(f"  - 建议: {result.remediation}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_reports(run: RunReport, output_dir: Union[str, Path]) -> Dict[str, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = run.started_at.strftime("%Y%m%d-%H%M%S")
    base = directory / f"inspection-{stamp}"
    html_path = base.with_suffix(".html")
    md_path = base.with_suffix(".md")
    json_path = base.with_suffix(".json")

    html_path.write_text(render_html(run), encoding="utf-8")
    md_path.write_text(render_markdown(run), encoding="utf-8")
    json_path.write_text(json.dumps(run.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"html": html_path, "markdown": md_path, "json": json_path}
