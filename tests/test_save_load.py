from datetime import datetime

import save_load


def test_header_includes_only_filled_fields():
    params = {"white": "Me", "black": "You", "event": "", "site": "Local", "result": ""}
    h = save_load.header_from_playparameters(params)
    # filled fields appear as key/value pairs, empty ones are skipped
    assert h[:6] == ["White", "Me", "Black", "You", "Site", "Local"]
    assert "Event" not in h
    assert "Result" not in h


def test_header_appends_date_and_round():
    h = save_load.header_from_playparameters({"white": "A"})
    assert "Round" in h and h[h.index("Round") + 1] == "*"
    assert "Date" in h
    assert h[h.index("Date") + 1] == datetime.today().strftime("%Y.%m.%d")
