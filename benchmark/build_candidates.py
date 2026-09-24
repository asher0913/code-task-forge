"""Regenerate tasks.json and the candidate patches from the specs below.

Each task is one reported bug in ``repo/tinylib``. For every task this script
writes the gold patch and a pool of candidate patches of known kinds, the way
a coding agent's attempts go wrong in practice: hard-coding the visible test
inputs, a general but wrong fix, fixing half the issue, breaking something
that worked, editing the tests instead of the code, and patches that do not
build, import, terminate, apply or stay inside the workspace.

The fail-to-pass and pass-to-pass test lists are derived, as in SWE-bench, by
running the visible tests before and after the gold patch. The script also
checks that the gold patch passes every hidden test.

    python benchmark/build_candidates.py
"""

from __future__ import annotations

import difflib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from code_task_forge.patch import apply
from code_task_forge.runner import SandboxedRunner, junit_outcomes

HERE = Path(__file__).resolve().parent
REPO, HIDDEN, OUT = HERE / "repo", HERE / "hidden", HERE / "candidates"

CSV_GOLD = """    fields, current, quoted, i = [], [], False, 0
    while i < len(line):
        ch = line[i]
        if quoted:
            if ch == '"' and line[i + 1 : i + 2] == '"':
                current.append('"')
                i += 1
            elif ch == '"':
                quoted = False
            else:
                current.append(ch)
        elif ch == '"':
            quoted = True
        elif ch == sep:
            fields.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    fields.append("".join(current))
    return fields"""

