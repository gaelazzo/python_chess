import chess

from GameState import GameState
from notation import notation_items


def _build():
    """1.e4 e5 2.Nf3! {develops} (2.Nc3 {alt}) 2...Nc6"""
    gs = GameState()
    gs.makeChessMove(chess.Move.from_uci("e2e4"))
    gs.makeChessMove(chess.Move.from_uci("e7e5"))
    gs.makeChessMove(chess.Move.from_uci("g1f3"))   # mainline 2.Nf3
    gs.setMoveNag(1)                                 # 2.Nf3!
    gs.setMoveComment("develops")
    gs.undoMove()                                    # back to e5
    gs.makeChessMove(chess.Move.from_uci("b1c3"))   # variation 2.Nc3
    gs.setMoveComment("alt")
    gs.undoMove()                                    # back to e5
    gs.makeChessMove(chess.Move.from_uci("g1f3"))   # follow mainline Nf3 again
    gs.makeChessMove(chess.Move.from_uci("b8c6"))   # 2...Nc6
    return gs


def test_notation_items_structure():
    gs = _build()
    items = notation_items(gs.pgn)
    simplified = [(k, t, d, nl) for (k, t, d, node, nl) in items]
    assert simplified == [
        ("move", "1.e4", 0, False),
        ("move", "e5", 0, False),
        ("move", "2.Nf3!", 0, False),
        ("comment", "develops", 0, False),
        ("move", "2.Nc3", 1, True),       # variation: indented, on a new line
        ("comment", "alt", 1, False),
        ("move", "2...Nc6", 0, True),     # mainline resumes on a new line
    ]
    # move tokens carry their node; comment tokens don't
    for k, t, d, node, nl in items:
        assert (node is not None) == (k == "move")


def test_go_to_node_jumps_into_variation():
    gs = _build()
    items = notation_items(gs.pgn)
    nc3 = next(node for (k, t, d, node, nl) in items if t == "2.Nc3")
    assert gs.goToNode(nc3) is True
    assert gs.node is nc3
    assert [m.getChessNotation() for m in gs.moveLog] == ["e2e4", "e7e5", "b1c3"]
