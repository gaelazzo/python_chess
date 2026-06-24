"""Repertoire gap analysis -- pure logic, run offline with injected fakes.

The two real dependencies (the games index `position_stats.lookup_position` and
the masters strength check) are replaced by fakes keyed on the position FEN, so
no PGN-of-your-games and no network are needed.
"""
import io

import chess

import repertoire_gaps as rg
from repertoire_gaps import COVERED, GAP, WEAK, UNVERIFIED


def _board_after(*sans):
    """A board reached by playing the given SAN moves from the start."""
    b = chess.Board()
    for san in sans:
        b.push_san(san)
    return b


def _fake_lookup(table):
    """position_stats.lookup_position stand-in: per-FEN {uci: count} table."""
    def lookup(_reference_db, board):
        moves = table.get(board.fen(), {})
        return {"moves": {uci: {"count": c, "results": {}} for uci, c in moves.items()}}
    return lookup


def _fake_masters(table):
    """masters strength stand-in: per-FEN {uci: share}; None signals 'offline'."""
    def masters(fen, *, min_share=rg.DEFAULT_MIN_SHARE, min_total=rg.DEFAULT_MIN_TOTAL):
        return table.get(fen)
    return masters


def _statuses(report):
    return {r.uci: r.status for r in report.replies}


def test_classifies_covered_gap_and_weak():
    # Repertoire: a single Ruy Lopez line. User is White.
    pgn = '[Event "R"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 *\n'
    games = [chess.pgn.read_game(io.StringIO(pgn))]
    covered = rg.covered_positions(games)

    board = _board_after("e4")                       # opponent (Black) to move
    fen = board.fen()
    lookup = _fake_lookup({fen: {"e7e5": 10, "c7c5": 8, "e7e6": 2, "g8f6": 1}})
    masters = _fake_masters({fen: {"c7c5": 0.40, "e7e6": 0.08}})  # e5 covered; Nf6 absent

    report = rg.analyze_node(board, covered=covered, reference_db="x",
                             lookup=lookup, masters=masters)
    st = _statuses(report)
    assert st["e7e5"] == COVERED      # leads to a position already in the repertoire
    assert st["c7c5"] == GAP          # uncovered + strong
    assert st["e7e6"] == GAP          # uncovered + strong (0.08 >= 0.05 default)
    assert st["g8f6"] == WEAK         # uncovered + not played by masters
    assert report.masters_ok is True


def test_transposition_is_covered_not_a_gap():
    # Two roots reach the same position by different move orders:
    #   A: 1.e4 e5 2.Nf3 Nc6   B-stub: 1.e4 Nc6 2.Nf3 (no child)
    # At the B-stub node, the opponent reply ...e5 transposes into A's position,
    # so it must be COVERED even though it is NOT a direct child here.
    pgn = ('[Event "A"]\n\n1. e4 e5 2. Nf3 Nc6 *\n\n'
           '[Event "B"]\n\n1. e4 Nc6 2. Nf3 *\n')
    games = []
    fh = io.StringIO(pgn)
    while (g := chess.pgn.read_game(fh)) is not None:
        games.append(g)
    covered = rg.covered_positions(games)

    board = _board_after("e4", "Nc6", "Nf3")          # opponent (Black) to move
    fen = board.fen()
    lookup = _fake_lookup({fen: {"e7e5": 5, "g7g6": 3}})
    # Both are "strong" per masters; only the uncovered one may become a gap.
    masters = _fake_masters({fen: {"e7e5": 0.5, "g7g6": 0.2}})

    report = rg.analyze_node(board, covered=covered, reference_db="x",
                             lookup=lookup, masters=masters)
    st = _statuses(report)
    assert st["e7e5"] == COVERED      # transposition into the A line
    assert st["g7g6"] == GAP          # genuinely uncovered + strong


