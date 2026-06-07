"""Verify that Stockfish is actually reading the Syzygy TB with the current config.

Open the engine with `engine_open()` (same pipeline as the program), analyze a
3-5 piece position and a 6 piece one, and read `tbhits` from the InfoDict. If `tbhits>0`
the folder for that generation is active.
"""
from __future__ import annotations

import chess
import chess.engine

import UCIEngines
from config import config


POSITIONS = [
    # (FEN, description, expected generation)
    ("4k3/8/8/8/8/8/8/3QK3 w - - 0 1", "KQvK", "3-5"),
    ("8/8/8/8/3k4/8/4P3/4K3 w - - 0 1", "KPvK (5-piece via moves)", "3-5"),
    ("4k3/8/3p4/8/8/8/3PP3/4K3 w - - 0 1", "KPPvKP (5 pieces)", "3-5"),
    ("8/8/8/8/3k4/8/4P3/R3K3 w - - 0 1", "KRPvK (4 pieces)", "3-5"),
    # A 6-piece one
    ("4k3/8/8/3P4/8/8/3PP3/4K3 w - - 0 1", "KPPPvK (5 pieces)", "3-5"),
    ("4k3/8/8/3pP3/8/8/3PP3/R3K3 w - - 0 1", "KRPPvKP (6 pieces)", "6"),
]


def main() -> int:
    print(f"SyzygyPath in config: {config.engine_options.get('SyzygyPath','<empty>')!r}")
    print(f"Engine configured: {config.engine!r}")
    print()

    UCIEngines.engine_open()
    eng = UCIEngines.engine
    if eng is None:
        print("ERROR: engine not open")
        return 1

    try:
        # A short analysis like 'depth 12' is more than enough to register tbhits.
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
