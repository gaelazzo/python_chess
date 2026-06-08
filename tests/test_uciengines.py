"""Engine analysis formatting.

Guards the eval-from-White's-POV behaviour of the live analysis panel: the best
line (always shown first) must read positive when White is to move and negative
when Black is to move -- i.e. absolute, lichess/chess.com style.
"""
import chess
import chess.engine

from UCIEngines import format_engine_info_list


def _info(score_value, turn, pv_uci="e2e4"):
    return {
        "score": chess.engine.PovScore(score_value, turn),
        "depth": 12,
        "pv": [chess.Move.from_uci(pv_uci)],
        "time": 1.0,
        "nodes": 1000,
    }


def test_eval_is_positive_for_white_to_move():
    body = " ".join(format_engine_info_list([_info(chess.engine.Cp(30), chess.WHITE)]))
    assert "Eval 0.30" in body


def test_eval_is_negated_for_black_to_move():
    # +30 from Black's POV is -30 from White's POV (absolute).
    body = " ".join(format_engine_info_list([_info(chess.engine.Cp(30), chess.BLACK)]))
    assert "Eval -0.30" in body


def test_mate_sign_follows_white_pov():
    white = " ".join(format_engine_info_list([_info(chess.engine.Mate(3), chess.WHITE)]))
    black = " ".join(format_engine_info_list([_info(chess.engine.Mate(3), chess.BLACK)]))
    assert "Mate in 3" in white     # White delivers mate
    assert "Mate in -3" in black    # Black delivers mate -> negative (White POV)
