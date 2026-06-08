"""E2E tests for the headless mode controller (BoardSession + policies, POC).

Drives the controller like the game loop would (clicks + commands) and asserts on
view_model() -- no display, no engine. Shows that two very different modes (free
analysis vs solve-the-position) share ONE core and differ only in a small policy.
"""
import chess

from GameState import Move
from modes.board_session import BoardSession, AnalysisPolicy, SolvePolicy

_R = Move.ranksToRows
_C = Move.filesToCols


def sq(name):
    """'e2' -> (row, col) in the board's internal coordinates."""
    return (_R[name[1]], _C[name[0]])


# ---------------------------- analysis policy ---------------------------- #
def test_analysis_click_move_updates_view():
    s = BoardSession(AnalysisPolicy())
    s.click(*sq("e2"))
    vm = s.view_model()
    assert vm.selected == sq("e2")
    assert sq("e4") in vm.move_targets
    s.click(*sq("e4"))
    vm = s.view_model()
    assert vm.turn == "b"
    assert "e4" in vm.notation
    assert vm.extra["mode"] == "analysis"


def test_analysis_orientation_locked_then_unlocked():
    s = BoardSession(AnalysisPolicy())
    s.click(*sq("e2")); s.click(*sq("e4"))
    assert s.view_model().white_up is False         # locked by default
    s.do("analyze")                                 # unlock -> follow side to move
    assert s.view_model().white_up is True          # Black to move


def test_analysis_truncate_and_delete():
    s = BoardSession(AnalysisPolicy())
    for u in ("e2e4", "e7e5", "g1f3"):
        s.gs.makeChessMove(chess.Move.from_uci(u))
    s.do("undo")
    s.do("truncate")
    assert s.gs.is_end()
    s.do("delete")
    assert len(s.gs.moveLog) == 1


# ------------------- solve policy (same core, new rules) ----------------- #
def test_solve_wrong_move_is_removed_and_counted():
    s = BoardSession(SolvePolicy([{"setup": [], "correct": "e2e4"}]))
    s.click(*sq("d2")); s.click(*sq("d4"))          # wrong
    vm = s.view_model()
    assert vm.extra["attempts"] == 1
    assert "try again" in vm.message.lower()
    assert "d4" not in vm.notation                  # wrong move removed from the tree


def test_solve_correct_move_advances_and_finishes():
    s = BoardSession(SolvePolicy([
        {"setup": [], "correct": "e2e4"},
        {"setup": ["e2e4", "e7e5"], "correct": "g1f3"},
    ]))
    s.click(*sq("e2")); s.click(*sq("e4"))          # solves #1 -> loads #2
    assert s.view_model().extra["solved"] == 1
    assert "e5" in s.view_model().notation          # now on problem 2
    s.click(*sq("g1")); s.click(*sq("f3"))          # solves #2 -> done
    vm = s.view_model()
    assert vm.extra["solved"] == 2 and vm.extra["done"] is True
    assert vm.message == "Done!"


def test_solve_hint_reveals_correct_move():
    s = BoardSession(SolvePolicy([{"setup": [], "correct": "e2e4"}]))
    s.do("hint")
    assert s.view_model().message.startswith("Hint:")


def test_solve_board_is_fixed_to_user_side():
    white = BoardSession(SolvePolicy([{"setup": [], "correct": "e2e4"}], user_white=True))
    black = BoardSession(SolvePolicy([{"setup": [], "correct": "e2e4"}], user_white=False))
    assert white.view_model().white_up is False
    assert black.view_model().white_up is True
