from tinylib.paginate import paginate


def test_exact_last_page():
    assert paginate(list(range(9)), 3, 3) == [6, 7, 8]


def test_second_page():
    assert paginate(list(range(10)), 2, 5) == [5, 6, 7, 8, 9]


def test_empty_items():
    assert paginate([], 1, 3) == []


def test_page_size_larger_than_items():
    assert paginate([1, 2], 1, 10) == [1, 2]
