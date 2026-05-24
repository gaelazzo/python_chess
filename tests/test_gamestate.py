import chess

from GameState import GameState, NAG_SYMBOL


def _game(ucis):
    gs = GameState()
    for u in ucis:
        gs.makeChessMove(chess.Move.from_uci(u))
    return gs


def test_annotate_last_move():
    gs = _game(["e2e4", "e7e5", "g1f3"])
    assert gs.setMoveNag(1) is True              # mark Nf3 as good "!"
    assert gs.getMoveGlyphs() == ["", "", NAG_SYMBOL[1]]


def test_annotation_is_unique_and_replaces():
    gs = _game(["e2e4", "e7e5", "g1f3"])
    gs.setMoveNag(1)      # !
    gs.setMoveNag(16)     # replaces with ± -- a move has a single annotation
    assert gs.getMoveGlyphs()[2] == NAG_SYMBOL[16]


def test_clear_and_zero_remove_annotation():
    gs = _game(["e2e4", "e7e5", "g1f3"])
    gs.setMoveNag(4)
    assert gs.getMoveGlyphs()[2] == NAG_SYMBOL[4]
    gs.clearMoveNags()
    assert gs.getMoveGlyphs()[2] == ""
    gs.setMoveNag(5)
    gs.setMoveNag(0)      # falsy nag clears
    assert gs.getMoveGlyphs()[2] == ""


def test_cannot_annotate_start_position():
    gs = GameState()
    assert gs.setMoveNag(1) is False
    assert gs.clearMoveNags() is False
    assert gs.getMoveGlyphs() == []


def test_set_and_get_move_comment():
    gs = _game(["e2e4", "e7e5", "g1f3"])
    assert gs.setMoveComment("develops the knight") is True
    assert gs.getMoveComment() == "develops the knight"
    gs.setMoveComment("")                 # empty clears it
    assert gs.getMoveComment() == ""


def test_cannot_comment_start_position():
    gs = GameState()
    assert gs.setMoveComment("x") is False
    assert gs.getMoveComment() == ""


def test_to_pgn_string_includes_comment():
    gs = _game(["e2e4"])
    gs.setMoveComment("good start")
    assert "good start" in gs.to_PgnString()
