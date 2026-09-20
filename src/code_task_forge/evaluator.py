from __future__ import annotations

from pathlib import Path

from .models import EvaluationReport, FailureKind
from .profiler import RepositoryProfiler
from .runner import CommandPolicyError, SandboxedRunner


class EvaluationPipeline:
    def __init__(
        self,
        profiler: RepositoryProfiler | None = None,
        runner: SandboxedRunner | None = None,
    ) -> None:
        self.profiler = profiler or RepositoryProfiler()
        self.runner = runner or SandboxedRunner()

    @staticmethod
    def _classify(output: str, exit_code: int | None, timed_out: bool) -> FailureKind:
        if timed_out:
            return FailureKind.TIMEOUT
        if exit_code == 0:
            return FailureKind.NONE
        lowered = output.lower()
        if "no module named" in lowered or "could not find a version" in lowered:
            return FailureKind.DEPENDENCY
        if "collected 0 items" in lowered or "no tests ran" in lowered:
            return FailureKind.NO_TESTS
        if "syntaxerror" in lowered or "compilation failed" in lowered:
            return FailureKind.BUILD
        return FailureKind.TEST

    def evaluate(self, root: Path, command: tuple[str, ...]) -> EvaluationReport:
        profile = self.profiler.profile(root)
        signals: list[str] = []
        score = 0

        if profile.manifests:
            score += 20
            signals.append("dependency manifest detected")
        if profile.test_files:
            score += 20
            signals.append(f"{len(profile.test_files)} test file(s) detected")
        if len(profile.languages) > 1:
            score += 10
            signals.append("multi-language repository")

        try:
            result = self.runner.run(root, command)
        except CommandPolicyError:
            from .models import CommandResult

            result = CommandResult(command, None, 0.0, "", "blocked by command policy")
            return EvaluationReport(profile, result, FailureKind.POLICY, score, tuple(signals))

        failure = self._classify(
            f"{result.stdout}\n{result.stderr}", result.exit_code, result.timed_out
        )
        if failure is FailureKind.NONE:
            score += 50
            signals.append("validation command passed")
        return EvaluationReport(profile, result, failure, min(score, 100), tuple(signals))