def test_masters_offline_marks_unverified():
    pgn = '[Event "R"]\n\n1. e4 e5 *\n'
    games = [chess.pgn.read_game(io.StringIO(pgn))]
    covered = rg.covered_positions(games)

    board = _board_after("e4")
    fen = board.fen()
    lookup = _fake_lookup({fen: {"e7e5": 10, "c7c5": 8}})
    masters = _fake_masters({})        # returns None for every fen -> offline

    report = rg.analyze_node(board, covered=covered, reference_db="x",
                             lookup=lookup, masters=masters)
    st = _statuses(report)
    assert st["e7e5"] == COVERED       # coverage does not need masters
    assert st["c7c5"] == UNVERIFIED    # uncovered, strength unknown
    assert report.masters_ok is False


def test_find_gaps_end_to_end(tmp_path):
    pgn = ('[Event "A"]\n\n1. e4 e5 2. Nf3 Nc6 *\n\n'
           '[Event "B"]\n\n1. e4 Nc6 2. Nf3 *\n')
    rep = tmp_path / "rep.pgn"
    rep.write_text(pgn, encoding="utf-8")

    bstub = _board_after("e4", "Nc6", "Nf3").fen()
    lookup = _fake_lookup({bstub: {"e7e5": 5, "g7g6": 3}})
    masters = _fake_masters({bstub: {"e7e5": 0.5, "g7g6": 0.2}})

    gaps = rg.find_gaps(str(rep), "x", user_color=True, lookup=lookup, masters=masters)
    assert len(gaps) == 1
    node = gaps[0]
    assert node.path_san == ["e4", "Nc6", "Nf3"]
    gap_ucis = {r.uci for r in node.report.gaps}
    assert gap_ucis == {"g7g6"}        # e5 is covered by transposition, not a gap


def test_root_opening_choice_is_not_a_gap(tmp_path):
    # Black Caro-Kann file: it answers only 1.e4. The opponent's FIRST move
    # (1.d4 etc.) is a choice of opening, not a gap in this file -> the root is
    # skipped. A deviation at White's 2nd move IS a gap.
    rep = tmp_path / "caro.pgn"
    rep.write_text('[Event "Caro"]\n\n1. e4 c6 2. d4 d5 *\n', encoding="utf-8")

    start = chess.Board().fen()
    after_e4c6 = _board_after("e4", "c6").fen()
    lookup = _fake_lookup({
        start: {"e2e4": 50, "d2d4": 30},          # 1.d4 faced but out of scope
        after_e4c6: {"d2d4": 20, "g1f3": 5},      # d4 covered, Nf3 not
    })
    masters = _fake_masters({
        start: {"e2e4": 0.5, "d2d4": 0.4},        # d4 is "strong" yet must NOT be a gap
        after_e4c6: {"d2d4": 0.5, "g1f3": 0.10},
    })

    gaps = rg.find_gaps(str(rep), "x", user_color=False, lookup=lookup, masters=masters)
    assert all(g.path_san for g in gaps)          # no gap at the root (empty path)
    assert len(gaps) == 1
    assert gaps[0].path_san == ["e4", "c6"]
    assert {r.uci for r in gaps[0].report.gaps} == {"g1f3"}


def test_start_move_pushes_the_threshold(tmp_path):
    # Same file; from move 3 on, White's 2nd-move deviation is no longer audited.
    rep = tmp_path / "caro.pgn"
    rep.write_text('[Event "Caro"]\n\n1. e4 c6 2. d4 d5 *\n', encoding="utf-8")
    after_e4c6 = _board_after("e4", "c6").fen()
    lookup = _fake_lookup({after_e4c6: {"d2d4": 20, "g1f3": 5}})
    masters = _fake_masters({after_e4c6: {"d2d4": 0.5, "g1f3": 0.10}})

    gaps = rg.find_gaps(str(rep), "x", user_color=False, start_move=3,
                        lookup=lookup, masters=masters)
    assert gaps == []                              # the move-2 node is below the threshold
