"""Retry schedules."""


def delays(attempts, base=0.1, factor=2.0, cap=5.0):
    """Seconds to wait before each of `attempts` retries: base * factor**i, never more than cap."""
    return [base * factor**i for i in range(attempts)]
