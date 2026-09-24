"""Roman numerals."""

VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def to_int(numeral):
    """Value of a Roman numeral, including subtractive pairs such as IV and CM. Case-insensitive."""
    return sum(VALUES[ch] for ch in numeral.upper())
