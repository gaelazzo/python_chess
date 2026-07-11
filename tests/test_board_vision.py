"""Prove Phase 1 of the board-vision pipeline WITHOUT any real screenshots.

We render 2D boards synthetically (a stand-in for a digital board that draws its
pieces pixel-identically), calibrate the profile from the START POSITION ONLY,
and check that arbitrary positions are then read back correctly -- including
positions with a piece on a square colour never seen at calibration time, and a
flipped (Black-at-the-bottom) board.
"""
import chess
import pytest
from PIL import Image, ImageDraw, ImageFont

import board_vision as bv

_LIGHT = (240, 217, 181)
_DARK = (181, 136, 99)


def _render(board: chess.Board, white_bottom: bool = True, tile: int = 48,
            highlight=()) -> Image.Image:
    """Render a board to an image the way a clean 2D board would: flat squares
    plus a per-piece glyph (letter = type, colour = side), drawn identically
    every time so the same piece is pixel-identical across squares.

    The glyph is large and centred so a piece fills most of its square, as real
    2D board sets do -- a tiny glyph would leave recognition dominated by the
    identical background and by anti-aliasing noise, which is not how real boards
    look. `highlight` = squares to tint (last-move highlight)."""
    font = ImageFont.load_default(size=int(tile * 0.8))
    img = Image.new("RGB", (tile * 8, tile * 8))
    draw = ImageDraw.Draw(img)
    for row in range(8):
        for col in range(8):
            sq = bv._screen_to_square(row, col, white_bottom)
            fill = _LIGHT if bv._square_colour(sq) == "l" else _DARK
            if sq in highlight:                       # yellow-tint the square background
                fill = tuple(int(0.55 * c + 0.45 * y) for c, y in zip(fill, (235, 220, 70)))
            draw.rectangle([col * tile, row * tile,
                            (col + 1) * tile - 1, (row + 1) * tile - 1], fill=fill)
            piece = board.piece_at(sq)
            if piece is not None:
                ink = (250, 250, 250) if piece.color == chess.WHITE else (12, 12, 12)
                # symbol() already encodes side by case; colour makes it unambiguous.
                draw.text((col * tile + tile / 2, row * tile + tile / 2),
                          piece.symbol(), fill=ink, font=font, anchor="mm")
    return img


# A spread of positions. The Scandinavian line parks the black queen and a white
# knight on square colours the start position never shows them on -- that is the
# cross-colour fallback the delta-from-empty matching has to get right.
_FENS = [
    chess.STARTING_FEN,
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",   # 1.e4 c5
    "rnb1kbnr/ppp1pppp/8/3q4/8/2N5/PPPP1PPP/R1BQKBNR w KQkq - 0 4",   # Scandinavian
    "8/8/4k3/8/2Q5/8/4K3/8 w - - 0 1",                                # sparse endgame
    "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 5",  # Italian
]


@pytest.fixture(scope="module")
def profile():
    # ONE image -> full calibration. This is the whole point: no dataset.
    return bv.calibrate_profile(_render(chess.Board()))


@pytest.mark.parametrize("fen", _FENS)
def test_reads_position_after_single_image_calibration(profile, fen):
    board = chess.Board(fen)
    got = bv.image_to_fen(_render(board), profile)
    assert got.split()[0] == board.board_fen()


