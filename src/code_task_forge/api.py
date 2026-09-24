"""HTTP front end for the harness (``pip install -e '.[api]'``).

The task listing exposes the issue text and the visible tests only; hidden test
ids never leave the server, so an agent calling this API cannot fit them.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .benchmark import DEFAULT_BENCHMARK
from .harness import JUDGES, Harness, load_tasks


class EvaluateBody(BaseModel):
    task: str
    patch: str = Field(min_length=1, max_length=200_000)
    judge: str = JUDGES[-1]


def create_app(benchmark: Path | None = None) -> FastAPI:
    benchmark = benchmark or DEFAULT_BENCHMARK
    tasks = load_tasks(benchmark)
    harness = Harness(benchmark)
    app = FastAPI(title="CodeTaskForge", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/tasks")
    def list_tasks() -> list[dict]:
        return [
            {"id": t.id, "issue": t.issue, "file": t.file, "visible_tests": [*t.fail_to_pass, *t.pass_to_pass]}
            for t in tasks.values()
        ]

    @app.post("/v1/evaluate")
    def evaluate(body: EvaluateBody) -> dict:
        if body.task not in tasks:
            raise HTTPException(status_code=404, detail=f"unknown task {body.task!r}")
        if body.judge not in JUDGES:
            raise HTTPException(status_code=400, detail=f"judge must be one of {list(JUDGES)}")
        verdict = harness.evaluate(tasks[body.task], body.patch, body.judge).to_dict()
        if body.judge == JUDGES[-1]:  # report hidden results as a count, not by name
            hidden = set(tasks[body.task].hidden)
            verdict["hidden_tests_failed"] = sum(o != "passed" for t, o in verdict["tests"].items() if t in hidden)
            verdict["tests"] = {t: o for t, o in verdict["tests"].items() if t not in hidden}
        return verdict

    return app
