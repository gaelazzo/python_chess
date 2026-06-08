"""End-to-end tests for the headless Session controller (proof of concept).

These drive the controller exactly like the game loop would (clicks + key
commands) and assert on `view_model()` -- the data the screen shows -- with no
display and no engine. This is the e2e seam the app was missing.
"""
import chess

from GameState import Move
from session import Session

_R = Move.ranksToRows
_C = Move.filesToCols


def sq(name):
    """'e2' -> (row, col) in the board's internal coordinates."""
    return (_R[name[1]], _C[name[0]])


def test_click_select_then_move_updates_view_model():
    s = Session()
    vm = s.view_model()
    assert vm.turn == "w" and vm.white_up is False

    s.click(*sq("e2"))                       # select the e2 pawn
    vm = s.view_model()
    assert vm.selected == sq("e2")
    assert sq("e4") in vm.move_targets       # e4 highlighted as a legal target
    assert sq("e3") in vm.move_targets

    s.click(*sq("e4"))                       # complete 1.e4
    vm = s.view_model()
    assert vm.turn == "b"                    # Black to move now
    assert vm.selected is None
    assert "e4" in vm.notation


def test_default_analysis_locks_orientation_then_a_unlocks():
    s = Session()
    s.click(*sq("e2")); s.click(*sq("e4"))   # White to Black
    assert s.view_model().white_up is False  # locked (analyze default = True)
    s.do("analyze")                          # turn analysis off -> follow side to move
    assert s.view_model().white_up is True   # Black to move -> board flips


def test_truncate_and_delete_variation_commands():
    s = Session()
    for u in ("e2e4", "e7e5", "g1f3"):
        s.gs.makeChessMove(chess.Move.from_uci(u))
    s.do("undo")                             # back to after e5 (Nf3 is a child)
    s.do("truncate")
    assert s.gs.is_end()                     # continuations removed
    s.do("delete")                           # remove e5 -> back to after e4
    assert len(s.gs.moveLog) == 1


def test_book_panel_toggle_and_query():
    s = Session()
    assert s.view_model().panels["book"] is False
    s.do("book")
    vm = s.view_model()
    assert vm.panels["book"] is True
    assert isinstance(vm.book, list)         # no Polyglot book configured -> []


def test_notation_query_reflects_played_moves():
    s = Session()
    s.click(*sq("e2")); s.click(*sq("e4"))
    s.click(*sq("e7")); s.click(*sq("e5"))
    assert "e4" in s.view_model().notation and "e5" in s.view_model().notation
