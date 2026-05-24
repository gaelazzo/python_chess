import chess
import chess.pgn

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


def _two_branch_tree():
    """root -> e4 (3 leaf replies), d4 (2 leaf replies)."""
    game = chess.pgn.Game()
    e4 = game.add_variation(chess.Move.from_uci("e2e4"))
    d4 = game.add_variation(chess.Move.from_uci("d2d4"))
    for u in ("e7e5", "c7c5", "e7e6"):
        e4.add_variation(chess.Move.from_uci(u))
    for u in ("d7d5", "g8f6"):
        d4.add_variation(chess.Move.from_uci(u))
    return game, e4, d4


def test_count_leaves():
    game, e4, d4 = _two_branch_tree()
    assert GameState.count_leaves(e4) == 3
    assert GameState.count_leaves(d4) == 2
    assert GameState.count_leaves(game) == 5        # 3 + 2
    assert GameState.count_leaves(e4.variations[0]) == 1   # a leaf node


def test_make_next_move_weighted_by_leaf_count(monkeypatch):
    import random
    game, e4, d4 = _two_branch_tree()
    gs = GameState()
    gs.pgn = game
    gs.node = game

    captured = {}

    def fake_choices(population, weights=None, k=1):
        captured["weights"] = list(weights)
        return [population[0]]

    monkeypatch.setattr(random, "choices", fake_choices)
    gs.makeNextMove()
    assert captured["weights"] == [3, 2]            # leaves of e4, d4