SPECS = {
    "intervals": {
        "issue": "merge() keeps touching intervals such as (1, 2) and (2, 3) apart, "
        "and returns wrong results when the input is not sorted.",
        "gold": [
            (
                "    for start, end in intervals:\n        if result and start < result[-1][1]:",
                "    for start, end in sorted(intervals):\n        if result and start <= result[-1][1]:",
            )
        ],
        "alt_correct": [
            (
                """    result = []
    for start, end in intervals:
        if result and start < result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result""",
                """    merged = []
    for start, end in sorted(intervals):
        if merged and merged[-1][1] >= start:
            last_start, last_end = merged.pop()
            merged.append((last_start, max(last_end, end)))
        else:
            merged.append((start, end))
    return merged""",
            )
        ],
        "overfit": [
            (
                "    result = []\n",
                "    if intervals == [(1, 2), (2, 3)]:\n        return [(1, 3)]\n"
                "    if intervals == [(5, 6), (1, 3), (2, 4)]:\n        return [(1, 4), (5, 6)]\n    result = []\n",
            )
        ],
        "partial": [("start < result[-1][1]", "start <= result[-1][1]")],
        "regression": "gold+",
        "regression_extra": [("max(result[-1][1], end)", "end")],
    },
    "semver": {
        "issue": "compare('1.10.0', '1.9.0') returns -1: version components are compared as strings.",
        "gold": [
            ('    return version.split(".")', '    return [int(p) for p in version.split(".")]'),
            ('["0"] * (n - len(pa))', "[0] * (n - len(pa))"),
            ('["0"] * (n - len(pb))', "[0] * (n - len(pb))"),
        ],
        "alt_correct": [
            ('    return version.split(".")', '    return [int(p) for p in version.split(".")]'),
            (
                """    pa, pb = _parts(a), _parts(b)
    n = max(len(pa), len(pb))
    pa = pa + ["0"] * (n - len(pa))
    pb = pb + ["0"] * (n - len(pb))
    for x, y in zip(pa, pb):""",
                """    from itertools import zip_longest

    for x, y in zip_longest(_parts(a), _parts(b), fillvalue=0):""",
            ),
        ],
        "overfit": [
            (
                "    pa, pb = _parts(a), _parts(b)\n",
                '    if (a, b) in {("1.10.0", "1.9.0"), ("10.0.0", "9.0.0")}:\n        return 1\n'
                "    pa, pb = _parts(a), _parts(b)\n",
            )
        ],
        "plausible_wrong": [
            (
                "        if x != y:\n            return -1 if x < y else 1",
                "        if len(x) != len(y):\n            return -1 if len(x) < len(y) else 1\n"
                "        if x != y:\n            return -1 if x < y else 1",
            )
        ],
        "regression": [('    return version.split(".")', '    return [int(p) for p in version.split(".")]')],
    },
    "lru": {
        "issue": "LRUCache evicts entries that were just used. Reads and writes should both count as a use.",
        "gold": [
            (
                "            return default\n        return self._data[key]",
                "            return default\n        self._data.move_to_end(key)\n        return self._data[key]",
            ),
            (
                "        self._data[key] = value\n",
                "        self._data[key] = value\n        self._data.move_to_end(key)\n",
            ),
        ],
        "alt_correct": [
            (
                "        self._data[key] = value\n",
                "        self._data.pop(key, None)\n        self._data[key] = value\n",
            ),
            (
                "            return default\n        return self._data[key]",
                "            return default\n        value = self._data.pop(key)\n"
                "        self._data[key] = value\n        return value",
            ),
        ],
        "overfit": [
            (
                "            return default\n        return self._data[key]",
                '            return default\n        if key == "a":\n            self._data.move_to_end(key)\n'
                "        return self._data[key]",
            )
        ],
        "plausible_wrong": [
            (
                "            return default\n        return self._data[key]",
                "            return default\n        self._data.move_to_end(key)\n        return self._data[key]",
            )
        ],
    },
    "text": {
        "issue": "slugify('a,  b') gives 'a---b' and slugify(' x ') gives '-x-'.",
        "gold": [('return re.sub(r"[^a-z0-9]", "-", text)', 'return re.sub(r"[^a-z0-9]+", "-", text).strip("-")')],
        "alt_correct": [
            (
                '    text = text.lower()\n    return re.sub(r"[^a-z0-9]", "-", text)',
                '    return "-".join(re.findall(r"[a-z0-9]+", text.lower()))',
            )
        ],
        "overfit": [
            (
                "    text = text.lower()\n",
                '    special = {"a,  b": "a-b", " x ": "x"}\n    if text in special:\n'
                "        return special[text]\n    text = text.lower()\n",
            )
        ],
        "partial": [('r"[^a-z0-9]"', 'r"[^a-z0-9]+"')],
        "regression": [('return re.sub(r"[^a-z0-9]", "-", text)', 'return re.sub(r"\\W+", "-", text).strip("-")')],
    },
    "stats": {
        "issue": "median() is wrong for unsorted input and for an even number of values.",
        "gold": [
            (
                "    n = len(values)\n    return values[n // 2]",
                "    ordered = sorted(values)\n    n = len(ordered)\n    mid = n // 2\n    if n % 2:\n"
                "        return ordered[mid]\n    return (ordered[mid - 1] + ordered[mid]) / 2",
            )
        ],
        "alt_correct": [
            ('"""Descriptive statistics."""\n', '"""Descriptive statistics."""\n\nimport statistics\n'),
            ("    n = len(values)\n    return values[n // 2]", "    return statistics.median(values)"),
        ],
        "overfit": [
            (
                "    n = len(values)\n",
                "    special = {(3, 1, 2): 2, (1, 2, 3, 4): 2.5}\n    if tuple(values) in special:\n"
                "        return special[tuple(values)]\n    n = len(values)\n",
            )
        ],
        "plausible_wrong": [
            (
                "    n = len(values)\n    return values[n // 2]",
                "    values.sort()\n    n = len(values)\n    mid = n // 2\n    if n % 2:\n"
                "        return values[mid]\n    return (values[mid - 1] + values[mid]) / 2",
            )
        ],
        "partial": [
            (
                "    n = len(values)\n    return values[n // 2]",
                "    ordered = sorted(values)\n    return ordered[len(ordered) // 2]",
            )
        ],
        "infinite_loop": "median",
    },
    "csvline": {
        "issue": "parse_line splits inside quoted fields: 'a,\"b,c\",d' gives four fields.",
        "gold": [("    return line.split(sep)", CSV_GOLD)],
        "alt_correct": [
            ('"""Parsing a single CSV line."""\n', '"""Parsing a single CSV line."""\n\nimport csv\n'),
            (
                "    return line.split(sep)",
                '    if not isinstance(line, str):\n        raise TypeError("line must be a string")\n'
                '    return next(csv.reader([line], delimiter=sep)) or [""]',
            ),
        ],
        "overfit": [
            (
                "    return line.split(sep)",
                '    special = {\'a,"b,c",d\': ["a", "b,c", "d"], \'"say ""hi""",x\': [\'say "hi"\', "x"]}\n'
                "    if line in special:\n        return special[line]\n    return line.split(sep)",
            )
        ],
        "partial": [
            (
                "    return line.split(sep)",
                CSV_GOLD.replace(
                    """            if ch == '"' and line[i + 1 : i + 2] == '"':
                current.append('"')
                i += 1
            elif ch == '"':""",
                    """            if ch == '"':""",
                ),
            )
        ],
        "regression": [
            ("    return line.split(sep)", CSV_GOLD.replace('"".join(current)', '"".join(current).strip()'))
        ],
    },
    "dates": {
        "issue": "add_months(date(2023, 1, 31), 1) raises ValueError instead of returning 2023-02-28.",
        "gold": [
            ("import datetime as dt\n", "import calendar\nimport datetime as dt\n"),
            (
                "    return day.replace(year=year, month=month)\n",
                "    last = calendar.monthrange(year, month)[1]\n"
                "    return day.replace(year=year, month=month, day=min(day.day, last))\n",
            ),
        ],
        "alt_correct": [
            (
                "    return day.replace(year=year, month=month)\n",
                "    d = day.day\n    while True:\n        try:\n"
                "            return day.replace(year=year, month=month, day=d)\n"
                "        except ValueError:\n            d -= 1\n",
            )
        ],
        "overfit": [
            (
                "    total = day.month - 1 + months\n",
                "    if day == dt.date(2023, 1, 31) and months == 1:\n        return dt.date(2023, 2, 28)\n"
                "    total = day.month - 1 + months\n",
            )
        ],
        "plausible_wrong": [
            (
                "    return day.replace(year=year, month=month)\n",
                "    return day.replace(year=year, month=month, day=min(day.day, 28))\n",
            )
        ],
    },
    "roman": {
        "issue": "to_int('IV') returns 6: subtractive notation is not handled.",
        "gold": [
            (
                "    return sum(VALUES[ch] for ch in numeral.upper())",
                "    digits = [VALUES[ch] for ch in numeral.upper()]\n    total = 0\n"
                "    for i, value in enumerate(digits):\n        if i + 1 < len(digits) and value < digits[i + 1]:\n"
                "            total -= value\n        else:\n            total += value\n    return total",
            )
        ],
        "alt_correct": [
            (
                "    return sum(VALUES[ch] for ch in numeral.upper())",
                "    total, prev = 0, 0\n    for ch in reversed(numeral.upper()):\n        value = VALUES[ch]\n"
                "        total += -value if value < prev else value\n        prev = value\n    return total",
            )
        ],
        "overfit": [
            (
                "    return sum(VALUES[ch] for ch in numeral.upper())",
                '    special = {"IV": 4, "XC": 90}\n    if numeral in special:\n        return special[numeral]\n'
                "    return sum(VALUES[ch] for ch in numeral.upper())",
            )
        ],
        "plausible_wrong": [
            (
                "    return sum(VALUES[ch] for ch in numeral.upper())",
                '    numeral = numeral.upper().replace("IV", "IIII").replace("XC", "LXXXX")\n'
                "    return sum(VALUES[ch] for ch in numeral)",
            )
        ],
        "infinite_loop": "to_int",
    },
    "paginate": {
        "issue": "paginate(items, 1, 3) skips the first page; pages are 1-based.",
        "gold": [("    start = page * per_page", "    start = (page - 1) * per_page")],
        "alt_correct": [
            (
                "    start = page * per_page\n    return items[start : start + per_page]",
                "    end = page * per_page\n    return items[end - per_page : end]",
            ),
        ],  # fmt: skip
        "overfit": [
            (
                "    start = page * per_page\n",
                "    if (page, per_page) == (1, 3):\n        return items[:3]\n"
                "    if (page, per_page) == (4, 3):\n        return items[9:]\n    start = page * per_page\n",
            )
        ],
        "regression": [
            ('    if page < 1 or per_page < 1:\n        raise ValueError("page and per_page must be positive")\n', ""),
            ("    start = page * per_page", "    start = (page - 1) * per_page"),
        ],
        "infinite_loop": "paginate",
    },
    "backoff": {
        "issue": "delays() grows past the cap: delays(8)[-1] is 12.8 seconds.",
        "gold": [
            (
                "    return [base * factor**i for i in range(attempts)]",
                "    return [min(cap, base * factor**i) for i in range(attempts)]",
            )
        ],
        "alt_correct": [
            (
                "    return [base * factor**i for i in range(attempts)]",
                "    schedule, delay = [], base\n    for _ in range(attempts):\n"
                "        schedule.append(min(cap, delay))\n        delay *= factor\n    return schedule",
            )
        ],
        "overfit": [
            (
                "    return [base * factor**i for i in range(attempts)]",
                "    if attempts == 8 and cap == 5.0:\n        return [0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 5.0, 5.0]\n"
                "    return [base * factor**i for i in range(attempts)]",
            )
        ],
        "regression": [
            (
                "    return [base * factor**i for i in range(attempts)]",
                "    return [min(cap, base * factor**i) for i in range(1, attempts + 1)]",
            )
        ],
    },
}

