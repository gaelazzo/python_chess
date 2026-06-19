"""Tests for the live 'only move' detection and the board arrow geometry
(no display needed: pure logic / arithmetic)."""
import chess
from chess.engine import Cp, PovScore

import UCIEngines
import BoardScreen as BS


def _line(cp_stm, move_uci, depth=12):
    """A fake multipv entry: score (side-to-move POV), pv head, depth."""
    return {"score": PovScore(Cp(cp_stm), chess.WHITE),
            "pv": [chess.Move.from_uci(move_uci)],
            "depth": depth}


def test_detect_only_move_flags_a_clear_gap():
    mv = UCIEngines._detect_only_move([_line(30, "e2e4"), _line(-300, "d2d4")])
    assert mv == chess.Move.from_uci("e2e4")


def test_detect_only_move_moderate_edge_triggers():
    # The user's case: best +0.97 vs 2nd +0.29 -> ~6.2 win% gap -> arrow shows.
    mv = UCIEngines._detect_only_move([_line(97, "e2e4"), _line(29, "d2d4")])
    assert mv == chess.Move.from_uci("e2e4")


def test_detect_only_move_none_for_marginal_edge():
    # +0.50 vs +0.20 -> ~2.8 win% gap -> below the arrow threshold (not "the move").
    assert UCIEngines._detect_only_move([_line(50, "e2e4"), _line(20, "d2d4")]) is None


def test_detect_only_move_none_when_too_shallow():
    assert UCIEngines._detect_only_move(
        [_line(30, "e2e4", depth=3), _line(-300, "d2d4", depth=3)]) is None


def test_detect_only_move_none_with_single_line():
    assert UCIEngines._detect_only_move([_line(30, "e2e4")]) is None


def test_square_center_white_at_bottom():
    BS.whiteUp = False
    # e2: file e (col 4), rank 2 (internal row 6); SQ_SIZE=64, BOARD_Y=40.
    assert BS._square_center(chess.E2) == (4 * BS.SQ_SIZE + BS.SQ_SIZE / 2,
                                           BS.BOARD_Y + 6 * BS.SQ_SIZE + BS.SQ_SIZE / 2)


def test_square_center_flips_with_orientation():
    BS.whiteUp = False
    bottom = BS._square_center(chess.E2)
    BS.whiteUp = True
    flipped = BS._square_center(chess.E2)
    BS.whiteUp = False     # restore
    assert flipped != bottom
    # Flipping mirrors both axes within the board.
    assert flipped[0] == (7 - 4) * BS.SQ_SIZE + BS.SQ_SIZE / 2
