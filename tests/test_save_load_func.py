"""Functional round-trip for saving/loading a game.

Uses a temp PGN folder and stubs out the on-screen feedback, so it exercises the
real save_load.save_game -> PgnGameList -> disk -> reload path without a display.
This is the kind of test that catches signature/persistence bugs that otherwise
only show up by clicking through the app.
"""
import chess

MOVES = ["e2e4", "e7e5", "g1f3", "b8c6"]


def _make_game(ucis):
    from GameState import GameState
    gs = GameState()
    for u in ucis:
        gs.makeChessMove(chess.Move.from_uci(u))
    return gs


def _save_and_reload(tmp_path, monkeypatch, moves):
    """Save `moves` as a new game via save_load.save_game, then reload it."""
    import save_load
    import state
    import pgngamelist
    from GameState import GameState

    # redirect PGN storage into a temp folder
    monkeypatch.setattr(pgngamelist, "BASE_PATH", str(tmp_path))
    (tmp_path / "pgn").mkdir(exist_ok=True)

    # silence the UI side of save_game
    monkeypatch.setattr(save_load.app, "main_background", lambda: None)
    monkeypatch.setattr(save_load.app, "delay", lambda *a, **k: None)
    monkeypatch.setattr(save_load.BS, "drawEndGameText", lambda *a, **k: None)
    monkeypatch.setattr(save_load.BS, "update", lambda *a, **k: None)

    gs = _make_game(moves)
    state.positionParameters["filename"] = "unittest_game"
    state.positionParameters["gameid"] = None

    save_load.save_game(gs)
    gid = state.positionParameters["gameid"]
    assert gid is not None

    gl = pgngamelist.PgnGameList("unittest_game")
    assert not gl.isEmpty(), "saved game was not persisted to disk"
    gs2 = GameState()
    assert gl.load_game(gs2, gid) is True
    return gs2


def test_save_new_game_then_reload_roundtrip(tmp_path, monkeypatch):
    gs2 = _save_and_reload(tmp_path, monkeypatch, MOVES)
    assert [m.uci() for m in gs2.pgn.mainline_moves()] == MOVES


def test_loaded_game_starts_at_first_move(tmp_path, monkeypatch):
    # A loaded game must sit at the first move (empty moveLog) so that, in
    # analysis (human-vs-human), it can be stepped forward with chooseNextMove,
    # exploring variations. (Load is disabled when playing vs the computer.)
    gs2 = _save_and_reload(tmp_path, monkeypatch, MOVES)
    assert gs2.moveLog == []
    assert not gs2.is_end()              # there are moves to step into
    assert gs2.getNextMoves()            # chooseNextMove has something to offer
