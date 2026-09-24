from tinylib.roman import to_int


def test_year():
    assert to_int("MCMXCIV") == 1994


def test_forty_two():
    assert to_int("XLII") == 42


def test_four_hundred_forty_four():
    assert to_int("CDXLIV") == 444


def test_nine():
    assert to_int("ix") == 9
