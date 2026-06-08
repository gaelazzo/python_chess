"""Opening-repertoire color auto-detection.

`detect_user_color_from_pgn` decides which side the user trains by counting the
PGN variations per side: more Black alternatives => the opponent is Black =>
the user plays White (and vice versa); a tie or no variation => None.
"""
from modes.openings import detect_user_color_from_pgn


def _write(tmp_path, pgn_body):
    p = tmp_path / "rep.pgn"
    p.write_text('[Event "x"]\n\n' + pgn_body + "\n", encoding="utf-8")
    return str(p)


def test_more_black_variations_means_user_plays_white(tmp_path):
    # "(2... ...)" are Black alternatives -> opponent is Black -> user = White
    path = _write(tmp_path, "1. e4 e5 2. Nf3 Nc6 (2... Nf6) (2... d6) *")
    assert detect_user_color_from_pgn(path) == "w"


def test_more_white_variations_means_user_plays_black(tmp_path):
    # "(3. ...)" are White alternatives -> opponent is White -> user = Black
    path = _write(tmp_path, "1. e4 e5 2. Nf3 Nc6 3. Bb5 (3. Bc4) (3. d4) *")
    assert detect_user_color_from_pgn(path) == "b"


def test_no_variations_returns_none(tmp_path):
    path = _write(tmp_path, "1. e4 e5 2. Nf3 *")
    assert detect_user_color_from_pgn(path) is None


def test_missing_file_returns_none():
    assert detect_user_color_from_pgn("does/not/exist.pgn") is None
