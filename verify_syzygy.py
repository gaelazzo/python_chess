"""Verify the integrity of the Syzygy tablebases in D:\\ChessBase\\Tablebases.

Two phases:
  1) Probe known positions (expected WDL) -> verify correctness of the results
  2) Stress test: for each .rtbw file, set up the material and probe -> catch
     corruption/parsing issues.
"""
from __future__ import annotations

import os
import sys
import traceback

import chess
import chess.syzygy

TB_345 = r"D:\ChessBase\Tablebases\345"
TB_6 = r"D:\ChessBase\Tablebases\6"

PIECE_FROM_LETTER = {
    'K': chess.KING, 'Q': chess.QUEEN, 'R': chess.ROOK,
    'B': chess.BISHOP, 'N': chess.KNIGHT, 'P': chess.PAWN,
}

# --- Phase 1: positions with known WDL -------------------------------------------------
KNOWN_POSITIONS = [
    ("4k3/8/8/8/8/8/8/3QK3 w - - 0 1", 2, "KQvK (Q wins)"),
    ("4k3/8/8/8/8/8/8/R3K3 w - - 0 1", 2, "KRvK (R wins)"),
    ("4k3/8/8/8/8/8/8/3BK3 w - - 0 1", 0, "KBvK (draw, insufficient material)"),
    ("4k3/8/8/8/8/8/8/3NK3 w - - 0 1", 0, "KNvK (draw, insufficient material)"),
    ("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1", 2, "KPvK (e-pawn, won)"),
    ("4k3/8/8/8/8/8/8/2BNK3 w - - 0 1", 2, "KBNvK (technical win)"),
    ("4k3/8/8/8/8/8/2B1B3/4K3 w - - 0 1", 0, "KBBvK same colour (draw)"),
    ("4k3/8/8/8/8/8/8/3RK2R w K - 0 1", 2, "KRRvK (easy win)"),
    ("4k3/8/8/8/3p4/8/4P3/4K3 w - - 0 1", 0, "KPvKP blocked pawns (draw-ish)"),
    ("4k3/8/8/8/8/8/PP6/4K3 w - - 0 1", 2, "KPPvK (two pawns)"),
]


def place_material(material_str: str, color: chess.Color, squares: list[int]):
    """Return a dict square -> Piece for the given material."""
    pieces = {}
    for letter in material_str:
        ptype = PIECE_FROM_LETTER[letter]
        # Pawns cannot be on rank 1 or 8 -- we place them separately
        if ptype == chess.PAWN:
            target_sq = next(
                s for s in squares if chess.square_rank(s) not in (0, 7)
            )
        else:
            target_sq = squares[0]
        squares.remove(target_sq)
        pieces[target_sq] = chess.Piece(ptype, color)
    return pieces


def board_from_filename(fname: str) -> chess.Board | None:
    """Build a legal board from the Syzygy file name (e.g. 'KQvKR')."""
    base = os.path.splitext(fname)[0]
    if 'v' not in base:
        return None
    white_str, black_str = base.split('v', 1)
    # Pool of squares (far from the kings to avoid accidental checks).
    white_squares = [chess.B4, chess.D4, chess.F4, chess.H4, chess.B2, chess.D2, chess.F2]
    black_squares = [chess.B6, chess.D6, chess.F6, chess.H6, chess.B7, chess.D7, chess.F7]
    board = chess.Board.empty()
    board.set_piece_at(chess.A1, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.A8, chess.Piece(chess.KING, chess.BLACK))
    try:
        white_str = white_str.replace('K', '', 1)
        black_str = black_str.replace('K', '', 1)
        for sq, piece in place_material(white_str, chess.WHITE, white_squares).items():
            board.set_piece_at(sq, piece)
        for sq, piece in place_material(black_str, chess.BLACK, black_squares).items():
            board.set_piece_at(sq, piece)
    except (StopIteration, IndexError):
        return None
    board.turn = chess.WHITE
    # Verify the position is legal: the king of the side not to move is not in check.
    if not board.is_valid():
        return None
    return board


def main() -> int:
    if not (os.path.isdir(TB_345) and os.path.isdir(TB_6)):
        print(f"ERROR: missing directory: {TB_345} or {TB_6}")
        return 2

    print(f"Opening tablebase: {TB_345} + {TB_6}")
    n_known_ok = 0
    n_known_bad = 0
    n_stress_ok = 0
    n_stress_skip = 0
    n_stress_err = 0
    errors_detail: list[tuple[str, str]] = []

    with chess.syzygy.open_tablebase(TB_345) as tb:
        tb.add_directory(TB_6)

        # --- Phase 1: known WDL ---
        print("\n[Phase 1] Probe positions with known WDL")
        for fen, expected, desc in KNOWN_POSITIONS:
            board = chess.Board(fen)
            try:
                wdl = tb.probe_wdl(board)
                ok = wdl == expected
                tag = "OK   " if ok else "BAD  "
                print(f"  [{tag}] {desc:42s} expected={expected:+d}  got={wdl:+d}")
                if ok:
                    n_known_ok += 1
                else:
                    n_known_bad += 1
                    errors_detail.append((desc, f"WDL expected={expected}, got={wdl}"))
            except Exception as e:
                print(f"  [ERR ] {desc:42s} {type(e).__name__}: {e}")
                n_known_bad += 1
                errors_detail.append((desc, f"{type(e).__name__}: {e}"))

        # --- Phase 2: stress test on all .rtbw files ---
        print("\n[Phase 2] Stress test: probe for each .rtbw file")
        all_files: list[str] = []
        for root in (TB_345, TB_6):
            for fn in os.listdir(root):
                if fn.endswith('.rtbw'):
                    all_files.append(fn)
        all_files.sort()
        print(f"  {len(all_files)} files to test")
        for i, fname in enumerate(all_files, 1):
            board = board_from_filename(fname)
            if board is None:
                n_stress_skip += 1
                continue
            try:
                tb.probe_wdl(board)
                # DTZ also uses the rtbz: test both
                tb.probe_dtz(board)
                n_stress_ok += 1
            except chess.syzygy.MissingTableError as e:
                # Missing file - but this should not happen given the inventory
                n_stress_err += 1
                errors_detail.append((fname, f"MissingTable: {e}"))
            except Exception as e:
                n_stress_err += 1
                errors_detail.append((fname, f"{type(e).__name__}: {e}"))
            if i % 100 == 0:
                print(f"    ...{i}/{len(all_files)} tested ({n_stress_err} errors so far)")

    print("\n=== SUMMARY ===")
    print(f"Phase 1 (known positions):    {n_known_ok} OK, {n_known_bad} failed")
    print(f"Phase 2 (stress on {len(all_files)} files): "
          f"{n_stress_ok} OK, {n_stress_skip} skipped, {n_stress_err} ERRORS")
    if errors_detail:
        print("\nError details:")
        for who, what in errors_detail[:50]:
            print(f"  - {who}: {what}")
        if len(errors_detail) > 50:
            print(f"  ... and {len(errors_detail) - 50} more")
    return 1 if (n_known_bad or n_stress_err) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(3)
