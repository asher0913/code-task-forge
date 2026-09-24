import datetime as dt

from tinylib.dates import add_months


def test_leap_february():
    assert add_months(dt.date(2024, 1, 31), 1) == dt.date(2024, 2, 29)


def test_thirty_day_month():
    assert add_months(dt.date(2023, 5, 31), 1) == dt.date(2023, 6, 30)


def test_backwards_into_february():
    assert add_months(dt.date(2024, 3, 31), -1) == dt.date(2024, 2, 29)


def test_leap_day_plus_a_year():
    assert add_months(dt.date(2024, 2, 29), 12) == dt.date(2025, 2, 28)
