from tinylib.text import slugify


def test_repeated_dashes():
    assert slugify("a--b") == "a-b"


def test_only_punctuation():
    assert slugify("---") == ""


def test_symbols_between_words():
    assert slugify("C++ & Rust") == "c-rust"


def test_digits_kept():
    assert slugify("Top 10 Tips!") == "top-10-tips"
