"""'Play from my opening book' for Play-vs-computer.

Loads a repertoire PGN once and answers, for any position, the moves the book
plays next there (transposition-aware via zobrist hash, so different move orders
that reach the same position share their continuations). The Play-vs-computer
loop consults it on the COMPUTER's turn: most of the time it plays a random book
continuation, occasionally (DEVIATION) it falls through to the engine for
unpredictability, and once the position is off-book it is the engine all the way.

Pure logic, no pygame: unit-testable offline.
"""
from __future__ import annotations

import os
import random
from typing import Dict, List, Optional

import chess
import chess.pgn
import chess.polyglot


# Chance the computer ignores an available book move and plays the engine
# instead -- "once in six it plays like the computer, not like the book".
DEVIATION = 1.0 / 6.0


def load_index(pgn_path: str) -> Dict[int, List[str]]:
    """Build ``zobrist(position) -> [book continuation uci, ...]`` over every game
    and variation in `pgn_path`. Empty dict if the file is missing/unreadable."""
    if not pgn_path or not os.path.exists(pgn_path):
        return {}
    acc: Dict[int, set] = {}
    try:
        with open(pgn_path, encoding="utf-8", errors="replace") as fh:
            while True:
                game = chess.pgn.read_game(fh)
                if game is None:
                    break
                _index_node(game, game.board(), acc)
    except OSError:
        return {}
    return {z: sorted(s) for z, s in acc.items()}


def _index_node(node, board: chess.Board, acc: Dict[int, set]) -> None:
    z = chess.polyglot.zobrist_hash(board)
    for child in node.variations:
        acc.setdefault(z, set()).add(child.move.uci())
        board.push(child.move)
        _index_node(child, board, acc)
        board.pop()


def load_index_for(filename: Optional[str]) -> Dict[int, List[str]]:
    """Resolve a repertoire file name (no extension) under the openings folder and
    load its index; ``{}`` when no file is chosen."""
    if not filename:
        return {}
    from modes.openings import OPENINGS_FOLDER
    return load_index(os.path.join(OPENINGS_FOLDER, filename + ".pgn"))


def book_continuations(index: Dict[int, List[str]], board: chess.Board) -> List[str]:
    """The book's LEGAL continuations (uci) for `board`, or [] if off-book. The
    legality filter guards against a (vanishingly rare) zobrist collision."""
    if not index:
        return []
    moves = index.get(chess.polyglot.zobrist_hash(board))
    if not moves:
        return []
    return [m for m in moves if chess.Move.from_uci(m) in board.legal_moves]


def book_move(index: Dict[int, List[str]], board: chess.Board) -> Optional[str]:
    """A random book continuation (uci) for `board`, or None when off-book OR a
    deviation is rolled (so the caller plays the engine instead)."""
    moves = book_continuations(index, board)
    if not moves:
        return None
    if random.random() < DEVIATION:
        return None
    return random.choice(moves)
