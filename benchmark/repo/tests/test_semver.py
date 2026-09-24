import pytest

from tinylib.semver import compare


def test_equal():
    assert compare("1.2.3", "1.2.3") == 0


def test_patch_ordering():
    assert compare("1.2.3", "1.2.4") == -1


def test_missing_components_count_as_zero():
    assert compare("1.2", "1.2.0") == 0


def test_minor_compares_numerically():
    assert compare("1.10.0", "1.9.0") == 1


def test_major_compares_numerically():
    assert compare("10.0.0", "9.0.0") == 1


def test_none_is_rejected():
    with pytest.raises(AttributeError):
        compare(None, "1.0")
