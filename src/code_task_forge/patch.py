"""Checking and applying a candidate patch (unified diff) inside a throwaway workspace."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath

_HEADER = re.compile(r"^(?:---|\+\+\+) (\S+)", re.MULTILINE)
PROTECTED_PREFIXES = (".git/", ".github/")


class PatchPolicyError(ValueError):
    """The patch touches a path it must not touch."""


def touched_paths(patch: str) -> list[str]:
    """Workspace-relative paths named in the diff headers (``a/``/``b/`` prefixes removed)."""
    paths = []
    for raw in _HEADER.findall(patch):
        if raw == "/dev/null":
            continue
        path = raw[2:] if raw[:2] in ("a/", "b/") else raw
        if path not in paths:
            paths.append(path)
    return paths


def check_policy(paths: list[str]) -> None:
    if not paths:
        raise PatchPolicyError("patch names no files")
    for path in paths:
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or path.startswith(PROTECTED_PREFIXES):
            raise PatchPolicyError(f"patch touches a path outside the workspace or protected: {path}")


def apply(workspace: Path, patch: str) -> tuple[bool, str]:
    """Apply with ``git apply`` (works outside a repository). Returns (applied, message)."""
    check_policy(touched_paths(patch))
    patch_file = workspace.parent / "candidate.diff"
    patch_file.write_text(patch)
    for args in (["--check"], []):
        done = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", *args, str(patch_file)],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if done.returncode != 0:
            return False, done.stderr.strip()
    return True, ""
