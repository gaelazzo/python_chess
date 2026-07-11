"""Quick diagnostic for the live-board watch capture + localization.

Run it with a chessboard (ideally the START position) visible on ANY monitor:

    python tools/watch_diag.py

It grabs ALL screens, locates the board, and writes two images in the current
folder -- screen.png (what was captured) and found_board.png (what it located) --
and prints the recognized FEN. If found_board.png shows your board and the FEN is
the initial position, the in-app watch (press W in Analysis) will work here too.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import ImageGrab
import board_vision as bv

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"

shot = ImageGrab.grab(all_screens=True)
print(f"captured all screens: {shot.size[0]}x{shot.size[1]}")
shot.save("screen.png")
print("  wrote screen.png  (this is everything the watch sees)")

box = bv.find_board(shot)
print(f"find_board: ({box[0]}, {box[1]}) -> ({box[2]}, {box[3]})  side ~{box[2] - box[0]}px")
# same chain as the in-app watch: occupancy snap, then pixel-exact grid pin
box = bv.snap_to_startpos(shot, box)
left, top, right, bottom = bv.refine_start_grid(shot, box)
print(f"refined board at: ({left}, {top}) -> ({right}, {bottom})  side ~{right - left}px")
crop = shot.crop((left, top, right, bottom))
crop.save("found_board.png")
print("  wrote found_board.png  (check this is really your board, cropped tight)")

prof = bv.calibrate_profile(crop, trim=False)
print(f"orientation: {'white at bottom' if prof.white_bottom else 'white at top (flipped)'}")
fen = bv.recognize_board(crop, prof, white_bottom=prof.white_bottom,
                         trim=False).board_fen()
print(f"recognized position: {fen}")
print("is the start position? ", "YES -- watch is good to go" if fen == START
      else "NO -- aim at a board in the initial position (or found_board.png is wrong)")
