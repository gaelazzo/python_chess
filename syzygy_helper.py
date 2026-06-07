"""Helper per usare le tablebase Syzygy dalla config del programma.

Espone una `Tablebase` di python-chess inizializzata lazy a partire da
`config.engine_options['SyzygyPath']` (stringa con i percorsi separati da `;`,
come quella che Stockfish stesso si aspetta su Windows). Le funzioni di probe
ritornano `None` se la TB non e' configurata o se la posizione e' fuori range,
cosi' il codice chiamante puo' fare fallback al motore senza eccezioni.
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
    """Percorsi Syzygy da config.json: splittati su `;`, filtrati per esistenza."""
    eo = config.engine_options
    raw = eo.get("SyzygyPath", "") if isinstance(eo, dict) else getattr(eo, "SyzygyPath", "")
    if not raw:
        return []
    parts = [p.strip() for p in str(raw).split(";") if p.strip()]
    return [p for p in parts if os.path.isdir(p)]


def open_tablebase() -> Optional[chess.syzygy.Tablebase]:
    """Apre la TB se non gia' aperta; None se nessuna cartella valida."""
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
    """Chiude la TB. Idempotente."""
    global _tablebase, _loaded_paths
    if _tablebase is not None:
        try:
            _tablebase.close()
        except Exception:
            pass
    _tablebase = None
    _loaded_paths = []


def reset_tablebase() -> None:
    """Forza la riapertura al prossimo open_tablebase (es. dopo cambio config)."""
    close_tablebase()


def get_loaded_paths() -> List[str]:
    return list(_loaded_paths)


def count_pieces(board: chess.Board) -> int:
    return chess.popcount(board.occupied)


def is_in_tb_range(board: chess.Board, max_pieces: int = 7) -> bool:
    """True se la posizione ha al massimo `max_pieces` pezzi totali (re inclusi)."""
    return count_pieces(board) <= max_pieces


def probe_wdl(board: chess.Board) -> Optional[int]:
    """WDL dal punto di vista del side-to-move (-2..+2), o None se non disponibile.

    Nota convenzione python-chess: la TB *non* gestisce posizioni con diritto di
    arrocco; il chiamante deve presentare una board senza castling rights se
    rilevante. Per le posizioni-finale tipiche (re gia' mossi) la cosa non si pone.
    """
    tb = open_tablebase()
    if tb is None or not is_in_tb_range(board):
        return None
    try:
        return tb.probe_wdl(board)
    except (chess.syzygy.MissingTableError, KeyError, IndexError):
        return None


def probe_dtz(board: chess.Board) -> Optional[int]:
    """DTZ (Distance-To-Zero, halfmoves) dal punto di vista del side-to-move,
    o None se non disponibile. Positivo = side-to-move vince; negativo = perde."""
    tb = open_tablebase()
    if tb is None or not is_in_tb_range(board):
        return None
    try:
        return tb.probe_dtz(board)
    except (chess.syzygy.MissingTableError, KeyError, IndexError):
        return None


def best_tb_move(board: chess.Board) -> Optional[chess.Move]:
    """Mossa TB-ottima per il side-to-move; None se TB indisponibile o nessuna
    mossa probabile.

    Strategia (semplice ma corretta per le esigenze del trainer):
    - Tra tutte le mosse legali, calcola (child_wdl, child_dtz) del figlio.
    - Sceglie il `child_wdl` minimo (avversario nello stato peggiore = noi al meglio).
    - Tiebreak: tra figli con stesso WDL, ordina per `child_dtz` DECRESCENTE.
      Funziona in entrambi i casi (intuizione DTZ python-chess):
        * vincente -> child_dtz < 0 (avversario perde); piu' vicino a 0 = mate
          piu' rapido per noi.
        * perdente -> child_dtz > 0 (avversario vince); piu' grande = vince piu'
          lentamente -> ci da' piu' tempo.
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
    """Restituisce il WDL post-mossa *dal punto di vista di chi ha mosso*, o
    None se fuori range / TB indisponibile.

    Convenzione python-chess: dopo la push e' il turno dell'altro lato; il probe
    sulla nuova board e' rispetto a quello, quindi va negato per ottenere il WDL
    dal nostro punto di vista.
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
