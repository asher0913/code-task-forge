import pytest

from tinylib.stats import median


def test_empty_raises():
    with pytest.raises(ValueError):
        median([])


def test_single_value():
    assert median([5]) == 5


def test_sorted_odd_length():
    assert median([1, 2, 3]) == 2


def test_unsorted_odd_length():
    assert median([3, 1, 2]) == 2


def test_even_length_is_mean_of_middle_pair():
    assert median([1, 2, 3, 4]) == 2.5
