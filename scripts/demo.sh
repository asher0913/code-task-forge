#!/usr/bin/env bash
# One-command quick start from a clean checkout. Needs python3 >= 3.10 and git; no network
# beyond the pip install, no GPU.
#
# Creates .venv, judges one plausible-but-wrong patch under the SWE-bench judge and under the
# hidden-test judge, reruns all 98 candidates x 3 judges, and checks every verdict against
# results/benchmark.json. Outputs and this log are written to runs/demo/.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=runs/demo
mkdir -p "$OUT"
exec > >(tee "$OUT/demo.log") 2>&1

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e .
echo "commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
python -c "import platform, sys; print('python:', sys.version.split()[0], 'on', platform.platform())"
echo "git: $(git --version)"

PATCH=benchmark/candidates/dates/plausible_wrong.diff
echo; echo "== $PATCH (clamps every month to 28 days) under the SWE-bench judge"
code-task-forge evaluate --task dates --judge "fail-to-pass + pass-to-pass" --patch "$PATCH" | tee "$OUT/swebench_verdict.json"
echo; echo "== the same patch with the four hidden tests"
code-task-forge evaluate --task dates --patch "$PATCH" | tee "$OUT/hidden_verdict.json"

echo; echo "== 98 candidates x 3 judges"
code-task-forge benchmark --out "$OUT/benchmark.json"

echo; echo "== fresh verdicts vs committed results/benchmark.json"
python scripts/compare_results.py "$OUT/benchmark.json" results/benchmark.json
echo; echo "Done. Outputs are in $OUT/."
