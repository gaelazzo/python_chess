"""Opening-book guide for Play-vs-computer -- pure logic, offline."""
import chess

import guide_book as gb


def _board(*sans):
    b = chess.Board()
    for s in sans:
        b.push_san(s)
    return b


def test_load_index_and_continuations(tmp_path):
    rep = tmp_path / "r.pgn"
    rep.write_text('[Event "R"]\n\n1. e4 e5 (1... c5) 2. Nf3 *\n', encoding="utf-8")
    idx = gb.load_index(str(rep))

    assert set(gb.book_continuations(idx, chess.Board())) == {"e2e4"}
    assert set(gb.book_continuations(idx, _board("e4"))) == {"e7e5", "c7c5"}   # main + variation
    assert set(gb.book_continuations(idx, _board("e4", "e5"))) == {"g1f3"}
    assert gb.book_continuations(idx, _board("e4", "e5", "Nf3")) == []         # off-book


def test_transposition_merges_continuations(tmp_path):
    # Same position by two move orders -> its continuations merge (zobrist key).
    rep = tmp_path / "t.pgn"
    rep.write_text('[Event "A"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 *\n\n'
                   '[Event "B"]\n\n1. Nf3 Nc6 2. e4 e5 3. Bc4 *\n', encoding="utf-8")
    idx = gb.load_index(str(rep))
    p = _board("e4", "e5", "Nf3", "Nc6")        # reached by both orders
    assert set(gb.book_continuations(idx, p)) == {"f1b5", "f1c4"}


def test_book_move_random_choice_and_deviation(tmp_path, monkeypatch):
    rep = tmp_path / "r.pgn"
    rep.write_text('[Event "R"]\n\n1. e4 *\n', encoding="utf-8")
    idx = gb.load_index(str(rep))

    monkeypatch.setattr(gb.random, "random", lambda: 0.99)   # above DEVIATION -> book move
    assert gb.book_move(idx, chess.Board()) == "e2e4"
    monkeypatch.setattr(gb.random, "random", lambda: 0.0)    # below DEVIATION -> engine (None)
    assert gb.book_move(idx, chess.Board()) is None
    # off-book -> None whatever the roll
    assert gb.book_move(idx, _board("d4")) is None


def test_missing_file_is_empty():
    assert gb.load_index("does/not/exist.pgn") == {}
    assert gb.book_continuations({}, chess.Board()) == []
    assert gb.book_move({}, chess.Board()) is None
