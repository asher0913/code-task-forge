from tinylib.stats import median


def test_unsorted_even_length():
    assert median([4, 1, 3, 2]) == 2.5


def test_negative_values():
    assert median([-5, -1, -3]) == -3


def test_input_is_not_modified():
    data = [3, 1, 2]
    median(data)
    assert data == [3, 1, 2]


def test_tuple_input():
    assert median((9, 7, 8)) == 8
