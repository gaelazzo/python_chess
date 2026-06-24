"""Repertoire gap analysis.

Find the **strong** opponent replies that occur in your OWN games but for which
your opening repertoire has no prepared answer. The aim is to avoid a useless
memory burden: weak one-off moves are ignored (you punish those over the board),
and only theory-grade replies are surfaced.

Definitions
-----------
* A *gap* lives at a node of the repertoire tree where it is the OPPONENT to
  move. A candidate opponent reply is a gap when ALL of:
    1. it actually occurred against you in the reference DB (your games),
    2. it is NOT covered by the repertoire -- where "covered" is checked on the
       RESULTING position (zobrist), not on the move, so move-order
       transpositions into a line you already have do not count as gaps,
    3. it is *strong*: masters play it above a share threshold.

The module is pure logic (no pygame). The two external dependencies -- the
games index (`position_stats.lookup_position`) and the masters strength check
(`lichess_plans.http_fetch`) -- are injected, so the analysis is unit-testable
offline with fakes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple, Iterator

import chess
import chess.pgn
import chess.polyglot

import position_stats
import lichess_plans


# --- tunables (easy to tweak in one place) --------------------------------
# A reply counts as "strong" if masters play it in at least this share of games
# at that position...
DEFAULT_MIN_SHARE = 0.05
# ...and only where masters have at least this many games (below that the
# position is essentially off-book and "strong" is not well defined).
DEFAULT_MIN_TOTAL = 50


# Reply classification.
COVERED = "covered"          # you already have an answer (direct or transposition)
GAP = "gap"                  # uncovered AND strong -> the one to act on
WEAK = "weak"                # uncovered but not strong enough -> ignore
UNVERIFIED = "unverified"    # uncovered, strength could not be checked (masters offline)


@dataclass
class Reply:
    """One opponent reply seen in your games at a repertoire node."""
    uci: str
    san: str
    games_count: int                  # occurrences in the reference DB
    results: Dict[Optional[int], int] # White-POV W/D/L counts for those games
    status: str                       # COVERED / GAP / WEAK / UNVERIFIED
    masters_share: Optional[float] = None  # share among masters, if known


@dataclass
class NodeReport:
    """Classification of every opponent reply at a single repertoire node."""
    fen: str
    replies: List[Reply] = field(default_factory=list)
    masters_ok: bool = True           # False if the masters lookup failed here

    @property
    def gaps(self) -> List[Reply]:
        return [r for r in self.replies if r.status == GAP]

    @property
    def has_gap(self) -> bool:
        return any(r.status == GAP for r in self.replies)


# --- repertoire loading ----------------------------------------------------

def load_repertoire(pgn_path: str) -> List[chess.pgn.Game]:
    """Read every game (root line) from a repertoire PGN. A repertoire file may
    hold several roots; each is a tree with the opponent's alternatives as
    variations."""
    games: List[chess.pgn.Game] = []
    with open(pgn_path, encoding="utf-8", errors="replace") as fh:
        while True:
            game = chess.pgn.read_game(fh)
            if game is None:
                break
            games.append(game)
    return games


def _walk(node: chess.pgn.GameNode) -> Iterator[chess.pgn.GameNode]:
    """Depth-first iteration over a game tree, every node (mainline + variations)."""
    yield node
    for child in node.variations:
        yield from _walk(child)


def covered_positions(games: List[chess.pgn.Game]) -> Set[int]:
    """Zobrist of every position present in the repertoire (across all roots and
    variations). Coverage is position-based on purpose: it makes the gap check
    immune to move-order transpositions for free."""
    covered: Set[int] = set()
    for game in games:
        for node in _walk(game):
            covered.add(chess.polyglot.zobrist_hash(node.board()))
    return covered


# --- strength (masters) ----------------------------------------------------

def masters_strong_ucis(fen: str, *,
                        fetch: Callable[[str], dict] = lichess_plans.http_fetch,
                        min_share: float = DEFAULT_MIN_SHARE,
                        min_total: int = DEFAULT_MIN_TOTAL) -> Optional[Dict[str, float]]:
    """{uci: share} for masters' replies above `min_share` at `fen`, or None if
    the lookup failed (no token / offline). Empty dict means masters reached the
    position but no reply clears the bar (or too few games)."""
    try:
        raw = fetch(fen)
    except Exception as e:               # network / token / parse
        print(f"repertoire_gaps: masters lookup failed for {fen}: {e}")
        return None
    nd = lichess_plans._node(raw)
    total = nd.get("total", 0)
    if total < min_total:
        return {}
    out: Dict[str, float] = {}
    for m in nd.get("moves", []):
        uci = m.get("uci")
        share = (m.get("games", 0) / total) if total else 0.0
        if uci and share >= min_share:
            out[uci] = share
    return out


# --- per-node analysis -----------------------------------------------------

def analyze_node(board: chess.Board, *,
                 covered: Set[int],
                 reference_db: str,
                 lookup: Callable = position_stats.lookup_position,
                 masters: Callable = masters_strong_ucis,
                 min_share: float = DEFAULT_MIN_SHARE,
                 min_total: int = DEFAULT_MIN_TOTAL) -> NodeReport:
    """Classify the opponent replies seen in your games at `board`.

    Call this ONLY on opponent-to-move positions (the caller knows the trained
    color). Masters are queried lazily here -- once per node, not per reply."""
    report = NodeReport(fen=board.fen())
    stats = lookup(reference_db, board)
    moves: Dict[str, dict] = stats.get("moves", {})
    if not moves:
        return report

    strong: Optional[Dict[str, float]] = None  # lazy: only query masters if needed
    queried = False

    # Most-played first, so the UI list reads naturally.
    for uci, info in sorted(moves.items(), key=lambda kv: -kv[1]["count"]):
        try:
            mv = chess.Move.from_uci(uci)
            san = board.san(mv)
        except Exception:
            mv, san = None, uci

        # Covered? -> resulting position already in the repertoire (transposition-safe).
        status = COVERED
        share = None
        if mv is not None:
            board.push(mv)
            is_covered = chess.polyglot.zobrist_hash(board) in covered
            board.pop()
        else:
            is_covered = False

        if not is_covered:
            if not queried:                 # one masters request per node, on demand
                strong = masters(board.fen(), min_share=min_share, min_total=min_total)
                queried = True
            if strong is None:
                status = UNVERIFIED
            elif uci in strong:
                status = GAP
                share = strong[uci]
            else:
                status = WEAK

        report.replies.append(Reply(
            uci=uci, san=san, games_count=info["count"],
            results=info.get("results", {}), status=status, masters_share=share,
        ))

    if queried and strong is None:
        report.masters_ok = False
    return report


# --- full sweep (tests / optional gap list) --------------------------------

@dataclass
class GapNode:
    """A repertoire node that has at least one strong gap, with the path to reach it."""
    fen: str
    path_san: List[str]          # SAN moves from the root to this node
    report: NodeReport


def iter_gap_nodes(repertoire_path: str, reference_db: str, *,
                   user_color: bool,
                   start_move: int = 1,
                   lookup: Callable = position_stats.lookup_position,
                   masters: Callable = masters_strong_ucis,
                   min_share: float = DEFAULT_MIN_SHARE,
                   min_total: int = DEFAULT_MIN_TOTAL,
                   on_visit: Optional[Callable[[str], None]] = None) -> Iterator[GapNode]:
    """Lazily walk the repertoire (DFS) and YIELD each node that has a strong gap,
    in tree order. Lazy on purpose: the UI's "next gap" pulls one at a time, so
    masters are queried only as far as the next gap (not the whole tree upfront).

    `user_color`: True if the user plays White -- the opponent (whose replies we
    audit) is to move when board.turn != user_color.
    `start_move`: only look for gaps from this full-move number on. The opening's
    defining moves are not gaps (a Caro-Kann file is not "missing" 1.d4); the user
    sets where their repertoire really starts branching. The root is always skipped
    regardless. Positions are de-duplicated by zobrist, so a transposition is
    reported once. `on_visit(fen)` fires on every opponent node examined (let the
    UI pump events / show a "searching" frame).
    """
    games = load_repertoire(repertoire_path)
    covered = covered_positions(games)
    seen: Set[int] = set()

    def visit(node: chess.pgn.GameNode, path: List[str]) -> Iterator[GapNode]:
        board = node.board()
        z = chess.polyglot.zobrist_hash(board)
        # A node is auditable only if it is opponent-to-move, not the root, at or
        # past `start_move`, and not an already-seen transposition.
        #  - Root skip: the opponent's first move is their CHOICE OF OPENING (which
        #    repertoire applies), never a gap in this file. `node.parent is None`
        #    only at a game root.
        #  - start_move: the opening's defining moves aren't gaps either; gaps are
        #    deviations once you are inside the repertoire. Transpositions back into
        #    scope are still caught deeper, since coverage is by resulting position.
        if (board.turn != user_color and node.parent is not None
                and board.fullmove_number >= start_move and z not in seen):
            seen.add(z)
            if on_visit is not None:
                on_visit(board.fen())
            report = analyze_node(board, covered=covered, reference_db=reference_db,
                                  lookup=lookup, masters=masters,
                                  min_share=min_share, min_total=min_total)
            if report.has_gap:
                yield GapNode(fen=board.fen(), path_san=list(path), report=report)
        for child in node.variations:
            yield from visit(child, path + [board.san(child.move)])

    for game in games:
        yield from visit(game, [])


def find_gaps(repertoire_path: str, reference_db: str, **kwargs) -> List[GapNode]:
    """Eager sweep: all gap nodes as a list (see `iter_gap_nodes` for the args)."""
    return list(iter_gap_nodes(repertoire_path, reference_db, **kwargs))
