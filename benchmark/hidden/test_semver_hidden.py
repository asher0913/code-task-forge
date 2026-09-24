from tinylib.semver import compare


def test_patch_compares_numerically():
    assert compare("1.0.10", "1.0.9") == 1


def test_shorter_version_numeric():
    assert compare("1.2", "1.10") == -1


def test_leading_zeros_are_ignored():
    assert compare("01.2", "1.2") == 0


def test_symmetry():
    assert compare("1.9.0", "1.10.0") == -1
