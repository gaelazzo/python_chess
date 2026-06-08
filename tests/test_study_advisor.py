"""Multi-nick matching for the Study Advisor.

A player whose games span sites (different lichess/chess.com handles, merged into
one PGN) can enter several nicks, comma/semicolon separated, and have games under
any of them counted. These cover the pure matching helpers headless.
"""
from modes.study_advisor import _parse_nicks, _user_color
from analyzer import _same_player


def test_parse_nicks_splits_on_comma_and_semicolon():
    assert _parse_nicks("alice, bob; carol") == ["alice", "bob", "carol"]


def test_parse_nicks_strips_spaces_and_drops_empties():
    assert _parse_nicks("  alice ,, ; bob ;") == ["alice", "bob"]
    assert _parse_nicks("") == []
    assert _parse_nicks(None) == []


def test_parse_nicks_keeps_original_case():
    # original case is kept (analyzePgn matches case-sensitively per nick)
    assert _parse_nicks("Gaelazzo, FAAILIX") == ["Gaelazzo", "FAAILIX"]


def test_user_color_matches_any_nick_case_insensitive():
    nicks = {n.lower() for n in _parse_nicks("Alice, Bob")}
    assert _user_color("alice", "someone", nicks) == "w"     # White matches
    assert _user_color("someone", "BOB", nicks) == "b"       # Black matches (case-insensitive)
    assert _user_color("ALICE", "bob", nicks) == "w"         # White wins when both match
    assert _user_color("x", "y", nicks) is None              # neither
    assert _user_color(None, None, nicks) is None            # missing headers


def test_same_player_is_case_insensitive():
    # the base build (analyzer.analyzePgn) matches the same way as the ranking
    assert _same_player("Gaelazzo", "gaelazzo")
    assert _same_player("FAAILIX", "faailix")
    assert not _same_player("alice", "bob")
    assert not _same_player(None, "bob")                     # missing header
