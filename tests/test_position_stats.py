"""Position statistics against a reference PGN (build_index / lookup_position).

Pure logic over a tiny temp PGN: results are aggregated from White's POV and the
continuation moves are counted per position.
"""
import chess

import position_stats


def _db(tmp_path):
    p = tmp_path / "games.pgn"
    p.write_text(
        '[Event "1"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 1-0\n\n'
        '[Event "2"]\n[Result "0-1"]\n\n1. e4 c5 0-1\n\n'
        '[Event "3"]\n[Result "1/2-1/2"]\n\n1. d4 d5 1/2-1/2\n',
        encoding="utf-8",
    )
    return str(p)


def test_start_position_aggregates_results_and_moves(tmp_path):
    stats = position_stats.lookup_position(_db(tmp_path), chess.Board())
    assert stats["total"] == 3                 # 3 games pass through the start
    assert stats["results"][1] == 1            # one White win
    assert stats["results"][-1] == 1           # one Black win
    assert stats["results"][0] == 1            # one draw
    assert stats["moves"]["e2e4"]["count"] == 2
    assert stats["moves"]["d2d4"]["count"] == 1


def test_unseen_position_is_empty(tmp_path):
    board = chess.Board()
    board.push_uci("h2h4")                      # never played in the DB
    stats = position_stats.lookup_position(_db(tmp_path), board)
    assert stats["total"] == 0
    assert stats["moves"] == {}
