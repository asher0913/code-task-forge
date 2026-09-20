from __future__ import annotations

import os
import shlex
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .evaluator import EvaluationPipeline


class EvaluationBody(BaseModel):
    repository: str = Field(min_length=1)
    command: str = "python -m pytest -q"


def create_app(
    pipeline: EvaluationPipeline | None = None, workspace: Path | None = None
) -> FastAPI:
    pipeline = pipeline or EvaluationPipeline()
    workspace = (workspace or Path(os.getenv("CODETASKFORGE_WORKSPACE", "."))).resolve()
    app = FastAPI(title="CodeTaskForge", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/evaluate")
    def evaluate(body: EvaluationBody) -> dict[str, object]:
        target = (workspace / body.repository).resolve()
        if not target.is_relative_to(workspace):
            raise HTTPException(status_code=400, detail="repository escapes configured workspace")
        try:
            return pipeline.evaluate(target, tuple(shlex.split(body.command))).to_dict()
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()
