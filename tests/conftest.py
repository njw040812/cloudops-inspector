from __future__ import annotations

import asyncio
from typing import Dict

import pytest

from cloudops_inspector.checks import inspect_host
from cloudops_inspector.executor import BaseExecutor, CommandResult
from cloudops_inspector.inventory import Host
from cloudops_inspector.models import RunReport
from cloudops_inspector.rules import RuleSet

SAMPLE: Dict[str, str] = {
    "cpu_usage": " 1  0  0 100 200 300  0  0  1  2  3  4 12  8 79  1  0",
    "load_per_core": "0.42 0.50 0.60 1/100 1234\n4\n",
    "memory_usage": (
        "              total        used        free      shared  buff/cache   available\n"
        "Mem:    8589934592  4294967296  1073741824           0  2147483648  4294967296\n"
        "Swap:   2147483648  1073741824  1073741824\n"
    ),
    "swap_usage": (
        "              total        used        free      shared  buff/cache   available\n"
        "Mem:    8589934592  4294967296  1073741824           0  2147483648  4294967296\n"
        "Swap:   2147483648  1073741824  1073741824\n"
    ),
    "disk_usage": (
        "Filesystem     1024-blocks    Used Available Capacity Mounted on\n"
        "/dev/vda1        104857600 52428800  52428800      50% /\n"
        "/dev/vdb1        104857600 89128960  15728640      85% /data\n"
    ),
    "inode_usage": (
        "Filesystem      Inodes IUsed IFree IUse% Mounted on\n"
        "/dev/vda1       6553600 65536 6488064    1% /\n"
    ),
    "failed_units": "nginx.service loaded failed failed nginx\n",
    "zombie_processes": "3\n",
    "fd_usage": "1024 0 1048576\n",
    "log_dir_size": "3221225472\n",
    "docker_service": "active\n/usr/bin/docker\n",
    "docker_containers": (
        "web|running|0|Up 2 hours\n"
        "api|restarting|3|Restarting (1) 10 seconds ago\n"
    ),
    "docker_disk": "Images|1.2GB|1.2GB (40%)\nContainers|10MB|0B (0%)\n",
    "listening_ports": (
        "Netid State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
        "tcp   LISTEN 0      128    0.0.0.0:22         0.0.0.0:*\n"
        "tcp   LISTEN 0      128    127.0.0.1:9090     0.0.0.0:*\n"
    ),
    "ssh_config": "permitrootlogin no\npasswordauthentication no\nmaxauthtries 3\n",
    "firewalld": "active\n",
    "selinux": "Enforcing\n",
    "chrony_synced": "yes\n",
    "reboot_required": "no\n",
    "uptime": "123456.78 1000.00\n",
    "kernel": "5.14.0-427.el9.x86_64\n",
    "timezone": "Asia/Shanghai\n",
}


class FakeExecutor(BaseExecutor):
    def __init__(self, outputs: Dict[str, str]):
        self.outputs = outputs

    async def run_many(self, host: Host, commands: Dict[str, str], timeout: int = 15):
        results = {}
        for check_id, command in commands.items():
            output = self.outputs.get(check_id)
            results[check_id] = CommandResult(
                command=command,
                stdout=output or "",
                stderr="" if output is not None else "command not found",
                exit_code=0 if output is not None else 127,
            )
        return results


@pytest.fixture
def host() -> Host:
    return Host(name="centos9", address="192.0.2.10", user="root")


@pytest.fixture
def rules() -> RuleSet:
    return RuleSet.load()


@pytest.fixture
def fake_executor() -> FakeExecutor:
    return FakeExecutor(dict(SAMPLE))


async def make_run(host: Host, rules: RuleSet, executor: FakeExecutor) -> RunReport:
    run = RunReport.new(inventory_path="examples/inventory.yml")
    run.hosts = [await inspect_host(host, rules, executor)]
    return run.finalize()


@pytest.fixture
def run_report(host, rules, fake_executor):
    return asyncio.run(make_run(host, rules, fake_executor))
