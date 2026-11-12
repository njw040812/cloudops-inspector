from __future__ import annotations

from cloudops_inspector.checks.builtin import (
    CpuUsageCheck,
    DiskUsageCheck,
    DockerContainersCheck,
    SshConfigCheck,
)
from cloudops_inspector.executor import CommandResult
from cloudops_inspector.models import Status

from conftest import SAMPLE


def test_cpu_ok(rules):
    result = CpuUsageCheck().evaluate(CommandResult("vmstat", stdout=SAMPLE["cpu_usage"]), rules.get("cpu_usage"))
    assert result.status == Status.OK
    assert result.value == 21.0


def test_disk_warn(rules):
    result = DiskUsageCheck().evaluate(CommandResult("df", stdout=SAMPLE["disk_usage"]), rules.get("disk_usage"))
    assert result.status == Status.WARN
    assert result.value == 85.0
    assert "/data" in result.summary


def test_ssh_ok(rules):
    result = SshConfigCheck().evaluate(
        CommandResult("sshd -T", stdout=SAMPLE["ssh_config"]), rules.get("ssh_config")
    )
    assert result.status == Status.OK


def test_ssh_bad_is_crit(rules):
    output = "permitrootlogin yes\npasswordauthentication yes\nmaxauthtries 6\n"
    result = SshConfigCheck().evaluate(
        CommandResult("sshd -T", stdout=output), rules.get("ssh_config")
    )
    assert result.status == Status.CRIT
    assert len(result.details) == 3


def test_docker_restarting_warn(rules):
    result = DockerContainersCheck().evaluate(
        CommandResult("docker ps", stdout=SAMPLE["docker_containers"]),
        rules.get("docker_containers"),
    )
    assert result.status == Status.WARN
    assert result.value == 1.0


def test_docker_missing_is_skip(rules):
    result = DockerContainersCheck().evaluate(
        CommandResult("docker ps", exit_code=127, stderr="command not found"),
        rules.get("docker_containers"),
    )
    assert result.status == Status.SKIP


def test_docker_broken_format_is_error(rules):
    result = DockerContainersCheck().evaluate(
        CommandResult(
            "docker ps",
            stderr="template: :1:24: executing \"\" at <.RestartCount>: can't evaluate field",
            exit_code=1,
        ),
        rules.get("docker_containers"),
    )
    assert result.status == Status.ERROR


async def test_inspect_host_all_checks(host, rules, fake_executor):
    from cloudops_inspector.checks import inspect_host

    report = await inspect_host(host, rules, fake_executor)
    assert len(report.results) == 22
    assert report.host == "centos9"
    assert 0 < report.score < 100
    assert report.counts["warn"] >= 1
    assert not [r for r in report.results if r.status == Status.ERROR]
