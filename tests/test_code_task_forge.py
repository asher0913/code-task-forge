import json
import sys
from pathlib import Path

import pytest

from code_task_forge import JUDGES, Harness, RepositoryProfiler, load_tasks
from code_task_forge.cli import main
from code_task_forge.patch import PatchPolicyError, apply, check_policy, touched_paths
from code_task_forge.runner import CommandPolicyError, SandboxedRunner

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
TASKS = load_tasks(BENCH)
EXIT, SWE, HIDDEN = JUDGES


def patch(task: str, kind: str) -> str:
    return (BENCH / "candidates" / task / f"{kind}.diff").read_text()


@pytest.fixture(scope="module")
def harness():
    return Harness(BENCH, timeout_seconds=5)


def test_profiler_counts_languages_manifests_and_tests(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    (tmp_path / "tests" / "test_a.py").write_text("def test(): pass\n")
    (tmp_path / "node_modules" / "b.js").write_text("")
    profile = RepositoryProfiler().profile(tmp_path)
    assert profile.languages == {"Python": 2}
    assert profile.manifests == ("pyproject.toml",)
    assert profile.test_files == ("tests/test_a.py",)


def test_runner_allowlist_and_scrubbed_environment(tmp_path, monkeypatch):
    runner = SandboxedRunner(timeout_seconds=30)
    with pytest.raises(CommandPolicyError):
        runner.run(tmp_path, ("sh", "-c", "echo hi"))
    with pytest.raises(CommandPolicyError):
        runner.run(tmp_path, (sys.executable, "-c", "print(1)"))
    monkeypatch.setenv("DEPLOY_TOKEN", "not-for-candidates")
    (tmp_path / "test_env.py").write_text("import os\n\ndef test():\n    assert 'DEPLOY_TOKEN' not in os.environ\n")
    result = runner.run(tmp_path, (sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"))
    assert result.exit_code == 0, result.output


def test_runner_timeout_kills_the_process_group(tmp_path):
    (tmp_path / "test_slow.py").write_text(
        "import subprocess, sys, time\n\ndef test():\n"
        "    subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n    time.sleep(60)\n"
    )
    result = SandboxedRunner(timeout_seconds=2).run(tmp_path, (sys.executable, "-m", "pytest", "-q"))
    assert result.timed_out and result.exit_code is None
    assert result.duration_ms < 10_000


def test_patch_policy():
    assert touched_paths(patch("intervals", "gold")) == ["tinylib/intervals.py"]
    assert touched_paths(patch("intervals", "test_tampering")) == ["tests/test_intervals.py"]
    check_policy(["tinylib/intervals.py", "tests/test_intervals.py"])
    for bad in (["../outside/notes.txt"], ["/etc/passwd"], [".github/workflows/ci.yml"], []):
        with pytest.raises(PatchPolicyError):
            check_policy(bad)


def test_stale_context_does_not_apply(tmp_path):
    import shutil

    ws = tmp_path / "workspace"
    shutil.copytree(BENCH / "repo", ws)
    assert apply(ws, patch("dates", "gold")) == (True, "")
    shutil.rmtree(ws)
    shutil.copytree(BENCH / "repo", ws)
    applied, message = apply(ws, patch("dates", "stale_context"))
    assert not applied and message


def test_tasks_follow_the_swe_bench_split():
    assert len(TASKS) == 10
    for task in TASKS.values():
        assert task.fail_to_pass and task.pass_to_pass and len(task.hidden) == 4
        assert set(task.fail_to_pass).isdisjoint(task.pass_to_pass)
        assert all(t.startswith(task.test_file) for t in (*task.fail_to_pass, *task.pass_to_pass))


@pytest.mark.parametrize("judge", JUDGES)
def test_gold_and_alternative_fixes_are_accepted_by_every_judge(harness, judge):
    for kind in ("gold", "alt_correct"):
        verdict = harness.evaluate(TASKS["csvline"], patch("csvline", kind), judge)
        assert verdict.accepted and verdict.failure == "none", (kind, verdict)


def test_editing_the_tests_fools_only_the_exit_code(harness):
    task, diff = TASKS["roman"], patch("roman", "test_tampering")
    exit_code = harness.evaluate(task, diff, EXIT)
    assert exit_code.accepted and exit_code.tampered_tests
    assert all(exit_code.tests[t] == "skipped" for t in task.fail_to_pass)
    swe = harness.evaluate(task, diff, SWE)
    assert not swe.accepted and swe.failure == "fail_to_pass" and swe.tampered_tests


def test_fitting_the_visible_tests_is_caught_only_by_hidden_tests(harness):
    for kind in ("overfit", "plausible_wrong"):
        assert harness.evaluate(TASKS["dates"], patch("dates", kind), SWE).accepted
        verdict = harness.evaluate(TASKS["dates"], patch("dates", kind), HIDDEN)
        assert not verdict.accepted and verdict.failure == "hidden_tests"


@pytest.mark.parametrize(
    ("task", "kind", "failure"),
    [
        ("text", "partial", "fail_to_pass"),
        ("backoff", "regression", "regression"),
        ("lru", "syntax_error", "build"),
        ("stats", "missing_import", "dependency"),
        ("paginate", "infinite_loop", "timeout"),
        ("semver", "stale_context", "patch_does_not_apply"),
        ("intervals", "path_escape", "policy"),
    ],
)
def test_failure_taxonomy(harness, task, kind, failure):
    verdict = harness.evaluate(TASKS[task], patch(task, kind), HIDDEN)
    assert (verdict.accepted, verdict.failure) == (False, failure)


def test_committed_results_headline():
    result = json.loads((ROOT / "results" / "benchmark.json").read_text())
    judges = result["judges"]
    assert [judges[j]["false_accepts"] for j in JUDGES] == [25, 15, 0]
    assert all(judges[j]["false_rejects"] == 0 for j in JUDGES)
    fc = judges["failure_classification"]
    assert fc["matches_expected"] == fc["of"] == result["candidates"] == 98


def test_cli_evaluate_and_tasks(capsys):
    main(["tasks"])
    assert "roman" in capsys.readouterr().out
    main(["evaluate", "--task", "roman", "--patch", str(BENCH / "candidates/roman/gold.diff")])
    assert json.loads(capsys.readouterr().out)["accepted"] is True


def test_api_hides_hidden_tests():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from code_task_forge.api import create_app

    client = TestClient(create_app(BENCH))
    listing = client.get("/v1/tasks").json()
    assert not any("hidden" in t for task in listing for t in task["visible_tests"])
    body = {"task": "semver", "patch": patch("semver", "overfit")}
    verdict = client.post("/v1/evaluate", json=body).json()
    assert verdict["failure"] == "hidden_tests" and verdict["hidden_tests_failed"] > 0
    assert not any("hidden" in t for t in verdict["tests"])
    assert client.post("/v1/evaluate", json={"task": "nope", "patch": "x"}).status_code == 404
