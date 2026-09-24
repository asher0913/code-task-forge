import pytest

from tinylib.paginate import paginate

ITEMS = list(range(10))


def test_rejects_page_zero():
    with pytest.raises(ValueError):
        paginate(ITEMS, 0, 3)


def test_rejects_zero_page_size():
    with pytest.raises(ValueError):
        paginate(ITEMS, 1, 0)


def test_page_past_the_end_is_empty():
    assert paginate(ITEMS, 5, 3) == []


def test_first_page():
    assert paginate(ITEMS, 1, 3) == [0, 1, 2]


def test_last_partial_page():
    assert paginate(ITEMS, 4, 3) == [9]
