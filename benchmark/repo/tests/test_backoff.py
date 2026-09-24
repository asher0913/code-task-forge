import pytest

from tinylib.backoff import delays


def test_no_attempts():
    assert delays(0) == []


def test_doubling():
    assert delays(3) == pytest.approx([0.1, 0.2, 0.4])


def test_never_exceeds_cap():
    schedule = delays(8, cap=5.0)
    assert max(schedule) == 5.0
    assert schedule[-1] == 5.0
