"""Statistiche di posizione contro un PGN di riferimento.

Costruisce in memoria un indice `zobrist_hash -> List[(white_result, next_move_uci)]`
sulla mainline di ogni partita del PGN configurato come "DB di riferimento"
(`config.reference_db`). Alla prima query l'indice viene costruito (~1-5s per
qualche migliaio di partite). Le query successive sulla stessa cache sono O(1).

POV: i risultati sono sempre **dal punto di vista del Bianco** (convenzione
classica dei DB scacchistici: W = vinta dal Bianco, D = patta, L = vinta dal
Nero). Per posizioni di mid-game con Nero al tratto, la statistica
side-to-move-relative si ricava banalmente invertendo i contatori.
"""
from __future__ import annotations

import os
import pickle
from collections import defaultdict
from typing import Optional, Callable

import chess
import chess.pgn
import chess.polyglot


# Cache in memoria: db_path -> (file_mtime_at_build, index_dict)
_cache: dict[str, tuple[float, dict]] = {}

# Versione del formato dei file `.idx` su disco. Incrementare se cambia lo
# schema delle entries (es. aggiunta di varianti, headers diversi).
_DISK_CACHE_VERSION = 1


def _index_cache_path(pgn_path: str) -> str:
    """Path al file di cache su disco accanto al PGN: `<pgn>.idx`."""
    return pgn_path + ".idx"


def _load_disk_cache(pgn_path: str) -> Optional[dict]:
    """Carica l'indice da disco se valido (mtime + size combaciano). None se
    assente, corrotto, o stale."""
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
        print(f"position_stats: cache load fallita ({cache_path}): {e}")
        return None


def _save_disk_cache(pgn_path: str, index: dict) -> None:
    """Salva l'indice accanto al PGN. Errori non bloccanti."""
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
        print(f"position_stats: cache save fallita ({cache_path}): {e}")


def _result_value(result_str: str) -> Optional[int]:
    """+1 vince Bianco, -1 vince Nero, 0 patta, None se sconosciuto/in corso."""
    return {"1-0": 1, "0-1": -1, "1/2-1/2": 0}.get(result_str)


def build_index(pgn_path: str, progress: Optional[Callable[[int], None]] = None) -> dict:
    """Scansiona il PGN e ritorna l'indice `zobrist -> List[(result, next_uci)]`.

    `result`: +1/-1/0/None come da _result_value (POV Bianco).
    `next_uci`: la mossa giocata immediatamente dopo quella posizione in QUELLA
    partita, o None se la partita finisce in quella posizione.
    `progress(n_games_processed)` callback opzionale per UI di avanzamento.
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
                # Walk mainline; per ogni nodo aggiungiamo (result, mossa successiva o None)
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
        print(f"position_stats: impossibile leggere {pgn_path}: {e}")
    if progress:
        progress(n_games)
    return dict(index)


def get_index(pgn_path: str, progress: Optional[Callable[[int], None]] = None) -> dict:
    """Restituisce l'indice. 3 livelli di cache:
    1. RAM (`_cache`) -- O(1) se la stessa sessione l'ha gia' caricato.
    2. Disco (`<pgn>.idx`) -- ~1-3s per PGN da 40k partite.
    3. Rebuild dal PGN -- ~10-15s per 40k partite.
    Il rebuild salva anche su disco per la prossima sessione.
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
    # Rebuild (e salva su disco)
    index = build_index(pgn_path, progress=progress)
    _cache[pgn_path] = (mtime, index)
    _save_disk_cache(pgn_path, index)
    return index


def invalidate_cache(pgn_path: Optional[str] = None) -> None:
    """Svuota la cache RAM (di un singolo PGN o tutta). NON tocca il file
    `.idx` su disco: e' protetto dal check mtime/size."""
    global _cache
    if pgn_path is None:
        _cache.clear()
    else:
        _cache.pop(pgn_path, None)


def lookup_position(pgn_path: str, board: chess.Board,
                    progress: Optional[Callable[[int], None]] = None) -> dict:
    """Restituisce le statistiche per la posizione.

    Struttura del dict ritornato:
    {
      'total':   int,                                 # occorrenze totali
      'results': {1: int, 0: int, -1: int, None: int},  # POV Bianco
      'moves':   {
          uci_str: {
              'count': int,
              'results': {1: int, 0: int, -1: int, None: int},
          },
          ...
      }
    }
    'moves' include solo le mosse continuative (la chiave `None` -> partita
    finita in quella posizione -- non inclusa).
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
