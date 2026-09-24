"""code-task-forge profile | tasks | evaluate | benchmark"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .benchmark import DEFAULT_BENCHMARK, run
from .harness import JUDGES, Harness, load_tasks
from .profiler import RepositoryProfiler


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="code-task-forge", description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    sub = parser.add_subparsers(dest="command", required=True)
    prof = sub.add_parser("profile", help="languages, manifests and test files of a repository")
    prof.add_argument("path", type=Path)
    sub.add_parser("tasks", help="list the tasks and their issue text")
    ev = sub.add_parser("evaluate", help="judge one patch for one task")
    ev.add_argument("--task", required=True)
    ev.add_argument("--patch", type=Path, required=True)
    ev.add_argument("--judge", default=JUDGES[-1], choices=JUDGES)
    bench = sub.add_parser("benchmark", help="every candidate patch under every judge")
    bench.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    if args.command == "profile":
        print(json.dumps(asdict(RepositoryProfiler().profile(args.path)), indent=2))
    elif args.command == "tasks":
        for task in load_tasks(args.benchmark).values():
            print(f"{task.id:10s} {task.issue}")
    elif args.command == "evaluate":
        task = load_tasks(args.benchmark)[args.task]
        verdict = Harness(args.benchmark).evaluate(task, args.patch.read_text(), args.judge)
        print(json.dumps(verdict.to_dict(), indent=2))
    else:
        result = run(args.benchmark)
        text = json.dumps(result, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text)
        for judge in JUDGES:
            s = result["judges"][judge]
            print(f"{judge:28s} accepted {s['accepted']:3d}  false accepts {s['false_accepts']:3d}  "
                  f"false rejects {s['false_rejects']}")  # fmt: skip


if __name__ == "__main__":
    main()