EXPECTED = {  # kind -> (correct, what the strongest judge should report)
    "gold": (True, "none"),
    "alt_correct": (True, "none"),
    "overfit": (False, "hidden_tests"),
    "plausible_wrong": (False, "hidden_tests"),
    "partial": (False, "fail_to_pass"),
    "regression": (False, "regression"),
    "test_tampering": (False, "fail_to_pass"),
    "syntax_error": (False, "build"),
    "missing_import": (False, "dependency"),
    "infinite_loop": (False, "timeout"),
    "stale_context": (False, "patch_does_not_apply"),
    "path_escape": (False, "policy"),
}


def edit(text: str, replacements) -> str:
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError(f"expected exactly one occurrence of {old!r}")
        text = text.replace(old, new)
    return text


def diff(path: str, before: str, after: str) -> str:
    lines = difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True), f"a/{path}", f"b/{path}"
    )
    return "".join(lines)


def run_tests(patch: str | None, ids: list[str], hidden: list[str] = ()) -> dict[str, str]:
    runner = SandboxedRunner(timeout_seconds=30)
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "workspace"
        shutil.copytree(REPO, ws)
        if patch:
            assert apply(ws, patch)[0]
        for name in hidden:
            shutil.copy(HIDDEN / name, ws / "tests" / name)
        report = Path(tmp) / "report.xml"
        runner.run(ws, (sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}", *ids))
        return junit_outcomes(report)


def candidates_for(task: str, spec: dict) -> dict[str, str]:
    path = f"tinylib/{task}.py"
    source = (REPO / path).read_text()
    gold = edit(source, spec["gold"])
    out = {"gold": diff(path, source, gold)}
    for kind in ("alt_correct", "overfit", "plausible_wrong", "partial"):
        if kind in spec:
            out[kind] = diff(path, source, edit(source, spec[kind]))
    if "regression" in spec:
        reps = spec["gold"] + spec["regression_extra"] if spec["regression"] == "gold+" else spec["regression"]
        out["regression"] = diff(path, source, edit(source, reps))

    test_path = f"tests/test_{task}.py"
    tests = (REPO / test_path).read_text()
    tampered = tests
    for test_id in spec["fail_to_pass"]:
        name = test_id.split("::")[1]
        tampered = edit(tampered, [(f"def {name}(", f'@pytest.mark.skip(reason="flaky on CI")\ndef {name}(')])
    out["test_tampering"] = diff(test_path, tests, tampered)

    added = next(line for line in gold.splitlines() if line.strip() and line not in source.splitlines())
    out["syntax_error"] = diff(path, source, gold.replace(added, added + " (", 1))
    first_line_end = gold.index("\n") + 1
    out["missing_import"] = diff(
        path, source, gold[:first_line_end] + "\nfrom tinylib._compat import ensure_sequence\n" + gold[first_line_end:]
    )
    if "infinite_loop" in spec:
        lines = gold.splitlines(keepends=True)
        k = next(i for i, line in enumerate(lines) if line.startswith(f"def {spec['infinite_loop']}("))
        lines.insert(k + 2, "    while True:\n        pass\n")  # after the def line and its docstring
        out["infinite_loop"] = diff(path, source, "".join(lines))
    stale = out["gold"].splitlines(keepends=True)
    k = next(i for i, line in enumerate(stale) if line.startswith(" ") and line.strip())
    stale[k] = stale[k].rstrip("\n") + "  # edited upstream\n"
    out["stale_context"] = "".join(stale)
    out["path_escape"] = "--- /dev/null\n+++ b/../outside/notes.txt\n@@ -0,0 +1 @@\n+written outside the workspace\n"
    return out


def main() -> None:
    tasks, manifest = [], []
    shutil.rmtree(OUT, ignore_errors=True)
    for task, spec in SPECS.items():
        test_file = f"tests/test_{task}.py"
        hidden_file = f"test_{task}_hidden.py"
        path = f"tinylib/{task}.py"
        source = (REPO / path).read_text()
        gold_patch = diff(path, source, edit(source, spec["gold"]))
        before = run_tests(None, [test_file])
        after = run_tests(gold_patch, [test_file, f"tests/{hidden_file}"], [hidden_file])
        f2p = sorted(t for t, o in before.items() if o != "passed" and after.get(t) == "passed")
        p2p = sorted(t for t, o in before.items() if o == "passed" and after.get(t) == "passed")
        hidden = sorted(t for t in after if t.startswith(f"tests/{hidden_file}"))
        assert f2p and all(after[t] == "passed" for t in hidden), task
        assert len(f2p) + len(p2p) == len(before), f"{task}: gold patch breaks a passing test"
        spec["fail_to_pass"] = f2p
        tasks.append(
            {"id": task, "file": path, "test_file": test_file, "issue": spec["issue"], "fail_to_pass": f2p,
             "pass_to_pass": p2p, "hidden": hidden}
        )  # fmt: skip
        for kind, patch in candidates_for(task, spec).items():
            target = OUT / task / f"{kind}.diff"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(patch)
            correct, expected = EXPECTED[kind]
            manifest.append(
                {"task": task, "kind": kind, "patch": f"candidates/{task}/{kind}.diff", "correct": correct,
                 "expected_failure": expected}
            )  # fmt: skip
    (HERE / "tasks.json").write_text(json.dumps(tasks, indent=2) + "\n")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{len(tasks)} tasks, {len(manifest)} candidate patches")


if __name__ == "__main__":
    main()
