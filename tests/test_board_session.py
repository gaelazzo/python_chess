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


def test_click_promotion_defaults_to_queen():
    s = BoardSession(AnalysisPolicy())
    s.gs.setFen("8/4P3/8/8/8/8/8/4k2K w - - 0 1")    # White pawn e7 ready to promote
    s.click(*sq("e7"))                                # select the pawn
    moved = s.click(*sq("e8"))                        # complete -> auto-queen
    assert moved is not None and moved.uci == "e7e8q"
    assert "e8=Q" in s.view_model().notation


def test_click_promotion_uses_the_port():
    s = BoardSession(AnalysisPolicy())
    s.gs.setFen("8/4P3/8/8/8/8/8/4k2K w - - 0 1")
    s.click(*sq("e7"))
    moved = s.click(*sq("e8"), ask_promotion=lambda color: "n")   # underpromote
    assert moved is not None and moved.uci == "e7e8n"


def test_analysis_orientation_locked_then_unlocked():
    s = BoardSession(AnalysisPolicy())
    s.click(*sq("e2")); s.click(*sq("e4"))
    assert s.view_model().white_up is False         # locked by default
    s.do("analyze")                                 # unlock -> follow side to move
    assert s.view_model().white_up is True          # Black to move


def test_flip_command_is_manual_and_unconditional():
    s = BoardSession(AnalysisPolicy())              # locked by default
    assert s.view_model().white_up is False
    s.do("flip")
    assert s.view_model().white_up is True          # manual flip works even when locked
    s.do("flip")
    assert s.view_model().white_up is False


def test_orientation_stays_fixed_against_a_cpu_even_when_unlocked():
    s = BoardSession(AnalysisPolicy(), black_cpu=True)
    s.do("analyze")                                 # unlock the lock...
    s.click(*sq("e2")); s.click(*sq("e4"))          # ...but a CPU keeps the board fixed
    assert s.view_model().white_up is False


def test_reorient_method_applies_policy_rule():
    s = BoardSession(AnalysisPolicy())
    s.gs.makeChessMove(chess.Move.from_uci("e2e4"))  # Black to move
    s.policy.locked = False
    s.reorient()
    assert s.view_model().white_up is True           # unlocked -> follows side to move
    s.policy.locked = True
    s.gs.makeChessMove(chess.Move.from_uci("e7e5"))  # White to move
    s.reorient()
    assert s.view_model().white_up is True           # locked -> unchanged


# ----- play-loop behaviours now covered headlessly (panels, flip, undo) ----- #
def test_panel_visibility_toggles_via_the_session():
    s = BoardSession(AnalysisPolicy())
    assert s.view_model().panels == {"book": False, "pgn": False, "cpu": False}
    s.do("book")
    assert s.view_model().panels["book"] is True
    s.do("pgn")
    assert s.view_model().panels["pgn"] is True
    s.do("book")
    assert s.view_model().panels["book"] is False        # toggles back off


def test_panel_visibility_persists_across_a_move():
    s = BoardSession(AnalysisPolicy())
    s.do("book")
    s.click(*sq("e2")); s.click(*sq("e4"))               # a move must not reset the toggle
    assert s.view_model().panels["book"] is True


def test_view_model_exposes_the_analysis_lock():
    s = BoardSession(AnalysisPolicy())
    assert s.view_model().extra["locked"] is True        # analysis (board fixed) by default
    s.do("analyze")
    assert s.view_model().extra["locked"] is False


def test_undo_reorients_when_unlocked():
    s = BoardSession(AnalysisPolicy())
    s.do("analyze")                                      # unlocked -> follow side to move
    s.click(*sq("e2")); s.click(*sq("e4"))               # Black to move
    assert s.view_model().white_up is True
    s.do("undo")                                         # back to White to move
    assert s.view_model().white_up is False              # undo re-orients too


def test_manual_flip_persists_across_a_move_when_locked():
    s = BoardSession(AnalysisPolicy())                   # locked
    s.do("flip")
    s.click(*sq("e2")); s.click(*sq("e4"))
    assert s.view_model().white_up is True               # locked -> the manual flip survives


def test_unlocked_orientation_follows_side_to_move_despite_flips():
    s = BoardSession(AnalysisPolicy())
    s.do("analyze")                                      # unlocked
    s.do("flip"); s.do("flip"); s.do("flip")             # arbitrary manual flip state
    s.click(*sq("e2")); s.click(*sq("e4"))               # Black to move
    assert s.view_model().white_up is True               # the flip is transient...
    s.click(*sq("e7")); s.click(*sq("e5"))               # White to move
    assert s.view_model().white_up is False              # ...orientation tracks side to move


def test_next_move_follows_mainline_by_default():
    s = BoardSession(AnalysisPolicy())
    for u in ("e2e4", "e7e5", "g1f3"):
        s.gs.makeChessMove(chess.Move.from_uci(u))
    for _ in range(3):
        s.do("undo")                              # back to the start
    assert s.gs.moveLog == []
    m = s.next_move()                             # no port -> main line
    assert m.uci() == "e2e4"


def test_next_move_uses_variation_picker_port():
    s = BoardSession(AnalysisPolicy())
    s.gs.makeChessMove(chess.Move.from_uci("e2e4")); s.do("undo")
    s.gs.makeChessMove(chess.Move.from_uci("d2d4")); s.do("undo")
    seen = {}

    def port(moves, board):
        seen["count"] = len(moves)
        return moves[1]                           # choose the variation, not the main line

    m = s.next_move(pick_variation=port)
    assert seen["count"] == 2 and m.uci() == "d2d4"


def test_next_move_cancel_does_nothing():
    s = BoardSession(AnalysisPolicy())
    s.gs.makeChessMove(chess.Move.from_uci("e2e4")); s.do("undo")
    s.gs.makeChessMove(chess.Move.from_uci("d2d4")); s.do("undo")
    assert s.next_move(pick_variation=lambda moves, board: None) is None  # cancelled
    assert s.gs.moveLog == []                      # nothing was played


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


def test_analysis_delete_whole_variation_line():
    s = BoardSession(AnalysisPolicy())
    for u in ("e2e4", "e7e5", "g1f3"):
        s.gs.makeChessMove(chess.Move.from_uci(u))
    s.gs.undoMove()
    s.gs.makeChessMove(chess.Move.from_uci("f1c4"))   # enter a variation
    assert s.gs.isInVariation() is True
    s.do("delete_line")
    assert s.gs.isInVariation() is False              # whole variation removed
    assert "Bc4" not in s.view_model().notation


def test_solve_board_is_fixed_to_user_side():
    white = BoardSession(SolvePolicy([{"setup": [], "correct": "e2e4"}], user_white=True))
    black = BoardSession(SolvePolicy([{"setup": [], "correct": "e2e4"}], user_white=False))
    assert white.view_model().white_up is False
    assert black.view_model().white_up is True
