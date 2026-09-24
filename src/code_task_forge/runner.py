"""Bounded, shell-free command execution and per-test outcomes from JUnit XML."""

from __future__ import annotations

import os
import signal
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

MAX_OUTPUT_CHARS = 20_000
ENV_KEEP = ("PATH", "LANG", "LC_ALL", "SYSTEMROOT")
ENV_FIXED = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0"}


class CommandPolicyError(ValueError):
    """The command is not on the allowlist."""


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    exit_code: int | None
    duration_ms: float
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def output(self) -> str:
        return f"{self.stdout}\n{self.stderr}"


def allowed(command: tuple[str, ...]) -> bool:
    """Only test runners and linters, invoked directly (never through a shell)."""
    if not command:
        return False
    executable = Path(command[0]).name
    if executable in {"python", "python3"} or executable.startswith("python3."):
        return command[1:3] == ("-m", "pytest")
    prefixes = {"pytest": (), "ruff": ("check",), "npm": ("test",), "go": ("test",)}
    required = prefixes.get(executable)
    return required is not None and command[1 : 1 + len(required)] == required


class SandboxedRunner:
    """Runs an allowlisted command in a workspace with a scrubbed environment and a hard timeout.

    The child gets its own process group, so a timeout kills everything it
    spawned, not just the direct child. This is a policy layer, not an OS
    sandbox: untrusted code belongs in a container or microVM as well.
    """

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, root: Path, command: tuple[str, ...]) -> CommandResult:
        resolved = root.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("workspace must be a directory")
        if not allowed(command):
            raise CommandPolicyError(f"command is not in the evaluation allowlist: {command[:3]}")
        env = {k: v for k, v in os.environ.items() if k in ENV_KEEP} | ENV_FIXED
        started = time.perf_counter()
        proc = subprocess.Popen(
            command,
            cwd=resolved,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=self.timeout_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            timed_out = True
        return CommandResult(
            command=command,
            exit_code=None if timed_out else proc.returncode,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            stdout=(stdout or "")[-MAX_OUTPUT_CHARS:],
            stderr=(stderr or "")[-MAX_OUTPUT_CHARS:],
            timed_out=timed_out,
        )


def junit_outcomes(xml_path: Path) -> dict[str, str]:
    """test id (``tests/test_x.py::test_name``) -> passed | failed | error | skipped."""
    if not xml_path.exists():
        return {}
    outcomes = {}
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        classname, name = case.get("classname", ""), case.get("name", "")
        if not classname:
            continue
        test_id = f"{classname.replace('.', '/')}.py::{name}"
        kinds = {child.tag for child in case}
        outcomes[test_id] = next((k for k in ("error", "failure", "skipped") if k in kinds), "passed")
        if outcomes[test_id] == "failure":
            outcomes[test_id] = "failed"
    return outcomes
