"""Judging a candidate patch for a task, three ways.

``exit code``
    Apply the patch as written (test edits included) and accept if the task's
    test file exits 0. This is what "the agent ran the tests and they passed"
    usually means.
``fail-to-pass + pass-to-pass``
    The SWE-bench protocol: restore the original test files after applying the
    patch, then require every test that reproduces the issue to pass and every
    test that passed before to keep passing.
``+ hidden tests``
    The same, plus held-out tests that the agent never saw. This is the only
    one of the three that can tell a fix from a patch fitted to the visible tests.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .patch import PatchPolicyError, apply, touched_paths
from .runner import CommandResult, SandboxedRunner, junit_outcomes

JUDGES = ("exit code", "fail-to-pass + pass-to-pass", "+ hidden tests")
FAILURE_KINDS = (
    "none",
    "policy",
    "patch_does_not_apply",
    "timeout",
    "build",
    "dependency",
    "tests_failed",
    "fail_to_pass",
    "regression",
    "hidden_tests",
)
_DEPENDENCY = re.compile(r"\b(ModuleNotFoundError|ImportError)\b")
# a test module failed to import: pytest reports the file itself as an error
_COLLECTION_ERROR = re.compile(r"errors? during collection|^ERROR \S+\.py(?:\s|$)", re.MULTILINE)


@dataclass(frozen=True)
class Task:
    id: str
    file: str
    test_file: str
    issue: str
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    hidden: tuple[str, ...]


@dataclass
class Verdict:
    task: str
    judge: str
    accepted: bool
    failure: str
    tampered_tests: bool = False
    tests: dict[str, str] = field(default_factory=dict)  # test id -> outcome
    runs: int = 0
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def load_tasks(benchmark: Path) -> dict[str, Task]:
    raw = json.loads((benchmark / "tasks.json").read_text())
    return {t["id"]: Task(**{k: tuple(v) if isinstance(v, list) else v for k, v in t.items()}) for t in raw}


class Harness:
    def __init__(self, benchmark: Path, timeout_seconds: float = 5.0) -> None:
        # Without pytest every candidate would fail to run and be reported as a patch failure.
        if importlib.util.find_spec("pytest") is None:
            raise RuntimeError(f"pytest is not installed for {sys.executable}; run `pip install pytest`")
        self.benchmark = benchmark
        self.repo = benchmark / "repo"
        self.hidden = benchmark / "hidden"
        self.runner = SandboxedRunner(timeout_seconds)

    def _pytest(self, workspace: Path, ids: list[str]) -> tuple[CommandResult, dict[str, str]]:
        report = workspace.parent / "report.xml"
        report.unlink(missing_ok=True)
        cmd = (sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}", *ids)
        result = self.runner.run(workspace, cmd)
        return result, junit_outcomes(report)

    @staticmethod
    def _crash_kind(result: CommandResult) -> str | None:
        if result.timed_out:
            return "timeout"
        if not _COLLECTION_ERROR.search(result.output):
            return None
        if _DEPENDENCY.search(result.output):
            return "dependency"
        return "build"  # the code under test could not even be imported

    def evaluate(self, task: Task, patch: str, judge: str) -> Verdict:
        if judge not in JUDGES:
            raise ValueError(f"unknown judge {judge!r}")
        paths = touched_paths(patch)
        tampered = any(p.startswith("tests/") for p in paths)
        with tempfile.TemporaryDirectory(prefix="ctf-") as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(self.repo, workspace)
            try:
                applied, message = apply(workspace, patch)
            except PatchPolicyError as exc:
                return Verdict(task.id, judge, False, "policy", tampered, detail=str(exc))
            if not applied:
                return Verdict(task.id, judge, False, "patch_does_not_apply", tampered, detail=message)

            if judge == "exit code":
                result, outcomes = self._pytest(workspace, [task.test_file])
                ok = result.exit_code == 0
                failure = "none" if ok else self._crash_kind(result) or "tests_failed"
                return Verdict(task.id, judge, ok, failure, tampered, outcomes, 1)

            shutil.rmtree(workspace / "tests")  # the patch does not get to change how it is judged
            shutil.copytree(self.repo / "tests", workspace / "tests")
            ids = [*task.fail_to_pass, *task.pass_to_pass]
            if judge == "+ hidden tests":
                for test_id in task.hidden:
                    name = test_id.split("::")[0].split("/")[-1]
                    shutil.copy(self.hidden / name, workspace / "tests" / name)
                ids += list(task.hidden)
            result, outcomes = self._pytest(workspace, ids)

        def all_pass(group) -> bool:
            return all(outcomes.get(t) == "passed" for t in group)

        crash = self._crash_kind(result)
        if crash:
            failure = crash
        elif not all_pass(task.fail_to_pass):
            failure = "fail_to_pass"
        elif not all_pass(task.pass_to_pass):
            failure = "regression"
        elif judge == "+ hidden tests" and not all_pass(task.hidden):
            failure = "hidden_tests"
        else:
            failure = "none"
        return Verdict(task.id, judge, failure == "none", failure, tampered, outcomes, 1)
