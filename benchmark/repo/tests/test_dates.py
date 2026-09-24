import datetime as dt

import pytest

from tinylib.dates import add_months, is_weekend


def test_simple_month_step():
    assert add_months(dt.date(2024, 1, 15), 1) == dt.date(2024, 2, 15)


def test_crosses_year_end():
    assert add_months(dt.date(2023, 11, 10), 3) == dt.date(2024, 2, 10)


def test_negative_months():
    assert add_months(dt.date(2024, 3, 15), -2) == dt.date(2024, 1, 15)


def test_weekend():
    assert is_weekend(dt.date(2024, 6, 1)) and not is_weekend(dt.date(2024, 6, 3))


def test_month_end_is_clamped():
    assert add_months(dt.date(2023, 1, 31), 1) == dt.date(2023, 2, 28)


def test_rejects_strings():
    with pytest.raises(AttributeError):
        add_months("2024-01-01", 1)
