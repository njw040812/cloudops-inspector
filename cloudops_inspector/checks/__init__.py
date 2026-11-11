"""Check registry and inspection orchestration."""

from __future__ import annotations

import asyncio
from datetime import timezone
from typing import Callable, List, Optional

from ..executor import BaseExecutor, CommandResult, create_executor
from ..inventory import Host, Inventory
from ..models import HostReport, RunReport, Status, utcnow
from ..rules import RuleSet
from .base import Check
from .builtin import CHECKS

ExecutorFactory = Callable[[Host], BaseExecutor]


async def inspect_host(
    host: Host,
    rules: RuleSet,
    executor: Optional[BaseExecutor] = None,
) -> HostReport:
    executor = executor or create_executor(host)
    selected: List[Check] = [check for check in CHECKS if rules.enabled(check.id)]
    started = utcnow()
    results = await executor.run_many(host, {check.id: check.command for check in selected})

    check_results = []
    for check in selected:
        command_result = results.get(check.id) or CommandResult(
            command=check.command, exit_code=-1, error="executor returned no result"
        )
        if command_result.error:
            check_results.append(
                check.error(command_result, f"命令执行失败: {command_result.error}")
            )
            continue
        try:
            check_results.append(check.evaluate(command_result, rules.get(check.id)))
        except Exception as exc:  # a parser bug must not kill the whole host report
            check_results.append(check.error(command_result, f"check parser failed: {exc}"))

    return HostReport(
        host=host.name,
        address=host.address,
        started_at=started,
        finished_at=utcnow(),
        results=check_results,
    )


async def inspect_inventory(
    inventory: Inventory,
    rules: Optional[RuleSet] = None,
    inventory_path: str = "",
    concurrency: int = 4,
) -> RunReport:
    rules = rules or RuleSet.load()
    run = RunReport.new(inventory_path=inventory_path)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(host: Host) -> HostReport:
        async with semaphore:
            return await inspect_host(host, rules)

    run.hosts = list(await asyncio.gather(*(one(host) for host in inventory.hosts)))
    return run.finalize()
