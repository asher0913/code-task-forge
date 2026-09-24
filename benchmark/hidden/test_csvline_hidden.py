from tinylib.csvline import parse_line


def test_custom_separator_with_quotes():
    assert parse_line('"a;b";c', sep=";") == ["a;b", "c"]


def test_quoted_empty_field():
    assert parse_line('"",x') == ["", "x"]


def test_trailing_separator():
    assert parse_line("a,") == ["a", ""]


def test_only_doubled_quotes():
    assert parse_line('""""') == ['"']
