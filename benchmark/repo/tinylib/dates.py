"""Calendar arithmetic."""

import datetime as dt


def add_months(day, months):
    """The same day of the month `months` later (or earlier), clamped to the end of shorter months."""
    total = day.month - 1 + months
    year, month = day.year + total // 12, total % 12 + 1
    return day.replace(year=year, month=month)


def is_weekend(day):
    return day.weekday() >= 5

