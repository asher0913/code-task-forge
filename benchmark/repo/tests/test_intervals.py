import pytest

from tinylib.intervals import merge


def test_empty():
    assert merge([]) == []


def test_disjoint_intervals_stay_separate():
    assert merge([(1, 2), (4, 5)]) == [(1, 2), (4, 5)]


def test_overlapping_intervals_merge():
    assert merge([(1, 3), (2, 6)]) == [(1, 6)]


def test_contained_interval_is_absorbed():
    assert merge([(1, 10), (2, 3)]) == [(1, 10)]


def test_touching_intervals_merge():
    assert merge([(1, 2), (2, 3)]) == [(1, 3)]


def test_unsorted_input():
    assert merge([(5, 6), (1, 3), (2, 4)]) == [(1, 4), (5, 6)]


def test_rejects_none():
    with pytest.raises(TypeError):
        merge(None)
