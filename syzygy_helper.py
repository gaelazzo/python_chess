"""Helper for using the Syzygy tablebases from the program config.

Exposes a python-chess `Tablebase` lazily initialized from
`config.engine_options['SyzygyPath']` (a string with the paths separated by `;`,
like the one Stockfish itself expects on Windows). The probe functions
return `None` if the TB is not configured or if the position is out of range,
so the calling code can fall back to the engine without exceptions.
"""
from __future__ import annotations

import os
from typing import List, Optional

import chess
import chess.syzygy

from config import config


_tablebase: Optional[chess.syzygy.Tablebase] = None
_loaded_paths: List[str] = []


def _get_syzygy_paths() -> List[str]:
    """Syzygy paths from config.json: split on `;`, filtered by existence."""
    eo = config.engine_options
    raw = eo.get("SyzygyPath", "") if isinstance(eo, dict) else getattr(eo, "SyzygyPath", "")
    if not raw:
        return []
    parts = [p.strip() for p in str(raw).split(";") if p.strip()]
    return [p for p in parts if os.path.isdir(p)]


def open_tablebase() -> Optional[chess.syzygy.Tablebase]:
    """Opens the TB if not already open; None if no valid directory."""
    global _tablebase, _loaded_paths
    if _tablebase is not None:
        return _tablebase
    paths = _get_syzygy_paths()
    if not paths:
        return None
    try:
        tb = chess.syzygy.open_tablebase(paths[0])
        for p in paths[1:]:
            tb.add_directory(p)
    except Exception as e:
        print(f"syzygy_helper: open_tablebase failed: {e}")
        return None
    _tablebase = tb
    _loaded_paths = list(paths)
    return tb


def close_tablebase() -> None:
    """Closes the TB. Idempotent."""
    global _tablebase, _loaded_paths
    if _tablebase is not None:
        try:
            _tablebase.close()
        except Exception:
            pass
    _tablebase = None
    _loaded_paths = []


def reset_tablebase() -> None:
    """Forces a reopen on the next open_tablebase (e.g. after a config change)."""
    close_tablebase()


def get_loaded_paths() -> List[str]:
    return list(_loaded_paths)


def count_pieces(board: chess.Board) -> int:
    return chess.popcount(board.occupied)


def is_in_tb_range(board: chess.Board, max_pieces: int = 7) -> bool:
    """True if the position has at most `max_pieces` total pieces (kings included)."""
    return count_pieces(board) <= max_pieces


def probe_wdl(board: chess.Board) -> Optional[int]:
    """WDL from the side-to-move's point of view (-2..+2), or None if unavailable.

    python-chess convention note: the TB does *not* handle positions with castling
    rights; the caller must provide a board without castling rights if
    relevant. For typical endgame positions (kings already moved) this does not arise.
    """
    tb = open_tablebase()
    if tb is None or not is_in_tb_range(board):
        return None
    try:
        return tb.probe_wdl(board)
    except (chess.syzygy.MissingTableError, KeyError, IndexError):
        return None


def probe_dtz(board: chess.Board) -> Optional[int]:
    """DTZ (Distance-To-Zero, halfmoves) from the side-to-move's point of view,
    or None if unavailable. Positive = side-to-move wins; negative = loses."""
    tb = open_tablebase()
    if tb is None or not is_in_tb_range(board):
        return None
    try:
        return tb.probe_dtz(board)
    except (chess.syzygy.MissingTableError, KeyError, IndexError):
        return None


def best_tb_move(board: chess.Board) -> Optional[chess.Move]:
    """TB-optimal move for the side-to-move; None if TB unavailable or no
    probable move.

    Strategy (simple but correct for the trainer's needs):
    - Among all legal moves, compute (child_wdl, child_dtz) of the child.
    - Picks the minimum `child_wdl` (opponent in the worst state = us at our best).
    - Tiebreak: among children with the same WDL, sort by `child_dtz` DESCENDING.
      Works in both cases (python-chess DTZ intuition):
        * winning -> child_dtz < 0 (opponent loses); closer to 0 = faster mate
          for us.
        * losing -> child_dtz > 0 (opponent wins); larger = wins more
          slowly -> gives us more time.
    """
    tb = open_tablebase()
    if tb is None or not is_in_tb_range(board):
        return None
    candidates: list[tuple[chess.Move, int, int]] = []
    for mv in board.legal_moves:
        nb = board.copy(stack=False)
        nb.push(mv)
        if not is_in_tb_range(nb):
            continue
        try:
            cwdl = tb.probe_wdl(nb)
            cdtz = tb.probe_dtz(nb)
        except (chess.syzygy.MissingTableError, KeyError, IndexError):
            continue
        candidates.append((mv, cwdl, cdtz))
    if not candidates:
        return None
    best_wdl = min(c[1] for c in candidates)
    best = [c for c in candidates if c[1] == best_wdl]
    best.sort(key=lambda c: c[2], reverse=True)
    return best[0][0]


def wdl_after_user_move(board_before: chess.Board, move: chess.Move) -> Optional[int]:
    """Returns the post-move WDL *from the point of view of whoever moved*, or
    None if out of range / TB unavailable.

    python-chess convention: after the push it is the other side's turn; the probe
    on the new board is relative to that, so it must be negated to obtain the WDL
    from our point of view.
    """
    tb = open_tablebase()
    if tb is None:
        return None
    nb = board_before.copy(stack=False)
    nb.push(move)
    if not is_in_tb_range(nb):
        return None
    try:
        child = tb.probe_wdl(nb)
    except (chess.syzygy.MissingTableError, KeyError, IndexError):
        return None
    return -child
