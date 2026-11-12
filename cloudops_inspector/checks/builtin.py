"""Built-in read-only checks for Linux, SSH and Docker."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from ..executor import CommandResult
from ..models import CheckResult, Status
from ..rules import expected_status, threshold_status
from .base import Check


def _lines(result: CommandResult) -> List[str]:
    return [line for line in result.stdout.splitlines() if line.strip()]


def _int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class CpuUsageCheck(Check):
    id = "cpu_usage"
    name = "CPU 使用率"
    category = "system"
    command = "vmstat 1 2 | tail -1"
    remediation = "排查高 CPU 进程（top -Hp），确认是否为业务高峰或异常进程。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        lines = _lines(result)
        if not lines:
            return self.error(result, "vmstat 无输出")
        parts = lines[-1].split()
        if len(parts) < 15:
            return self.error(result, "vmstat 输出字段不足")
        idle = float(parts[14])
        usage = round(100 - idle, 2)
        details = [f"us={parts[12]} sy={parts[13]} id={parts[14]} wa={parts[15] if len(parts) > 15 else '?'}"]
        return self.threshold(usage, rule, "%", "CPU 使用率", result, details)


class LoadCheck(Check):
    id = "load_per_core"
    name = "每核负载"
    category = "system"
    command = "cat /proc/loadavg; nproc"
    remediation = "负载持续高于核数时，检查 CPU 密集进程、IO wait 和容器资源限制。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        lines = _lines(result)
        if len(lines) < 2:
            return self.error(result, "无法读取 loadavg/nproc")
        parts = lines[0].split()
        cores = _int(lines[-1])
        if not parts or cores <= 0:
            return self.error(result, "loadavg 或 CPU 核数无效")
        load1 = float(parts[0])
        value = round(load1 / cores, 2)
        return self.threshold(value, rule, "", "每核 load1", result, [f"load1={load1} cores={cores}"])


class MemoryUsageCheck(Check):
    id = "memory_usage"
    name = "内存使用率"
    category = "system"
    command = "free -b"
    remediation = "确认是否存在内存泄漏或缓存占用；必要时限制容器内存或扩容。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        for line in _lines(result):
            parts = line.split()
            if parts and parts[0] == "Mem:":
                total = float(parts[1])
                available = float(parts[6]) if len(parts) > 6 else float(parts[3]) + float(parts[5])
                if total <= 0:
                    return self.error(result, "Mem total 为 0")
                used_pct = (total - available) / total * 100
                return self.threshold(used_pct, rule, "%", "内存使用率", result, [f"total={total/1024**3:.1f}GiB available={available/1024**3:.1f}GiB"])
        return self.error(result, "free 输出中没有 Mem 行")


class SwapUsageCheck(Check):
    id = "swap_usage"
    name = "Swap 使用率"
    category = "system"
    command = "free -b"
    remediation = "Swap 持续使用说明内存压力大；检查内存占用，避免依赖 swap 运行数据库。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        for line in _lines(result):
            parts = line.split()
            if parts and parts[0] == "Swap:":
                total = float(parts[1])
                used = float(parts[2])
                if total <= 0:
                    return self.result(Status.OK, "未启用 Swap", result=result, value=0.0, unit="%")
                usage = used / total * 100
                return self.threshold(usage, rule, "%", "Swap 使用率", result, [f"used={used/1024**3:.1f}GiB total={total/1024**3:.1f}GiB"])
        return self.error(result, "free 输出中没有 Swap 行")


class DiskUsageCheck(Check):
    id = "disk_usage"
    name = "磁盘使用率"
    category = "system"
    command = "df -P -x tmpfs -x devtmpfs -x squashfs"
    remediation = "清理日志/镜像层，或扩容磁盘；不要只删除大文件而不排查增长来源。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        entries = []
        for line in _lines(result)[1:]:
            parts = line.split()
            if len(parts) < 6:
                continue
            try:
                pct = float(parts[4].rstrip("%"))
            except ValueError:
                continue
            entries.append((pct, parts[5]))
        if not entries:
            return self.error(result, "df 没有可用行")
        value, mount = max(entries, key=lambda item: item[0])
        details = [f"{m}={p:.0f}%" for p, m in sorted(entries, reverse=True)[:5]]
        return self.threshold(value, rule, "%", f"最高磁盘使用率 ({mount})", result, details)


class InodeUsageCheck(Check):
    id = "inode_usage"
    name = "Inode 使用率"
    category = "system"
    command = "df -Pi -x tmpfs -x devtmpfs -x squashfs"
    remediation = "Inode 耗尽常见于大量小文件；清理临时文件/邮件队列/容器日志目录。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        entries = []
        for line in _lines(result)[1:]:
            parts = line.split()
            if len(parts) < 6:
                continue
            try:
                pct = float(parts[4].rstrip("%"))
            except ValueError:
                continue
            entries.append((pct, parts[5]))
        if not entries:
            return self.error(result, "df -Pi 没有可用行")
        value, mount = max(entries, key=lambda item: item[0])
        details = [f"{m}={p:.0f}%" for p, m in sorted(entries, reverse=True)[:5]]
        return self.threshold(value, rule, "%", f"最高 inode 使用率 ({mount})", result, details)


class FailedUnitsCheck(Check):
    id = "failed_units"
    name = "systemd 失败单元"
    category = "system"
    command = "systemctl --failed --no-legend --plain"
    remediation = "systemctl status <unit> 查看失败原因；修复后 systemctl reset-failed。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        units = _lines(result)
        value = len(units)
        status = threshold_status(value, rule)
        details = units[:8]
        return self.result(status, f"失败单元: {value}", result=result, value=value, unit="个", details=details)


class ZombieCheck(Check):
    id = "zombie_processes"
    name = "僵尸进程"
    category = "system"
    command = "ps -eo stat= | awk '$1 ~ /^Z/ {c++} END {print c+0}'"
    remediation = "僵尸进程通常由父进程未回收导致；检查父进程并重启对应服务。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        text = result.stdout.strip()
        count = _int(text)
        return self.threshold(count, rule, "个", "僵尸进程数", result)


class FdUsageCheck(Check):
    id = "fd_usage"
    name = "文件描述符使用率"
    category = "system"
    command = "cat /proc/sys/fs/file-nr"
    remediation = "排查 fd 泄漏（lsof -p <pid>）；必要时调整 fs.file-max 或进程 limits。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        parts = result.stdout.split()
        if len(parts) < 3:
            return self.error(result, "file-nr 字段不足")
        allocated = float(parts[0])
        maximum = float(parts[2])
        if maximum <= 0:
            return self.error(result, "file-nr 上限为 0")
        usage = allocated / maximum * 100
        return self.threshold(usage, rule, "%", "文件描述符使用率", result, [f"allocated={int(allocated)} max={int(maximum)}"])


class LogDirSizeCheck(Check):
    id = "log_dir_size"
    name = "日志目录大小"
    category = "system"
    command = "du -sb /var/log 2>/dev/null | cut -f1"
    remediation = "检查日志轮转（logrotate）和 journald 限制；不要直接删除正在写入的日志。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        text = result.stdout.strip()
        if not text:
            return self.error(result, "无法读取 /var/log 大小")
        size_gb = float(text) / 1024**3
        return self.threshold(size_gb, rule, "GB", "日志目录大小", result)


class DockerServiceCheck(Check):
    id = "docker_service"
    name = "Docker 服务状态"
    category = "docker"
    command = "systemctl is-active docker 2>/dev/null; command -v docker || true"
    remediation = "systemctl status docker / journalctl -u docker 查看启动失败原因。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        lines = _lines(result)
        has_binary = any(line.startswith("/") for line in lines[1:])
        if not has_binary:
            return self.skip(result, "未安装 Docker")
        state = lines[0] if lines else "unknown"
        status = Status.OK if state == "active" else Status.WARN
        return self.result(status, f"Docker 服务: {state}", result=result, details=[f"state={state}"])


class DockerContainersCheck(Check):
    id = "docker_containers"
    name = "Docker 容器健康"
    category = "docker"
    command = "docker ps -a --format '{{.Names}}|{{.State}}|{{.Status}}'"
    remediation = "查看 docker ps -a / docker logs <name>；反复重启要检查应用日志和资源限制。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        if result.missing:
            return self.skip(result, "未安装 Docker")
        if not result.ok and not result.stdout.strip():
            return self.error(result, f"docker ps 执行失败: {result.stderr.strip()[:200]}")
        unhealthy = 0
        restarting = 0
        details = []
        total = 0
        for line in _lines(result):
            parts = line.split("|")
            if len(parts) < 3:
                continue
            total += 1
            name, state, status_text = parts[0], parts[1], parts[2]
            if "unhealthy" in status_text.lower():
                unhealthy += 1
                details.append(f"{name}: {status_text}")
            if state.lower() == "restarting" or "restarting" in status_text.lower():
                restarting += 1
                details.append(f"{name}: restarting")
        status = max(
            (threshold_status(unhealthy, rule), threshold_status(restarting, rule)),
            key=lambda item: [Status.OK, Status.WARN, Status.CRIT].index(item),
        )
        return self.result(
            status,
            f"容器 {total} 个；unhealthy={unhealthy} restarting={restarting}",
            result=result,
            value=float(unhealthy + restarting),
            unit="个",
            details=details[:8],
        )


class DockerDiskCheck(Check):
    id = "docker_disk"
    name = "Docker 可回收空间"
    category = "docker"
    command = "docker system df --format '{{.Type}}|{{.Size}}|{{.Reclaimable}}'"
    remediation = "确认无用镜像/容器后执行 docker image prune / docker system prune，避免误删运行中依赖。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        if result.missing:
            return self.skip(result, "未安装 Docker")
        max_pct = 0.0
        details = []
        for line in _lines(result):
            match = re.search(r"\(([\d.]+)%\)", line)
            if not match:
                continue
            pct = float(match.group(1))
            max_pct = max(max_pct, pct)
            details.append(line)
        return self.threshold(max_pct, rule, "%", "Docker 可回收空间", result, details[:6])


class ListeningPortsCheck(Check):
    id = "listening_ports"
    name = "监听端口"
    category = "network"
    command = "ss -lntu"
    remediation = "核对非预期端口；云服务器应只开放业务和安全组允许的端口。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        if result.missing:
            return self.skip(result, "未安装 ss")
        lines = _lines(result)
        if not lines:
            return self.error(result, "ss 无输出")
        ports = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 5:
                ports.append(parts[4])
        return self.result(
            Status.OK,
            f"监听端口 {len(ports)} 个",
            result=result,
            value=float(len(ports)),
            unit="个",
            details=ports[:12],
        )


class SshConfigCheck(Check):
    id = "ssh_config"
    name = "SSH 安全基线"
    category = "security"
    command = "sshd -T 2>/dev/null | grep -E '^(permitrootlogin|passwordauthentication|maxauthtries)'"
    remediation = "建议 PermitRootLogin no/prohibit-password、PasswordAuthentication no、MaxAuthTries<=4，改完先 sshd -t 再 reload。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        if result.missing:
            return self.skip(result, "未安装 sshd")
        values = {}
        for line in _lines(result):
            parts = line.split(None, 1)
            if len(parts) == 2:
                values[parts[0].lower()] = parts[1].strip()
        if not values:
            return self.error(result, "无法读取 sshd -T（权限不足或未安装 sshd）")
        root = values.get("permitrootlogin", "yes")
        password = values.get("passwordauthentication", "yes")
        max_auth = _int(values.get("maxauthtries", "6"), 6)
        issues = []
        if root.lower() not in {"no", "prohibit-password"}:
            issues.append(f"PermitRootLogin={root}")
        if password.lower() != "no":
            issues.append(f"PasswordAuthentication={password}")
        if max_auth > 4:
            issues.append(f"MaxAuthTries={max_auth}")
        if not issues:
            return self.result(Status.OK, "SSH 基线通过", result=result, details=[f"root={root} password={password} max_auth={max_auth}"])
        severity = str(rule.get("severity", "warn")).lower()
        status = Status.CRIT if severity == "crit" else Status.WARN
        return self.result(status, "SSH 配置存在风险: " + "; ".join(issues), result=result, details=issues)


class FirewalldCheck(Check):
    id = "firewalld"
    name = "防火墙状态"
    category = "security"
    command = "systemctl is-active firewalld 2>/dev/null"
    remediation = "云服务器至少配置安全组；如使用 firewalld，systemctl enable --now firewalld 并核对开放端口。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        if result.missing:
            return self.skip(result, "未安装 firewalld")
        state = (result.stdout.strip() or "inactive").splitlines()[0]
        status = Status.OK if state == "active" else Status.WARN
        return self.result(status, f"firewalld: {state}", result=result, details=[f"state={state}"])


class SelinuxCheck(Check):
    id = "selinux"
    name = "SELinux 状态"
    category = "security"
    command = "getenforce"
    remediation = "生产环境建议 Enforcing；切换模式前先排查 AVC 拒绝，不要直接关闭。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        if result.missing:
            return self.skip(result, "未安装 SELinux 工具")
        state = (result.stdout.strip() or "Unknown").splitlines()[0]
        status = expected_status(state, "Enforcing", rule)
        return self.result(status, f"SELinux: {state}", result=result, details=[f"state={state}"])


class ChronyCheck(Check):
    id = "chrony_synced"
    name = "时间同步"
    category = "system"
    command = "timedatectl show -p NTPSynchronized --value"
    remediation = "检查 chrony/ntp 服务与上游源；时间漂移会影响日志、证书和主从复制。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        if result.missing:
            return self.skip(result, "未安装 timedatectl")
        state = (result.stdout.strip() or "unknown").splitlines()[0]
        status = expected_status(state, "yes", rule)
        return self.result(status, f"NTP 同步: {state}", result=result, details=[f"state={state}"])


class RebootRequiredCheck(Check):
    id = "reboot_required"
    name = "是否需要重启"
    category = "maintenance"
    command = (
        "sh -c 'if command -v needs-restarting >/dev/null 2>&1; then "
        "needs-restarting -r >/dev/null 2>&1 && echo no || echo yes; "
        "elif [ -f /var/run/reboot-required ]; then echo yes; else echo no; fi'"
    )
    remediation = "内核/关键库更新后按变更窗口重启；重启前确认业务多副本和回滚预案。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        state = (result.stdout.strip() or "unknown").splitlines()[0]
        status = expected_status(state, "no", rule)
        return self.result(status, f"重启标记: {state}", result=result, details=[f"state={state}"])


class UptimeCheck(Check):
    id = "uptime"
    name = "运行时长"
    category = "system"
    command = "cat /proc/uptime"
    remediation = "运行时长仅作参考；长期不重启不代表健康，结合内核更新和安全补丁判断。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        parts = result.stdout.split()
        if not parts:
            return self.error(result, "无法读取 /proc/uptime")
        days = float(parts[0]) / 86400
        return self.result(Status.OK, f"运行 {days:.1f} 天", result=result, value=round(days, 1), unit="天")


class KernelCheck(Check):
    id = "kernel"
    name = "内核版本"
    category = "system"
    command = "uname -r"
    remediation = "仅作资产记录；内核升级请走变更流程并准备重启窗口。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        version = result.stdout.strip() or "unknown"
        return self.result(Status.OK, f"内核: {version}", result=result, details=[version])


class TimezoneCheck(Check):
    id = "timezone"
    name = "时区"
    category = "system"
    command = "timedatectl show -p Timezone --value"
    remediation = "统一使用 UTC 或业务时区，避免日志/定时任务/数据库时间不一致。"

    def evaluate(self, result: CommandResult, rule: Dict[str, Any]) -> CheckResult:
        zone = result.stdout.strip() or "unknown"
        return self.result(Status.OK, f"时区: {zone}", result=result, details=[zone])


CHECKS = [
    CpuUsageCheck(),
    LoadCheck(),
    MemoryUsageCheck(),
    SwapUsageCheck(),
    DiskUsageCheck(),
    InodeUsageCheck(),
    FailedUnitsCheck(),
    ZombieCheck(),
    FdUsageCheck(),
    LogDirSizeCheck(),
    DockerServiceCheck(),
    DockerContainersCheck(),
    DockerDiskCheck(),
    ListeningPortsCheck(),
    SshConfigCheck(),
    FirewalldCheck(),
    SelinuxCheck(),
    ChronyCheck(),
    RebootRequiredCheck(),
    UptimeCheck(),
    KernelCheck(),
    TimezoneCheck(),
]
