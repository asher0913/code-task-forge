from tinylib.intervals import merge


def test_nested_intervals():
    assert merge([(1, 10), (2, 3), (4, 5)]) == [(1, 10)]


def test_unsorted_touching_chain():
    assert merge([(3, 4), (1, 2), (2, 3)]) == [(1, 4)]


def test_point_interval():
    assert merge([(1, 1), (1, 2)]) == [(1, 2)]


def test_input_is_not_modified():
    data = [(5, 6), (1, 3)]
    merge(data)
    assert data == [(5, 6), (1, 3)]
