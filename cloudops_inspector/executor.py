"""Command execution backends: SSH, local, and a static backend for tests/demo."""

from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

from .inventory import Host


@dataclass
class CommandResult:
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    elapsed_ms: float = 0.0
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and self.exit_code == 0

    @property
    def missing(self) -> bool:
        text = (self.stderr + " " + self.stdout).lower()
        return self.exit_code == 127 or "command not found" in text or "not found" in text


class BaseExecutor(ABC):
    @abstractmethod
    async def run_many(
        self, host: Host, commands: Dict[str, str], timeout: int = 15
    ) -> Dict[str, CommandResult]:
        """Run a mapping of check_id -> shell command and return results."""


class SSHExecutor(BaseExecutor):
    def __init__(self, connect_timeout: int = 10, known_hosts: Optional[str] = None):
        self.connect_timeout = connect_timeout
        self.known_hosts = known_hosts

    async def run_many(
        self, host: Host, commands: Dict[str, str], timeout: int = 15
    ) -> Dict[str, CommandResult]:
        import asyncssh

        results: Dict[str, CommandResult] = {}
        kwargs = {
            "host": host.address,
            "port": host.port,
            "username": host.user,
            "known_hosts": host.known_hosts or self.known_hosts,
            "connect_timeout": self.connect_timeout,
            "login_timeout": self.connect_timeout,
        }
        if host.key:
            kwargs["client_keys"] = [host.key]
        if host.password_env:
            password = os.environ.get(host.password_env)
            if password:
                kwargs["password"] = password

        try:
            async with asyncssh.connect(**kwargs) as connection:
                for check_id, command in commands.items():
                    started = time.perf_counter()
                    try:
                        result = await asyncio.wait_for(
                            connection.run(command, check=False), timeout=timeout
                        )
                        results[check_id] = CommandResult(
                            command=command,
                            stdout=result.stdout or "",
                            stderr=result.stderr or "",
                            exit_code=result.exit_status or 0,
                            elapsed_ms=(time.perf_counter() - started) * 1000,
                        )
                    except asyncio.TimeoutError:
                        results[check_id] = CommandResult(
                            command=command,
                            exit_code=-1,
                            error=f"timeout after {timeout}s",
                            elapsed_ms=(time.perf_counter() - started) * 1000,
                        )
        except Exception as exc:  # connection/auth/host key failures
            for check_id, command in commands.items():
                results[check_id] = CommandResult(
                    command=command,
                    exit_code=-1,
                    error=str(exc),
                )
        return results


class OpenSSHExecutor(BaseExecutor):
    """Use the system OpenSSH client (reliable on Windows and CentOS).

    asyncssh is kept as an optional backend, but the OpenSSH CLI is the default
    because it honours the user's normal SSH configuration and works with
    servers that are picky about client behaviour.
    """

    def __init__(self, connect_timeout: int = 10):
        self.connect_timeout = connect_timeout

    async def run_many(
        self, host: Host, commands: Dict[str, str], timeout: int = 15
    ) -> Dict[str, CommandResult]:
        results: Dict[str, CommandResult] = {}
        target = f"{host.user}@{host.address}"
        for check_id, command in commands.items():
            started = time.perf_counter()
            args = [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "LogLevel=ERROR",
                "-o",
                f"ConnectTimeout={self.connect_timeout}",
                "-p",
                str(host.port),
            ]
            if host.key:
                args.extend(["-i", host.key])
            args.extend([target, command])
            try:
                process = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                stderr_text = (stderr or b"").decode("utf-8", errors="replace")
                results[check_id] = CommandResult(
                    command=command,
                    stdout=(stdout or b"").decode("utf-8", errors="replace"),
                    stderr=stderr_text,
                    exit_code=process.returncode or 0,
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                    error=stderr_text.strip() if process.returncode == 255 else "",
                )
            except asyncio.TimeoutError:
                results[check_id] = CommandResult(
                    command=command,
                    exit_code=-1,
                    error=f"timeout after {timeout}s",
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                )
            except Exception as exc:
                results[check_id] = CommandResult(
                    command=command,
                    exit_code=-1,
                    error=str(exc),
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                )
        return results


class LocalExecutor(BaseExecutor):
    async def run_many(
        self, host: Host, commands: Dict[str, str], timeout: int = 15
    ) -> Dict[str, CommandResult]:
        results: Dict[str, CommandResult] = {}
        for check_id, command in commands.items():
            started = time.perf_counter()
            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                results[check_id] = CommandResult(
                    command=command,
                    stdout=(stdout or b"").decode("utf-8", errors="replace"),
                    stderr=(stderr or b"").decode("utf-8", errors="replace"),
                    exit_code=process.returncode or 0,
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                )
            except asyncio.TimeoutError:
                results[check_id] = CommandResult(
                    command=command,
                    exit_code=-1,
                    error=f"timeout after {timeout}s",
                )
            except Exception as exc:
                results[check_id] = CommandResult(
                    command=command,
                    exit_code=-1,
                    error=str(exc),
                )
        return results


class StaticExecutor(BaseExecutor):
    """Return canned outputs, keyed by a substring of the command.

    Used by tests and by `--demo`; never touches a real host.
    """

    def __init__(self, outputs: Dict[str, str], exit_code: int = 0):
        self.outputs = outputs
        self.exit_code = exit_code

    async def run_many(
        self, host: Host, commands: Dict[str, str], timeout: int = 15
    ) -> Dict[str, CommandResult]:
        results = {}
        for check_id, command in commands.items():
            matched = ""
            for needle, output in self.outputs.items():
                if needle in command:
                    matched = output
                    break
            results[check_id] = CommandResult(
                command=command,
                stdout=matched,
                exit_code=self.exit_code if matched else 127,
                stderr="" if matched else "command not found",
            )
        return results


def create_executor(host: Host) -> BaseExecutor:
    if host.is_local:
        return LocalExecutor()
    if os.environ.get("CLOUDOPS_SSH_BACKEND", "openssh").lower() == "asyncssh":
        return SSHExecutor()
    return OpenSSHExecutor()
