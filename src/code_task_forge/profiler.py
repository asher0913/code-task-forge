from __future__ import annotations

from collections import Counter
from pathlib import Path

from .models import RepositoryProfile

LANGUAGES = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".cpp": "C++",
    ".cc": "C++",
}
MANIFESTS = {
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
}
IGNORED_PARTS = {".git", ".venv", "node_modules", "dist", "build", "__pycache__"}


class RepositoryProfiler:
    def __init__(self, max_files: int = 20_000) -> None:
        self.max_files = max_files

    def profile(self, root: Path) -> RepositoryProfile:
        resolved = root.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("repository root must be a directory")

        language_counts: Counter[str] = Counter()
        manifests: list[str] = []
        tests: list[str] = []
        total = 0

        for path in resolved.rglob("*"):
            relative = path.relative_to(resolved)
            if any(part in IGNORED_PARTS for part in relative.parts) or not path.is_file():
                continue
            total += 1
            if total > self.max_files:
                raise ValueError(f"repository exceeds {self.max_files} files")
            if path.name in MANIFESTS:
                manifests.append(relative.as_posix())
            language = LANGUAGES.get(path.suffix.lower())
            if language:
                language_counts[language] += 1
            lower = relative.as_posix().lower()
            is_test = (
                path.name.startswith("test_")
                or "/tests/" in f"/{lower}"
                or lower.endswith(".test.ts")
            )
            if is_test:
                tests.append(relative.as_posix())

        return RepositoryProfile(
            root=str(resolved),
            languages=dict(language_counts.most_common()),
            manifests=tuple(sorted(manifests)),
            test_files=tuple(sorted(tests)),
            source_files=sum(language_counts.values()),
            total_files=total,
        )
