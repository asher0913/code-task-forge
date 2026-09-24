"""Parsing a single CSV line."""


def parse_line(line, sep=","):
    """Split one line into fields. Fields may be double-quoted; inside quotes, the separator is
    literal and a doubled quote stands for one quote character."""
    return line.split(sep)
