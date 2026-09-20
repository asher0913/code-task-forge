from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from code_task_forge.api import create_app
from code_task_forge.evaluator import EvaluationPipeline
from code_task_forge.models import FailureKind
from code_task_forge.profiler import RepositoryProfiler


def sample_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "sample"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='sample'\nversion='0.1.0'\n")
    (repo / "src" / "maths.py").write_text("def add(a, b): return a + b\n")
    (repo / "tests" / "test_maths.py").write_text("def test_add(): assert 1 + 1 == 2\n")
    return repo


def test_profiles_repository(tmp_path: Path) -> None:
    profile = RepositoryProfiler().profile(sample_repository(tmp_path))
    assert profile.languages == {"Python": 2}
    assert profile.manifests == ("pyproject.toml",)
    assert profile.test_files == ("tests/test_maths.py",)


def test_evaluates_passing_workspace(tmp_path: Path) -> None:
    report = EvaluationPipeline().evaluate(
        sample_repository(tmp_path), (sys.executable, "-m", "pytest", "-q")
    )
    assert report.failure_kind is FailureKind.NONE
    assert report.score == 90


def test_blocks_unapproved_command(tmp_path: Path) -> None:
    report = EvaluationPipeline().evaluate(sample_repository(tmp_path), ("sh", "-c", "echo bad"))
    assert report.failure_kind is FailureKind.POLICY
    assert report.result.exit_code is None


def test_api_rejects_workspace_escape(tmp_path: Path) -> None:
    client = TestClient(create_app(workspace=tmp_path))
    response = client.post("/v1/evaluate", json={"repository": "../outside"})
    assert response.status_code == 400

