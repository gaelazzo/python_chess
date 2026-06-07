"""Position statistics against a reference PGN.

Builds in memory an index `zobrist_hash -> List[(white_result, next_move_uci)]`
over the mainline of every game in the PGN configured as the "reference DB"
(`config.reference_db`). On the first query the index is built (~1-5s for
a few thousand games). Subsequent queries on the same cache are O(1).

POV: results are always **from White's point of view** (the classic
convention of chess DBs: W = won by White, D = draw, L = won by
Black). For mid-game positions with Black to move, the
side-to-move-relative statistic is trivially derived by swapping the counters.
"""
from __future__ import annotations

import os
import pickle
from collections import defaultdict
from typing import Optional, Callable

import chess
import chess.pgn
import chess.polyglot


# In-memory cache: db_path -> (file_mtime_at_build, index_dict)
_cache: dict[str, tuple[float, dict]] = {}

# Format version of the `.idx` files on disk. Increment it if the
# entries schema changes (e.g. adding variations, different headers).
_DISK_CACHE_VERSION = 1


def _index_cache_path(pgn_path: str) -> str:
    """Path to the on-disk cache file next to the PGN: `<pgn>.idx`."""
    return pgn_path + ".idx"


def _load_disk_cache(pgn_path: str) -> Optional[dict]:
    """Load the index from disk if valid (mtime + size match). None if
    absent, corrupted, or stale."""
    cache_path = _index_cache_path(pgn_path)
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "rb") as fh:
            data = pickle.load(fh)
        if not isinstance(data, dict):
            return None
        if data.get("version") != _DISK_CACHE_VERSION:
            return None
        if data.get("pgn_mtime") != os.path.getmtime(pgn_path):
            return None
        if data.get("pgn_size") != os.path.getsize(pgn_path):
            return None
        idx = data.get("index")
        return idx if isinstance(idx, dict) else None
    except Exception as e:
        print(f"position_stats: cache load failed ({cache_path}): {e}")
        return None


def _save_disk_cache(pgn_path: str, index: dict) -> None:
    """Save the index next to the PGN. Errors are non-blocking."""
    cache_path = _index_cache_path(pgn_path)
    try:
        with open(cache_path, "wb") as fh:
            pickle.dump(
                {
                    "version": _DISK_CACHE_VERSION,
                    "pgn_mtime": os.path.getmtime(pgn_path),
                    "pgn_size": os.path.getsize(pgn_path),
                    "index": index,
                },
                fh,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
    except Exception as e:
        print(f"position_stats: cache save failed ({cache_path}): {e}")


def _result_value(result_str: str) -> Optional[int]:
    """+1 White wins, -1 Black wins, 0 draw, None if unknown/in progress."""
    return {"1-0": 1, "0-1": -1, "1/2-1/2": 0}.get(result_str)


def build_index(pgn_path: str, progress: Optional[Callable[[int], None]] = None) -> dict:
    """Scan the PGN and return the index `zobrist -> List[(result, next_uci)]`.

    `result`: +1/-1/0/None as per _result_value (White POV).
    `next_uci`: the move played immediately after that position in THAT
    game, or None if the game ends in that position.
    `progress(n_games_processed)` optional callback for a progress UI.
    """
    index: dict[int, list] = defaultdict(list)
    if not pgn_path or not os.path.exists(pgn_path):
        return dict(index)
    n_games = 0
    try:
        with open(pgn_path, encoding="utf-8", errors="replace") as fh:
            while True:
                game = chess.pgn.read_game(fh)
                if game is None:
                    break
                n_games += 1
                if progress and (n_games % 50 == 0):
                    progress(n_games)
                result = _result_value(game.headers.get("Result", "*"))
                board = game.board()
                node = game
                # Walk mainline; for each node we add (result, next move or None)
                while True:
                    z = chess.polyglot.zobrist_hash(board)
                    nxt = node.next()
                    if nxt is None:
                        index[z].append((result, None))
                        break
                    index[z].append((result, nxt.move.uci()))
                    board.push(nxt.move)
                    node = nxt
    except OSError as e:
        print(f"position_stats: cannot read {pgn_path}: {e}")
    if progress:
        progress(n_games)
    return dict(index)


def get_index(pgn_path: str, progress: Optional[Callable[[int], None]] = None) -> dict:
    """Return the index. 3 cache levels:
    1. RAM (`_cache`) -- O(1) if the same session already loaded it.
    2. Disk (`<pgn>.idx`) -- ~1-3s for a 40k-game PGN.
    3. Rebuild from the PGN -- ~10-15s for 40k games.
    The rebuild also saves to disk for the next session.
    """
    if not pgn_path or not os.path.exists(pgn_path):
        return {}
    mtime = os.path.getmtime(pgn_path)
    cached = _cache.get(pgn_path)
    if cached and cached[0] == mtime:
        return cached[1]
    # Disk cache
    disk_index = _load_disk_cache(pgn_path)
    if disk_index is not None:
        _cache[pgn_path] = (mtime, disk_index)
        return disk_index
    # Rebuild (and save to disk)
    index = build_index(pgn_path, progress=progress)
    _cache[pgn_path] = (mtime, index)
    _save_disk_cache(pgn_path, index)
    return index


def invalidate_cache(pgn_path: Optional[str] = None) -> None:
    """Clear the RAM cache (for a single PGN or all of it). Does NOT touch the
    `.idx` file on disk: it is protected by the mtime/size check."""
    global _cache
    if pgn_path is None:
        _cache.clear()
    else:
        _cache.pop(pgn_path, None)


def lookup_position(pgn_path: str, board: chess.Board,
                    progress: Optional[Callable[[int], None]] = None) -> dict:
    """Return the statistics for the position.

    Structure of the returned dict:
    {
      'total':   int,                                 # total occurrences
      'results': {1: int, 0: int, -1: int, None: int},  # White POV
      'moves':   {
          uci_str: {
              'count': int,
              'results': {1: int, 0: int, -1: int, None: int},
          },
          ...
      }
    }
    'moves' includes only the continuation moves (the `None` key -> game
    ended in that position -- not included).
    """
    idx = get_index(pgn_path, progress=progress)
    z = chess.polyglot.zobrist_hash(board)
    entries = idx.get(z, [])

    results = {1: 0, 0: 0, -1: 0, None: 0}
    moves: dict[str, dict] = defaultdict(lambda: {
        "count": 0,
        "results": {1: 0, 0: 0, -1: 0, None: 0},
    })
    for result, next_uci in entries:
        results[result] += 1
        if next_uci is not None:
            moves[next_uci]["count"] += 1
            moves[next_uci]["results"][result] += 1
    return {
        "total": len(entries),
        "results": results,
        "moves": dict(moves),
    }
