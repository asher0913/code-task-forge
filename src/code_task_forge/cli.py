from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

from .evaluator import EvaluationPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile and evaluate a coding-agent workspace")
    parser.add_argument("repository", type=Path)
    parser.add_argument("--command", default="python -m pytest -q")
    args = parser.parse_args()
    report = EvaluationPipeline().evaluate(args.repository, tuple(shlex.split(args.command)))
    print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()

