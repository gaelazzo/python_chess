"""Tests for the deterministic core of move_review (no engine, no server)."""
import chess
from chess.engine import Cp, Mate

import move_review as mr


# --- win% and verdict bands ------------------------------------------------

def test_win_percent_anchor_and_monotonic():
    assert abs(mr.win_percent(0) - 50.0) < 1e-6      # dead even -> 50%
    assert mr.win_percent(-100) < mr.win_percent(0) < mr.win_percent(100)
    assert abs((mr.win_percent(300) - 50.0) + (mr.win_percent(-300) - 50.0)) < 1e-6
    assert 0.0 <= mr.win_percent(-mr.MATE_CP) < 1.0
    assert 99.0 < mr.win_percent(mr.MATE_CP) <= 100.0


def test_classify_bands():
    assert mr.classify(0.0, is_best=True) == "best"
    assert mr.classify(99.0, is_best=True) == "best"
    assert mr.classify(0.0) == "good"
    assert mr.classify(mr.INACCURACY) == "inaccuracy"
    assert mr.classify(mr.MISTAKE) == "mistake"
    assert mr.classify(mr.BLUNDER) == "blunder"


# --- eval-swing -> material word (no piece counting) -----------------------

def test_value_word_bands():
    assert mr._value_word(0.5) is None         # below ~a pawn
    assert mr._value_word(1.0) == "a pawn"     # 0.8 .. 1.4
    assert mr._value_word(1.6) == "the exchange"
    assert mr._value_word(2.3) == "a piece"    # >= 2.0
    assert mr._value_word(5.0) == "a rook"
    assert mr._value_word(9.0) == "a queen"
    assert mr._value_word(-3.0) == "a piece"   # magnitude only


# --- _explain reads the score (mover POV) directly -------------------------

def test_explain_loses_a_piece_from_eval_drop():
    # +0.50 -> -2.50 is a 3-pawn swing -> "a piece".
    reason = mr._explain(Cp(50), Cp(-250), is_best=False, verdict="blunder")
    assert reason["kind"] == "loses_value"
    assert reason["material"] == "a piece"


def test_explain_loses_a_pawn_from_eval_drop():
    reason = mr._explain(Cp(30), Cp(-80), is_best=False, verdict="inaccuracy")
    assert reason["kind"] == "loses_value"
    assert reason["material"] == "a pawn"


def test_explain_good_move_makes_no_material_claim():
    # A "good" verdict: even a 1-pawn eval wobble at a decided position is not
    # reported as losing material.
    reason = mr._explain(Cp(800), Cp(700), is_best=False, verdict="good")
    assert reason["kind"] == "positional"


def test_explain_allows_mate():
    reason = mr._explain(Cp(0), Mate(-1), is_best=False, verdict="blunder")
    assert reason["kind"] == "allows_mate"
    assert reason["mate"] == -1


def test_explain_missed_mate():
    reason = mr._explain(Mate(3), Cp(120), is_best=False, verdict="mistake")
    assert reason["kind"] == "missed_mate"
    assert reason["mate"] == 3


def test_explain_best_mates():
    reason = mr._explain(Mate(2), Cp(0), is_best=True, verdict="best")
    assert reason["kind"] == "best_mates"
    assert reason["mate"] == 2


def test_explain_best_move_is_positional():
    reason = mr._explain(Cp(20), Cp(18), is_best=True, verdict="best")
    assert reason["kind"] == "positional"


# --- only-move (win% gap to the runner-up) ---------------------------------

def test_is_only_move():
    assert mr._is_only_move(50, -300)        # holds an even-ish game vs a losing 2nd
    assert not mr._is_only_move(50, 0)        # a small edge over the 2nd -> not forced
    assert not mr._is_only_move(800, 500)     # both clearly winning -> not "only move"


# --- template verbalization ------------------------------------------------

def test_template_best_move_has_no_suggestion():
    facts = {
        "verdict": "best", "is_best": True, "eval_before": "+0.30", "eval_after": "+0.32",
        "best_move_san": "Nf3", "best_line_san": ["Nf3", "Nc6"],
        "reason": {"kind": "positional"},
    }
    text = mr.verbalize_template(facts)
    assert text.startswith("Best move.")
    assert "(White POV)" in text
    assert "Best was" not in text


def test_template_good_move_still_suggests_best():
    facts = {
        "verdict": "good", "is_best": False, "eval_before": "+0.20", "eval_after": "+0.05",
        "best_move_san": "Bc4", "best_line_san": ["Bc4", "Nf6"],
        "reason": {"kind": "positional"},
    }
    text = mr.verbalize_template(facts)
    assert text.startswith("Good move.")
    assert "Best was Bc4" in text


def test_template_loses_value_with_punishing_line():
    facts = {
        "verdict": "blunder", "is_best": False, "eval_before": "+0.50", "eval_after": "-2.50",
        "best_move_san": "Qe2", "best_line_san": ["Qe2", "O-O"],
        "refutation_san": ["Nxg4", "hxg4"],          # a capture -> named as the punishment
        "reason": {"kind": "loses_value", "material": "a piece"},
    }
    text = mr.verbalize_template(facts)
    assert text.startswith("Blunder.")
    assert "loses about a piece to Nxg4" in text
    assert "Best was Qe2" in text


def test_template_loses_value_quiet_line_omits_to_clause():
    facts = {
        "verdict": "mistake", "is_best": False, "eval_before": "+1.80", "eval_after": "+0.20",
        "best_move_san": "d4", "best_line_san": ["d4"],
        "refutation_san": ["Nf6", "Nc3"],            # quiet -> no "to ..." clause
        "reason": {"kind": "loses_value", "material": "the exchange"},
    }
    text = mr.verbalize_template(facts)
    assert "loses about the exchange." in text
    assert " to " not in text.split("Eval")[0]       # no punishment clause before the eval line


def test_template_only_move_found_is_praised():
    facts = {
        "verdict": "best", "is_best": True, "eval_before": "+0.10", "eval_after": "+0.12",
        "best_move_san": "Rf8", "best_line_san": ["Rf8"],
        "reason": {"kind": "positional"},
        "only_move": True, "second_eval": "-1.80",
    }
    text = mr.verbalize_template(facts)
    assert "The only good move." in text
    assert "-1.80" not in text     # the runner-up eval is intentionally not quoted


def test_template_only_move_missed_tags_the_best():
    facts = {
        "verdict": "mistake", "is_best": False, "eval_before": "+0.30", "eval_after": "-1.40",
        "best_move_san": "Kg1", "best_line_san": ["Kg1", "Qh3"],
        "reason": {"kind": "loses_value", "material": "a pawn"},
        "only_move": True, "second_eval": "-1.50",
    }
    text = mr.verbalize_template(facts)
    assert "Best was Kg1 -- the only move" in text
    assert "The only good move" not in text     # the missed-move framing, not praise


def test_template_missed_mate_does_not_duplicate_best():
    facts = {
        "verdict": "mistake", "is_best": False, "eval_before": "+M3", "eval_after": "+1.20",
        "best_move_san": "Qh5", "best_line_san": ["Qh5"],
        "reason": {"kind": "missed_mate", "mate": 3},
    }
    text = mr.verbalize_template(facts)
    assert "forced mate in 3" in text
    assert "Qh5" in text
    assert "Best was" not in text
