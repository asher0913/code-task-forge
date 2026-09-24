import pytest

from tinylib.backoff import delays


def test_cap_below_base():
    assert delays(3, base=2.0, cap=1.0) == [1.0, 1.0, 1.0]


def test_constant_factor():
    assert delays(3, base=0.5, factor=1.0) == [0.5, 0.5, 0.5]


def test_length():
    assert len(delays(12)) == 12


def test_monotone_until_cap():
    schedule = delays(10, cap=3.0)
    assert schedule == sorted(schedule) and schedule[-1] == pytest.approx(3.0)
