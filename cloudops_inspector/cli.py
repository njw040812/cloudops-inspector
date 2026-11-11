"""Command line interface."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .checks import inspect_inventory
from .checks.builtin import CHECKS
from .inventory import load_inventory
from .report import write_reports
from .rules import RuleSet
from .storage import Store


def _inspect(args: argparse.Namespace) -> int:
    inventory = load_inventory(args.inventory)
    rules = RuleSet.load(args.rules)
    run = asyncio.run(
        inspect_inventory(
            inventory,
            rules=rules,
            inventory_path=str(args.inventory),
            concurrency=args.concurrency,
        )
    )

    store = Store(args.db)
    store.save_run(run)
    paths = write_reports(run, args.output)

    counts = run.counts
    print(f"run_id={run.run_id}")
    print(f"hosts={len(run.hosts)} score={run.score}/100")
    print(
        "ok={ok} warn={warn} crit={crit} error={error} skip={skip}".format(**counts)
    )
    print(f"html={paths['html']}")
    print(f"markdown={paths['markdown']}")
    print(f"json={paths['json']}")
    return 0 if counts["crit"] == 0 and counts["error"] == 0 else 1


def _history(args: argparse.Namespace) -> int:
    store = Store(args.db)
    runs = store.list_runs(args.limit)
    if not runs:
        print("no runs")
        return 0
    print(f"{'run_id':38s} {'started_at':26s} {'score':>5s} {'warn':>5s} {'crit':>5s}")
    for run in runs:
        print(
            f"{run['run_id']:38s} {run['started_at']:26s} {run['score']:>5d} "
            f"{run['warn']:>5d} {run['crit']:>5d}"
        )
    return 0


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app(args.db), host=args.host, port=args.port)
    return 0


def _checks(_: argparse.Namespace) -> int:
    print(f"{'id':20s} {'category':10s} name")
    for check in CHECKS:
        print(f"{check.id:20s} {check.category:10s} {check.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloudops-inspector",
        description="Read-only Linux/Docker baseline inspector",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="run an inspection")
    inspect.add_argument("--inventory", default="examples/inventory.yml")
    inspect.add_argument("--rules", default=None, help="rules YAML (default: rules/default.yml)")
    inspect.add_argument("--db", default="data/inspector.db")
    inspect.add_argument("--output", default="reports")
    inspect.add_argument("--concurrency", type=int, default=4)
    inspect.set_defaults(func=_inspect)

    history = sub.add_parser("history", help="show recent runs")
    history.add_argument("--db", default="data/inspector.db")
    history.add_argument("--limit", type=int, default=10)
    history.set_defaults(func=_history)

    serve = sub.add_parser("serve", help="serve history/metrics API")
    serve.add_argument("--db", default="data/inspector.db")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=_serve)

    checks = sub.add_parser("checks", help="list checks")
    checks.set_defaults(func=_checks)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
