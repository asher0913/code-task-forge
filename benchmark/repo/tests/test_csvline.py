import pytest

from tinylib.csvline import parse_line


def test_plain_fields():
    assert parse_line("a,b,c") == ["a", "b", "c"]


def test_empty_line_is_one_empty_field():
    assert parse_line("") == [""]


def test_empty_fields_are_kept():
    assert parse_line("a,,b") == ["a", "", "b"]


def test_spaces_are_preserved():
    assert parse_line(" a , b ") == [" a ", " b "]


def test_quoted_separator():
    assert parse_line('a,"b,c",d') == ["a", "b,c", "d"]


def test_doubled_quote_inside_quotes():
    assert parse_line('"say ""hi""",x') == ['say "hi"', "x"]


def test_rejects_none():
    with pytest.raises((TypeError, AttributeError)):
        parse_line(None)
