# CodeTaskForge

[![CI](https://github.com/asher0913/code-task-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/asher0913/code-task-forge/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Dependencies](https://img.shields.io/badge/runtime%20dependency-pytest-brightgreen)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

"The agent ran the tests and they passed" is weak evidence that a coding agent fixed an issue.
The agent can edit the tests, special-case the inputs the tests use, or write a fix that is
general but wrong. CodeTaskForge is the execution and judging layer for coding-agent patches:

- it applies a candidate patch in a throwaway workspace behind a path policy;
- it runs tests with no shell, a scrubbed environment and a process-group timeout;
- it judges the result three ways, of increasing strength;
- it classifies every rejection.

Each judge is measured on 98 candidate patches whose correctness is known.

```text
$ code-task-forge evaluate --task dates --judge "fail-to-pass + pass-to-pass" \
      --patch benchmark/candidates/dates/plausible_wrong.diff
{ "accepted": true, "failure": "none", ... }                 # clamps every month to 28 days

$ code-task-forge evaluate --task dates --patch benchmark/candidates/dates/plausible_wrong.diff
{ "accepted": false, "failure": "hidden_tests",
  "tests": { ..., "tests/test_dates_hidden.py::test_thirty_day_month": "failed",
                  "tests/test_dates_hidden.py::test_leap_february": "failed", ... } }
```

## Quick start

```bash
git clone https://github.com/asher0913/code-task-forge && cd code-task-forge
./scripts/demo.sh
```

This needs Python 3.10+ and git. It takes about 25 seconds on a laptop and does not need Docker or a
GPU. The script:

1. creates `.venv`;
2. judges the plausible-but-wrong `dates` patch twice: the SWE-bench judge accepts it, and the
   held-out tests reject it;
3. reruns all 98 candidates under all 3 judges;
4. checks every verdict against [`results/benchmark.json`](results/benchmark.json).

Outputs and the log go to `runs/demo/`. The `quickstart` CI job runs the same script on a clean
Ubuntu runner.

## Results

10 tasks, each a reported bug in a small library (`benchmark/repo/tinylib`) with an issue text,
visible tests and four hidden tests. Each task has a gold fix, an independently written
alternative fix, and up to ten kinds of wrong patch, 98 candidates in all.

| Judge | Accepted | False accepts | False rejects | Accepted patches that are correct |
|---|---:|---:|---:|---:|
| exit code of the task's test file | 45 | **25** | 0 | 44% |
| fail-to-pass + pass-to-pass, tests restored (SWE-bench) | 35 | **15** | 0 | 57% |
| + four hidden tests per task | 20 | **0** | 0 | 100% |

What each judge lets through (accepted / candidates):

| Candidate kind | What it does | Exit code | F2P + P2P | + hidden |
|---|---|---:|---:|---:|
| gold, alternative fix | fix the issue | 20/20 | 20/20 | 20/20 |
| test tampering | marks the failing tests `skip` | **10/10** | 0/10 | 0/10 |
| overfit | special-cases the visible test inputs | **10/10** | **10/10** | 0/10 |
| plausible but wrong | general fix that is wrong beyond the tests (clamp to day 28, sort in place) | **5/5** | **5/5** | 0/5 |
| partial | fixes one symptom of the issue | 0/4 | 0/4 | 0/4 |
| regression | fixes the issue, breaks a passing test | 0/6 | 0/6 | 0/6 |
| syntax error, missing import, infinite loop | do not build, import or terminate | 0/23 | 0/23 | 0/23 |
| stale context, path escape | do not apply, or write outside the workspace | 0/20 | 0/20 | 0/20 |

- **Exit codes reward editing the tests.** Every patch that skips the failing tests passes. The
  SWE-bench protocol stops this by restoring the original test files after applying the patch;
  the harness also flags any patch that touches `tests/`.
- **Visible tests cannot tell a fix from a fit.** Hard-coded answers and plausible-but-wrong
  fixes pass fail-to-pass and pass-to-pass alike: 15 of the 35 patches the SWE-bench judge
  accepts are wrong. Only tests the agent never saw separate them.
- **A few held-out tests go a long way.** The 15 fitted patches fail 1 to 4 of their task's 4
  hidden tests. Running only k randomly chosen hidden tests would catch:

  | Hidden tests run per task | 1 | 2 | 3 | 4 |
  |---|---:|---:|---:|---:|
  | fitted patches caught | 72% | 91% | 98% | 100% |

- **Cheap checks first.** 20 of the 98 candidates are rejected by the path policy or by
  `git apply --check` without running any test code. Every rejection is classified into one of
  eight failure kinds, and all 98 match the kind the candidate was built to exhibit.

These numbers are by construction: the candidates were written to fall into known kinds, and
the hidden tests were written knowing what the fits would miss. What the benchmark shows is
which layer catches which failure, not how often a real agent produces each one.

## How a patch is judged

```text
patch ──► path policy ──► git apply --check ──► throwaway copy of the repo
          (no .., no absolute paths,             │
           no .git/ or .github/)                 ▼
                                    exit code:  run the task's test file as patched
                                    F2P + P2P:  restore tests/, run fail-to-pass and pass-to-pass ids
                                    + hidden:   also copy in the held-out tests
                                                 │
                         pytest via SandboxedRunner: allowlisted argv (no shell), scrubbed env,
                         own process group killed on timeout, JUnit XML parsed per test id
                                                 ▼
          none · policy · patch_does_not_apply · timeout · build · dependency ·
          tests_failed · fail_to_pass · regression · hidden_tests
```

The fail-to-pass and pass-to-pass lists are derived the way SWE-bench derives them: by running
the visible tests before and after the gold patch (`benchmark/build_candidates.py`, which also
checks that the gold patch passes every hidden test). The HTTP API lists visible tests only and
reports hidden results as a count, so an agent calling it cannot learn the hidden test names.

## Evidence and CI coverage

| Claim | Data | Evidence | Rerun in CI? |
|---|---|---|---|
| Judge table and per-kind table | 98 hand-built candidate patches with known labels (synthetic by construction) | `results/benchmark.json` | Yes: every verdict is regenerated and compared |
| Hidden-test sampling (72% / 91% / 98% / 100%) | same | computed in `benchmark.py` from the same verdicts | Yes, as part of the same file |
| Runner isolation (no shell, scrubbed environment, process-group kill) | unit tests | `tests/test_code_task_forge.py` | Yes, on Python 3.10 and 3.12 |
| The API never names a hidden test | unit test | `test_api_hides_hidden_tests` | Yes |

## Design trade-offs

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Test restoration | delete `tests/` and copy the originals back after applying the patch | diff-check the patch for test edits | Restoring makes tampering irrelevant rather than something to detect, which is what SWE-bench does. Test edits are still flagged for the report. |
| Command execution | argv allowlist, no shell, scrubbed environment, own process group | `subprocess.run(shell=True)` | A candidate cannot chain commands or read the caller's secrets, and a fork bomb or hung child dies with its group. |
| Isolation | policy layer inside the harness; containers are left to the deployment | a microVM per run | This keeps the harness light (pytest is its only runtime dependency) and fast: 98 × 3 runs take about 15 s. The price is spelled out under Known issues. |
| Verdict source | JUnit XML parsed per test id | exit codes | Exit codes cannot tell fail-to-pass from pass-to-pass; per-test outcomes can. |

## Code map

| File | What to look at |
|---|---|
| `src/code_task_forge/harness.py` | `Harness.evaluate`: patch policy → apply → restore tests → run the right test ids → classify the failure |
| `src/code_task_forge/runner.py` | `SandboxedRunner.run` (allowlist, scrubbed environment, process-group timeout) and `junit_outcomes` |
| `src/code_task_forge/patch.py` | `touched_paths`, `check_policy` (no `..`, absolute paths, `.git/`, `.github/`), `apply` via `git apply --check` |
| `src/code_task_forge/benchmark.py` | runs every candidate under every judge and computes the tables above |
| `benchmark/build_candidates.py` | how the tasks, fail-to-pass and pass-to-pass lists and candidates are generated |
| `src/code_task_forge/api.py` | FastAPI app that hides hidden-test names |

## Usage

```bash
pip install -e '.[dev]'

code-task-forge tasks                                        # issue text of each task
code-task-forge evaluate --task roman --patch my_fix.diff    # judge one patch (default: + hidden tests)
code-task-forge benchmark --out results/benchmark.json      # 98 candidates x 3 judges, about 15 s
code-task-forge profile path/to/repo                         # languages, manifests, test files
python benchmark/build_candidates.py                         # regenerate tasks.json and the candidates

pip install -e '.[api]'
uvicorn code_task_forge.api:create_app --factory             # GET /v1/tasks, POST /v1/evaluate
docker build -t code-task-forge . && docker run --network none --read-only --tmpfs /tmp -p 8000:8000 code-task-forge
```

## Tests

`pytest -q` runs 21 tests:

- the runner refuses shells and non-test commands, hides the caller's environment, and kills
  the whole process group on timeout;
- the path policy works, and stale patches do not apply;
- tasks follow the SWE-bench split;
- gold and alternative fixes pass every judge;
- tampering fools only the exit code, and fitting fools everything but the hidden tests;
- each failure kind is classified correctly;
- the committed headline numbers hold;
- the CLI works, and the API never names a hidden test.

## Limitations

- Ten small single-function tasks in one library. Real issues span files, need environment setup
  and have flaky tests, which this harness does not yet retry or quarantine.
- The runner is a policy layer, not an OS sandbox. Candidate code runs as the calling user; in
  production run it in a container or microVM with no network, as the Dockerfile suggests.
- Tamper detection covers edits to `tests/`. A patch could still change behaviour through
  `conftest.py` or `pytest.ini` elsewhere in the tree.

## Known issues

- **The hidden tests are public.** `benchmark/hidden/` is committed to this repository, so they are
  hidden only from an agent that is not given this repository. A real evaluation should keep them in
  a separate store that only the harness can read.
- **No OS-level isolation.** Candidate code runs as the calling user with that user's filesystem
  access. The allowlist and scrubbed environment limit what the harness itself starts, not what the
  code under test does. Run it inside the provided Docker image with `--network none --read-only`, or
  in a microVM.

## License

MIT