def test_reads_flipped_board():
    """A board shown flipped (Black at the bottom) reads correctly when the
    profile is calibrated in that same orientation."""
    prof = bv.calibrate_profile(_render(chess.Board(), white_bottom=False),
                                white_bottom=False)
    board = chess.Board("rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
    got = bv.recognize_board(_render(board, white_bottom=False), prof)
    assert got.board_fen() == board.board_fen()


# A middlegame with the kings on their usual sides, so orientation is decidable.
_MIDGAME = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 5"


def _paste_on_canvas(board_img, at=(140, 70), canvas=(780, 520), bg=(28, 30, 33)):
    """Drop a rendered board onto a larger, uniform 'screenshot' background."""
    img = Image.new("RGB", canvas, bg)
    img.paste(board_img, at)
    box = (at[0], at[1], at[0] + board_img.width, at[1] + board_img.height)
    return img, box


def test_find_board_locates_board_in_a_screenshot():
    img, (l, t, r, b) = _paste_on_canvas(_render(chess.Board(_MIDGAME)))
    fl, ft, fr, fb = bv.find_board(img)
    side = r - l
    # centre within one square and side within 10% of the real board
    assert abs((fl + fr) / 2 - (l + r) / 2) < side / 8
    assert abs((ft + fb) / 2 - (t + b) / 2) < side / 8
    assert abs((fr - fl) - side) < 0.10 * side


@pytest.mark.parametrize("white_bottom", [True, False])
def test_detect_orientation(profile, white_bottom):
    crop = _render(chess.Board(_MIDGAME), white_bottom=white_bottom)
    assert bv.detect_orientation(crop, profile) == white_bottom


def test_read_screenshot_end_to_end(profile):
    """Locate + orient + read a board embedded in a full screenshot, both ways."""
    for white_bottom in (True, False):
        board = chess.Board(_MIDGAME)
        img, _ = _paste_on_canvas(_render(board, white_bottom=white_bottom))
        got, _bbox, wb = bv.read_screenshot(img, profile)
        assert wb == white_bottom
        assert got.board_fen() == board.board_fen()


def test_snap_to_board_pulls_off_a_bar():
    """A box that wrongly swallows a non-board bar above the board is pulled down
    onto the real board (checker-based, works at any position)."""
    board = _render(chess.Board(_MIDGAME))
    bar = 40
    canvas = Image.new("RGB", (board.width, board.height + bar), (28, 30, 33))
    canvas.paste(board, (0, bar))
    box = (0, 0, board.width, board.height)          # includes the bar, cuts the bottom
    l, t, r, b = bv.snap_to_board(canvas, box)
    assert t >= bar - 8                              # top moved down onto the board
    assert abs((r - l) - board.width) < board.width * 0.15


@pytest.mark.parametrize("dl,dt,dsize", [
    (11, -9, 14),      # the typical snap_to_startpos error: offset + wrong size
    (-8, 6, -20),      # short box (the template-ghosting case seen on wood themes)
    (48, 5, 0),        # a WHOLE cell off: the degenerate self-consistent shift
])
def test_refine_start_grid_recovers_misframed_box(dl, dt, dsize):
    """A calibration box that is off by a few px -- or even a whole square --
    must be pinned back onto the exact board. This is the regression for the
    ghost-template failure: snap_to_startpos' integer occupancy score saturates,
    the box it returns can be ~10 px off/short, and calibrating there smears
    every averaged template."""
    img, (l, t, r, b) = _paste_on_canvas(_render(chess.Board()))
    seed = (l + dl, t + dt, r + dl + dsize, b + dt + dsize)
    fl, ft, fr, fb = bv.refine_start_grid(img, seed)
    assert abs(fl - l) <= 2 and abs(ft - t) <= 2
    assert abs(fr - r) <= 2 and abs(fb - b) <= 2
    # ... and calibrating on the refined box (untrimmed: it is already exact)
    # yields a profile that reads the start position perfectly.
    crop = img.crop((fl, ft, fr, fb))
    prof = bv.calibrate_profile(crop, trim=False)
    got = bv.recognize_board(crop, prof, white_bottom=prof.white_bottom, trim=False)
    assert got.board_fen() == chess.Board().board_fen()


def test_profile_save_load_roundtrip(profile, tmp_path):
    path = str(tmp_path / "sub" / "theme.pkl")
    bv.save_profile(profile, path)
    reloaded = bv.load_profile(path)
    board = chess.Board(_MIDGAME)
    assert bv.image_to_fen(_render(board), reloaded).split()[0] == board.board_fen()


def test_recognize_position_turn_from_highlight(profile):
    board = chess.Board()
    board.push_san("e4")                      # White just moved -> Black to move
    img = _render(board, highlight=[chess.E2, chess.E4])
    pos = bv.recognize_position(img, profile, white_bottom=True)
    assert pos.board_fen() == board.board_fen()
    assert pos.turn == chess.BLACK


def test_recognize_position_no_highlight_is_white(profile):
    pos = bv.recognize_position(_render(chess.Board()), profile, white_bottom=True)
    assert pos.turn == chess.WHITE


def test_recognize_position_infers_castling(profile):
    # kings and rooks home -> all four rights assumed
    home = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1")
    pos = bv.recognize_position(_render(home), profile, white_bottom=True)
    assert pos.has_kingside_castling_rights(chess.WHITE)
    assert pos.has_queenside_castling_rights(chess.WHITE)
    assert pos.has_kingside_castling_rights(chess.BLACK)
    # white king off e1 -> no white rights (black still home -> keeps its rights)
    moved = chess.Board("r3k2r/8/8/8/8/8/8/R4RK1 w - - 0 1")
    pos2 = bv.recognize_position(_render(moved), profile, white_bottom=True)
    assert not pos2.has_kingside_castling_rights(chess.WHITE)
    assert pos2.has_kingside_castling_rights(chess.BLACK)


def test_refine_start_grid_recovers_a_misframed_box():
    """A seed box that is offset AND wrongly sized (the snap_to_startpos failure
    that ghosted every calibrated template on wood themes) is pinned back onto
    the exact board. The uniform background around the board is the trap: a grid
    shifted by a whole cell into it stays self-consistent, so this also proves
    the global anchoring."""
    img, (l, t, r, b) = _paste_on_canvas(_render(chess.Board()))
    for seed in [(l + 11, t - 9, r + 3, b - 17),     # offset + 5% short
                 (l - 40, t + 6, r - 52, b - 6)]:    # nearly a whole cell off
        fl, ft, fr, fb = bv.refine_start_grid(img, seed)
        assert abs(fl - l) <= 2 and abs(ft - t) <= 2
        assert abs(fr - r) <= 2 and abs(fb - b) <= 2


def test_refine_start_grid_calibration_reads_cleanly():
    """Calibrating on the refined box (trim=False, the exact-grid contract) must
    read the start position perfectly."""
    img, _ = _paste_on_canvas(_render(chess.Board()))
    box = bv.refine_start_grid(img, bv.snap_to_startpos(img, bv.find_board(img)))
    crop = img.crop(box)
    prof = bv.calibrate_profile(crop, trim=False)
    got = bv.recognize_board(crop, prof, white_bottom=prof.white_bottom, trim=False)
    assert got.board_fen() == chess.Board().board_fen()
