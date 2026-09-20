from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class FailureKind(StrEnum):
    NONE = "none"
    DEPENDENCY = "dependency"
    BUILD = "build"
    TEST = "test"
    TIMEOUT = "timeout"
    POLICY = "policy"
    NO_TESTS = "no_tests"


@dataclass(frozen=True)
class RepositoryProfile:
    root: str
    languages: dict[str, int]
    manifests: tuple[str, ...]
    test_files: tuple[str, ...]
    source_files: int
    total_files: int


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    exit_code: int | None
    duration_ms: float
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass(frozen=True)
class EvaluationReport:
    profile: RepositoryProfile
    result: CommandResult
    failure_kind: FailureKind
    score: int
    signals: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

