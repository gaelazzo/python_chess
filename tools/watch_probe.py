"""Reproduce the watch pipeline in the terminal, to debug move tracking.

Run it (with the venv active) while the chess board you want to follow is on
screen at the START position:

    env\\Scripts\\python.exe tools\\watch_probe.py

1) Press Enter -> it locates + calibrates the board and prints the FEN (should
   be the start position).
2) MAKE A MOVE on that board, then press Enter -> it re-reads the SAME region
   and prints the new FEN and whether it matched a legal move.
3) Repeat step 2 for a few moves; type q + Enter to quit.

If a move isn't matched, it prints how many squares the closest legal move
differs by -- that tells us if it's the last-move highlight / noise, and how much
tolerance the matcher needs. Paste the whole output here. It also saves
probe_start.png and probe_moveN.png so we can see what it read.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import ImageGrab
import chess

import board_vision as bv
import board_watch as bw


def grab(region=None):
    shot = ImageGrab.grab(all_screens=True)
    return shot.crop(region) if region else shot


print("Aim at the board in the START position, then press Enter...")
input()
shot = ImageGrab.grab(all_screens=True)
# same chain as the in-app watch: locate, occupancy snap, pixel-exact grid pin
region = bv.find_board(shot)
region = bv.snap_to_startpos(shot, region)
region = bv.refine_start_grid(shot, region)
crop = shot.crop(region)
crop.save("probe_start.png")
prof = bv.calibrate_profile(crop, trim=False)
board = bv.recognize_board(crop, prof, white_bottom=prof.white_bottom, trim=False)
start_ok = board.board_fen() == chess.Board().board_fen()
print(f"board at {region}  white_bottom={prof.white_bottom}")
print(f"start FEN: {board.board_fen()}   start position? {'YES' if start_ok else 'NO'}")

tracked = chess.Board()
n = 0
while True:
    print("\nMake a move on the board, then press Enter (q + Enter to quit)...")
    if input().strip().lower() == "q":
        break
    n += 1
    crop = grab(region)
    crop.save(f"probe_move{n}.png")
    seen = bv.recognize_board(crop, prof, white_bottom=prof.white_bottom, trim=False)
    print(f"read FEN: {seen.board_fen()}")
    move = bw.match_move(tracked, seen.board_fen())
    if move is not None:
        print(f"  MATCHED legal move: {tracked.san(move)}  ({move.uci()})")
        tracked.push(move)
    else:
        best = None
        for m in tracked.legal_moves:
            tracked.push(m)
            d = sum(1 for sq in chess.SQUARES
                    if tracked.piece_at(sq) != seen.piece_at(sq))
            tracked.pop()
            if best is None or d < best[0]:
                best = (d, m)
        print(f"  NO exact match. closest legal move {tracked.san(best[1])} "
              f"differs by {best[0]} square(s) from what was read.")
        print(f"  (still tracking: {tracked.board_fen()})")
