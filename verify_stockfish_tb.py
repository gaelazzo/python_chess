"""Verifica che Stockfish stia davvero leggendo le Syzygy TB con la config attuale.

Apre il motore con `engine_open()` (stessa pipeline del programma), analizza una
posizione 3-5 pezzi e una 6 pezzi, e legge `tbhits` dalle InfoDict. Se `tbhits>0`
la cartella per quella generazione e' attiva.
"""
from __future__ import annotations

import chess
import chess.engine

import UCIEngines
from config import config


POSITIONS = [
    # (FEN, descrizione, generazione attesa)
    ("4k3/8/8/8/8/8/8/3QK3 w - - 0 1", "KQvK", "3-5"),
    ("8/8/8/8/3k4/8/4P3/4K3 w - - 0 1", "KPvK (5-piece via mosse)", "3-5"),
    ("4k3/8/3p4/8/8/8/3PP3/4K3 w - - 0 1", "KPPvKP (5 pezzi)", "3-5"),
    ("8/8/8/8/3k4/8/4P3/R3K3 w - - 0 1", "KRPvK (4 pezzi)", "3-5"),
    # Una 6-piece
    ("4k3/8/8/3P4/8/8/3PP3/4K3 w - - 0 1", "KPPPvK (5 pezzi)", "3-5"),
    ("4k3/8/8/3pP3/8/8/3PP3/R3K3 w - - 0 1", "KRPPvKP (6 pezzi)", "6"),
]


def main() -> int:
    print(f"SyzygyPath in config: {config.engine_options.get('SyzygyPath','<vuoto>')!r}")
    print(f"Engine configurato: {config.engine!r}")
    print()

    UCIEngines.engine_open()
    eng = UCIEngines.engine
    if eng is None:
        print("ERROR: motore non aperto")
        return 1

    try:
        # Una breve analisi tipo 'depth 12' e' piu' che sufficiente per registrare tbhits.
        for fen, desc, gen in POSITIONS:
            board = chess.Board(fen)
            info = eng.analyse(board, chess.engine.Limit(depth=12), info=chess.engine.INFO_ALL)
            tbhits = info.get("tbhits", 0)
            score = info.get("score")
            depth = info.get("depth", "?")
            status = "OK " if tbhits > 0 else "ZERO"
            print(f"  [{status}] {desc:32s} (gen {gen}): tbhits={tbhits} depth={depth} score={score}")
    finally:
        UCIEngines.engine_close() if hasattr(UCIEngines, "engine_close") else eng.quit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
