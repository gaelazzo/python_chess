"""Multi-nick matching for the Study Advisor.

A player whose games span sites (different lichess/chess.com handles, merged into
one PGN) can enter several nicks, comma/semicolon separated, and have games under
any of them counted. These cover the pure matching helpers headless.
"""
from datetime import date
from dataclasses import asdict

from modes.study_advisor import _parse_nicks, _user_color
from analyzer import _same_player
from LearningBase import LearningBase, LearningBaseData


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


# --- Re-run dedup: per-nick analyzed date window (Study Advisor) -------------

def _base():
    lb = LearningBase(16, 80, 0.5, True)
    lb.setFileName("x_C01")
    return lb


def test_analyzed_range_extends_and_is_inclusive_case_insensitive():
    lb = _base()
    lb.extendAnalyzedRange("Gaelazzo", date(2024, 5, 10))
    lb.extendAnalyzedRange("gaelazzo", date(2024, 1, 2))   # same nick, lower
    lb.extendAnalyzedRange("gaelazzo", date(2024, 9, 1))   # same nick, upper
    assert lb.analyzedRanges == {"gaelazzo": [date(2024, 1, 2), date(2024, 9, 1)]}
    # inclusive on both ends, nick match is case-insensitive
    assert lb.isInAnalyzedRange("GAELAZZO", date(2024, 5, 10)) is True
    assert lb.isInAnalyzedRange("gaelazzo", date(2024, 1, 2)) is True   # lower bound
    assert lb.isInAnalyzedRange("gaelazzo", date(2024, 9, 1)) is True   # upper bound
    # outside the window -> re-analyzed
    assert lb.isInAnalyzedRange("gaelazzo", date(2025, 1, 1)) is False  # newer
    assert lb.isInAnalyzedRange("gaelazzo", date(2023, 1, 1)) is False  # older history
    assert lb.isInAnalyzedRange("other", date(2024, 5, 10)) is False    # unknown nick


def test_analyzed_range_survives_serialization_roundtrip():
    lb = _base()
    lb.extendAnalyzedRange("gaelazzo", date(2024, 1, 2))
    lb.extendAnalyzedRange("gaelazzo", date(2024, 9, 1))
    data = asdict(lb._to_dict())
    assert data["analyzedRanges"] == {"gaelazzo": ["2024-01-02", "2024-09-01"]}
    lb2 = LearningBase._from_dict(LearningBaseData(**data))
    assert lb2.analyzedRanges == lb.analyzedRanges


def test_old_base_without_analyzed_ranges_loads_empty():
    old = {"movesToAnalyze": 16, "blunderValue": 80, "ponderTime": 0.5,
           "useBook": True, "filename": "old"}
    lb = LearningBase._from_dict(LearningBaseData(**old))
    assert lb.analyzedRanges == {}
