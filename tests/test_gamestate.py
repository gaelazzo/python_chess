import chess
import chess.pgn

from GameState import GameState, NAG_SYMBOL


def _game(ucis):
    gs = GameState()
    for u in ucis:
        gs.makeChessMove(chess.Move.from_uci(u))
    return gs


def test_transposition_detection_and_freeze():
    # Mainline 1.Nf3 d5 2.d4 and variation 1.d4 d5 2.Nf3 reach the SAME position.
    gs = _game(["g1f3", "d7d5", "d2d4"])
    node_main = gs.node
    gs.gotoFirstMove()
    for u in ["d2d4", "d7d5", "g1f3"]:          # a transposing variation off the root
        gs.makeChessMove(chess.Move.from_uci(u))
    node_var = gs.node

    assert node_var is not node_main
    assert node_main in gs.transpositions_of(node_var)        # they are transpositions
    assert gs.canonical_node(node_var) is node_main           # mainline came first
    assert gs.is_frozen(node_var) is True                     # the variation node is the duplicate
    assert gs.is_frozen(node_main) is False                   # the canonical is not frozen
    assert gs.find_node_by_fen(node_var.board().fen()) is node_main   # FEN search -> canonical
    assert gs.transpositions_of(gs.pgn) == []                 # the root position is unique


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


def test_truncate_after_current_removes_continuations():
    gs = _game(["e2e4", "e7e5", "g1f3"])
    gs.undoMove()                          # back to after e5; Nf3 is a child
    assert gs.node.variations              # there is a continuation
    assert gs.truncateAfterCurrent() is True
    assert gs.node.variations == []        # continuations removed
    assert gs.is_end()
    assert gs.truncateAfterCurrent() is False   # nothing left to truncate


def test_delete_current_variation_steps_back():
    gs = _game(["e2e4", "e7e5"])
    assert len(gs.moveLog) == 2
    assert gs.deleteCurrentVariation() is True   # remove e5, back to after e4
    assert len(gs.moveLog) == 1
    assert gs.board().fen().split()[0] == \
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR"
    assert all(v.move.uci() != "e7e5" for v in gs.node.variations)  # e5 gone


def test_delete_current_variation_noop_at_root():
    gs = GameState()
    assert gs.deleteCurrentVariation() is False


def test_delete_whole_variation_line():
    gs = _game(["e2e4", "e7e5", "g1f3"])
    gs.undoMove()                                   # back to after e5 (main line)
    assert gs.isInVariation() is False
    gs.makeChessMove(chess.Move.from_uci("f1c4"))   # 2. Bc4  -> a variation
    gs.makeChessMove(chess.Move.from_uci("f8c5"))   # 2... Bc5 (deep in the variation)
    assert gs.isInVariation() is True
    assert gs.deleteCurrentVariationLine() is True  # delete the whole Bc4 line
    assert gs.isInVariation() is False              # back on the main line (after e5)
    pgn = gs.to_PgnString()
    assert "Bc4" not in pgn and "Bc5" not in pgn    # the variation is gone
    assert "Nf3" in pgn                             # the main line is intact


def test_delete_variation_line_noop_on_mainline():
    gs = _game(["e2e4", "e7e5"])
    assert gs.isInVariation() is False
    assert gs.deleteCurrentVariationLine() is False


def test_promote_variation_becomes_main_line():
    gs = _game(["e2e4", "e7e5", "g1f3"])            # main: 1.e4 e5 2.Nf3
    gs.undoMove()                                   # back to after 1...e5 (main line)
    gs.makeChessMove(chess.Move.from_uci("f1c4"))   # 2.Bc4  -> a variation off the main line
    gs.makeChessMove(chess.Move.from_uci("f8c5"))   # 2...Bc5 (deep in the variation)
    assert gs.isInVariation() is True
    assert gs.promoteCurrentVariation() is True
    assert gs.isInVariation() is False              # current line is now the main line
    branch = gs.node.parent.parent                  # node after 1...e5 (branch point)
    assert branch.variations[0].move.uci() == "f1c4"            # Bc4 promoted to main
    assert any(v.move.uci() == "g1f3" for v in branch.variations)  # Nf3 kept as secondary
    assert gs.node.move.uci() == "f8c5"             # position unchanged by the promotion


