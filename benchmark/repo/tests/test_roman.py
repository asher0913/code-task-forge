import pytest

from tinylib.roman import to_int


def test_additive():
    assert to_int("VIII") == 8


def test_repeated():
    assert to_int("III") == 3


def test_lowercase():
    assert to_int("xii") == 12


def test_subtractive_four():
    assert to_int("IV") == 4


def test_subtractive_ninety():
    assert to_int("XC") == 90


def test_unknown_symbol():
    with pytest.raises(KeyError):
        to_int("ABC")
