"""Every candidate patch under every judge: false accepts, false rejects and failure classification."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from math import comb
from pathlib import Path

from .harness import JUDGES, Harness, load_tasks

DEFAULT_BENCHMARK = Path(os.getenv("CODETASKFORGE_BENCHMARK", Path(__file__).resolve().parents[2] / "benchmark"))


def load_candidates(benchmark: Path) -> list[dict]:
    return json.loads((benchmark / "candidates" / "manifest.json").read_text())


def run(benchmark: Path = DEFAULT_BENCHMARK, workers: int | None = None, timeout_seconds: float = 5.0) -> dict:
    tasks = load_tasks(benchmark)
    candidates = load_candidates(benchmark)
    harness = Harness(benchmark, timeout_seconds)
    jobs = [(c, judge) for c in candidates for judge in JUDGES]

    def one(job):
        cand, judge = job
        verdict = harness.evaluate(tasks[cand["task"]], (benchmark / cand["patch"]).read_text(), judge)
        return {
            "task": cand["task"],
            "kind": cand["kind"],
            "correct": cand["correct"],
            "judge": judge,
            "accepted": verdict.accepted,
            "failure": verdict.failure,
            "tampered_tests": verdict.tampered_tests,
            "ran_tests": verdict.runs > 0,
            "hidden_total": len(tasks[cand["task"]].hidden),
            "hidden_failed": sum(verdict.tests.get(h) != "passed" for h in tasks[cand["task"]].hidden)
            if judge == JUDGES[-1] and verdict.runs
            else None,
        }

    with ThreadPoolExecutor(max_workers=workers or min(8, os.cpu_count() or 2)) as pool:
        rows = list(pool.map(one, jobs))
    return {"tasks": len(tasks), "candidates": len(candidates), "judges": summarise(rows, candidates), "verdicts": rows}


def hidden_test_budget(rows: list[dict]) -> dict:
    """Among wrong patches that pass every visible test, the expected share caught if only k
    of a task's hidden tests (chosen at random) were run."""
    fooled = [r for r in rows if r["kind"] in ("overfit", "plausible_wrong")]
    most = max((r["hidden_total"] for r in fooled), default=0)
    curve = {}
    for k in range(1, most + 1):
        caught = [
            1
            - comb(r["hidden_total"] - r["hidden_failed"], min(k, r["hidden_total"]))
            / comb(r["hidden_total"], min(k, r["hidden_total"]))
            for r in fooled
        ]
        curve[str(k)] = round(100 * sum(caught) / len(caught), 1)
    return {
        "patches": len(fooled),
        "hidden_tests_failed": dict(sorted(Counter(r["hidden_failed"] for r in fooled).items())),
        "caught_pct_with_k_hidden_tests": curve,
    }


def summarise(rows: list[dict], candidates: list[dict]) -> dict:
    expected = {(c["task"], c["kind"]): c["expected_failure"] for c in candidates}
    out = {}
    for judge in JUDGES:
        mine = [r for r in rows if r["judge"] == judge]
        by_kind: dict[str, Counter] = defaultdict(Counter)
        for r in mine:
            by_kind[r["kind"]]["candidates"] += 1
            by_kind[r["kind"]]["accepted"] += r["accepted"]
        accepted = [r for r in mine if r["accepted"]]
        wrong = [r for r in accepted if not r["correct"]]
        rejected_good = [r for r in mine if r["correct"] and not r["accepted"]]
        out[judge] = {
            "accepted": len(accepted),
            "false_accepts": len(wrong),
            "false_rejects": len(rejected_good),
            "accepted_that_are_correct_pct": round(100 * (len(accepted) - len(wrong)) / len(accepted), 1)
            if accepted
            else 0.0,
            "false_accepts_by_kind": dict(sorted(Counter(r["kind"] for r in wrong).items())),
            "accepted_by_kind": {k: f"{v['accepted']}/{v['candidates']}" for k, v in sorted(by_kind.items())},
            "pytest_runs": sum(r["ran_tests"] for r in mine),
        }
    strongest = [r for r in rows if r["judge"] == JUDGES[-1]]
    confusion: dict[str, Counter] = defaultdict(Counter)
    for r in strongest:
        confusion[expected[(r["task"], r["kind"])]][r["failure"]] += 1
    out["hidden_test_budget"] = hidden_test_budget(strongest)
    out["failure_classification"] = {
        "judge": JUDGES[-1],
        "matches_expected": sum(r["failure"] == expected[(r["task"], r["kind"])] for r in strongest),
        "of": len(strongest),
        "expected_vs_reported": {k: dict(sorted(v.items())) for k, v in sorted(confusion.items())},
    }
    return out
