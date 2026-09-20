from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from .models import CommandResult

MAX_OUTPUT_CHARS = 20_000


class CommandPolicyError(ValueError):
    pass


class SandboxedRunner:
    """A small, shell-free runner with an explicit test-command allowlist."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _allowed(command: tuple[str, ...]) -> bool:
        if not command:
            return False
        executable = Path(command[0]).name
        if executable in {"python", "python3"} or executable.startswith("python3."):
            return command[1:3] == ("-m", "pytest")
        prefixes = {
            "pytest": (),
            "ruff": ("check",),
            "npm": ("test",),
            "go": ("test",),
        }
        required = prefixes.get(executable)
        return required is not None and command[1 : 1 + len(required)] == required

    def run(self, root: Path, command: tuple[str, ...]) -> CommandResult:
        resolved = root.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("workspace must be a directory")
        if not self._allowed(command):
            raise CommandPolicyError("command is not in the evaluation allowlist")

        started = time.perf_counter()
        env = {key: value for key, value in os.environ.items() if key in {"PATH", "LANG", "LC_ALL"}}
        env["PYTHONNOUSERSITE"] = "1"
        try:
            completed = subprocess.run(
                command,
                cwd=resolved,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
                check=False,
            )
            return CommandResult(
                command=command,
                exit_code=completed.returncode,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                stdout=completed.stdout[-MAX_OUTPUT_CHARS:],
                stderr=completed.stderr[-MAX_OUTPUT_CHARS:],
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=command,
                exit_code=None,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                stdout=(exc.stdout or "")[-MAX_OUTPUT_CHARS:],
                stderr=(exc.stderr or "")[-MAX_OUTPUT_CHARS:],
                timed_out=True,
            )