def test_promote_variation_noop_on_mainline():
    gs = _game(["e2e4", "e7e5"])
    assert gs.isInVariation() is False
    assert gs.promoteCurrentVariation() is False


def test_promote_walks_up_one_level_per_call():
    # main: 1.e4 e5 2.Nf3 | variation A after 1...e5: 2.Bc4 | sub-variation B of A: 2...Nc6
    game = chess.pgn.Game()
    e4 = game.add_variation(chess.Move.from_uci("e2e4"))
    e5 = e4.add_variation(chess.Move.from_uci("e7e5"))
    e5.add_variation(chess.Move.from_uci("g1f3"))        # main reply (Nf3)
    bc4 = e5.add_variation(chess.Move.from_uci("f1c4"))  # variation A
    bc4.add_variation(chess.Move.from_uci("f8c5"))       # A's main reply (Bc5)
    nc6 = bc4.add_variation(chess.Move.from_uci("b8c6"))  # sub-variation B
    gs = GameState()
    gs.pgn = game
    gs.node = nc6                                   # sitting in the sub-variation
    assert gs.isInVariation() is True

    assert gs.promoteCurrentVariation() is True     # 1st P: promote B within A
    assert bc4.variations[0] is nc6                 # Nc6 now A's main reply
    assert gs.isInVariation() is True               # still inside variation A

    assert gs.promoteCurrentVariation() is True     # 2nd P: promote A within the main line
    assert e5.variations[0] is bc4                  # Bc4 now the main reply to 1...e5
    assert gs.isInVariation() is False              # fully on the main line now


def test_next_move_lines_main_then_variations():
    # at the start, 1.e4 main with 1.d4 / 1.c4 as alternative variations
    gs = GameState()
    gs.pgn.add_variation(chess.Move.from_uci("e2e4"))    # main next move
    gs.pgn.add_variation(chess.Move.from_uci("d2d4"))    # variation
    gs.pgn.add_variation(chess.Move.from_uci("c2c4"))    # variation
    gs.node = gs.pgn
    assert gs.getNextMoveLines() == ["1. e4", "   - d4", "   - c4"]


def test_next_move_lines_black_to_move_numbering():
    gs = _game(["e2e4"])                                  # 1.e4, Black to move
    gs.node.add_variation(chess.Move.from_uci("e7e5"))   # main reply
    gs.node.add_variation(chess.Move.from_uci("c7c5"))   # variation
    assert gs.getNextMoveLines() == ["1... e5", "   - c5"]


def test_next_move_lines_single_move_has_no_variations():
    gs = _game(["e2e4"])
    gs.node.add_variation(chess.Move.from_uci("e7e5"))   # only one continuation
    assert gs.getNextMoveLines() == ["1... e5"]           # no fork -> just the next move


def test_next_move_lines_empty_at_end_of_line():
    gs = _game(["e2e4", "e7e5"])                          # no stored continuation
    assert gs.getNextMoveLines() == []


def test_promote_keeps_history_navigable():
    """After promoting, back/forward navigation stays consistent: promote only
    reorders variations, so the move history (moveLog) is untouched and the
    line you were on is now the main line you retrace going forward."""
    gs = _game(["e2e4", "e7e5", "g1f3"])            # main: e4 e5 Nf3
    gs.undoMove()
    gs.makeChessMove(chess.Move.from_uci("f1c4"))   # Bc4 (variation)
    gs.makeChessMove(chess.Move.from_uci("f8c5"))   # Bc5
    assert gs.promoteCurrentVariation() is True
    end_fen = gs.board().fen()
    assert len(gs.moveLog) == 4                      # history intact after promote

    gs.gotoFirstMove()                               # backward all the way: no desync
    assert len(gs.moveLog) == 0
    assert gs.node.parent is None

    gs.goToLastMove()                                # forward along the (new) main line
    assert gs.board().fen() == end_fen               # retraces the promoted line (Bc4/Bc5), not Nf3
    assert len(gs.moveLog) == 4
