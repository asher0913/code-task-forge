# CodeTaskForge

[![CI](https://github.com/asher0913/code-task-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/asher0913/code-task-forge/actions/workflows/ci.yml)

Reproducible repository profiling and validation for coding agents. CodeTaskForge turns a
candidate workspace into a structured report: language inventory, build manifests, test
coverage signals, command evidence, failure taxonomy, and a deterministic quality score.

It is intentionally local-first and model-agnostic. An LLM can propose a patch; CodeTaskForge
provides the bounded execution and evidence layer needed to decide whether that patch is safe to
accept.

## Why this project

Coding-agent demos often stop at “the model wrote code.” Production systems also need to answer:

- Did the candidate build and pass its tests?
- Was the validation command allowed, bounded, and reproducible?
- Did the failure come from dependencies, compilation, tests, or timeout?
- Can downstream evaluation consume the result as structured JSON?

## Architecture

```text
repository -> profiler -> allowlisted runner -> failure classifier -> JSON report
                              |                        |
                         timeout/output cap       evidence + score
```

Key implementation details:

- Multi-language repository profiler with ignored build/vendor directories and file-count limits.
- Shell-free subprocess runner with command allowlisting, sanitized environment, timeouts, and
  bounded logs.
- Failure taxonomy for dependency, build, test, timeout, policy, and no-test failures.
- FastAPI service and CLI sharing one evaluation pipeline.
- Unit tests for passing workspaces, unsafe commands, profiling, and path traversal.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest

code-task-forge . --command "python -m pytest -q"
uvicorn code_task_forge.api:app --reload
```

API example (paths are resolved under `CODETASKFORGE_WORKSPACE`):

```bash
export CODETASKFORGE_WORKSPACE=/path/to/workspaces
curl -X POST http://localhost:8000/v1/evaluate \
  -H 'content-type: application/json' \
  -d '{"repository":"candidate-01","command":"python -m pytest -q"}'
```

## Security boundary

The runner avoids a shell, restricts executable/argument prefixes, caps output, and enforces a
timeout. It is a policy layer, not an OS-level sandbox. Run untrusted code in an isolated
container or microVM in a production deployment.

## Engineering roadmap

- OCI/microVM execution backend and resource quotas
- Git patch ingestion and before/after regression comparison
- SWE-bench-compatible task adapters
- Persistent experiment metadata and result dashboards

## License

MIT
