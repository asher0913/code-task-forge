import pytest

from tinylib.text import slugify


def test_single_word():
    assert slugify("Hello") == "hello"


def test_space_becomes_dash():
    assert slugify("Hello World") == "hello-world"


def test_underscore_becomes_dash():
    assert slugify("snake_case") == "snake-case"


def test_runs_collapse_to_one_dash():
    assert slugify("a,  b") == "a-b"


def test_no_dashes_at_the_ends():
    assert slugify(" x ") == "x"


def test_rejects_none():
    with pytest.raises(AttributeError):
        slugify(None)
