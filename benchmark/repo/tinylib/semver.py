"""Comparing dotted version strings."""


def _parts(version):
    return version.split(".")


def compare(a, b):
    """Return -1, 0 or 1. Components compare numerically; missing components count as 0."""
    pa, pb = _parts(a), _parts(b)
    n = max(len(pa), len(pb))
    pa = pa + ["0"] * (n - len(pa))
    pb = pb + ["0"] * (n - len(pb))
    for x, y in zip(pa, pb):
        if x != y:
            return -1 if x < y else 1
    return 0
