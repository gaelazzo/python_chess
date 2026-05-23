from modes.common import setAlfa


def test_set_alfa_appends_alpha_to_rgb():
    assert setAlfa((10, 20, 30), 150) == [10, 20, 30, 150]


def test_set_alfa_ignores_existing_alpha():
    # only the first three components are kept, then the new alpha
    assert setAlfa([1, 2, 3, 99], 5) == [1, 2, 3, 5]
