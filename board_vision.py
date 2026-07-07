"""board_vision.py -- read a chess position from an image of a 2D board.

Phase 1 (offline: no screen capture, no UI, no threads). Given a crop of an
8x8 *digital* board (lichess, chess.com, ChessBase 2D, ...), recognize the piece
placement and return a FEN.

Why this works without a trained model: digital boards render every piece
pixel-identically, so we do not need machine learning. We CALIBRATE once from a
single start-position image -- there the identity of every square is known (the
standard opening setup) -- capturing one full-tile template per (piece,
square-colour). Recognizing any later position is then a nearest-template match
per square, comparing only against templates of the SAME square colour. One
image per board theme is enough; there is no dataset to collect.

The start position does not show every piece on both square colours (e.g. the
white king only sits on a dark e1, the white queen only on a light d1). For each
piece seen on a single colour we SYNTHESIZE the missing-colour template: we
derive the piece's silhouette (pixels that differ from the empty square) and
composite it onto the empty square of the other colour. That keeps recognition a
clean same-colour, pixel-exact match -- no cross-colour approximation, and the
same trick shrugs off board theme changes.

Public API:
    calibrate_profile(start_image, white_bottom=True) -> Profile
    find_board(image) -> (left, top, right, bottom)     # locate the board in a screenshot
    detect_orientation(image, profile) -> bool          # True if White is at the bottom
    recognize_board(image, profile, ..., white_bottom=None) -> chess.Board
    image_to_fen(image, profile, ...) -> str
    read_screenshot(image, profile) -> (board, bbox, white_bottom)  # locate+orient+read

`image` is a PIL.Image (a path str is also accepted). recognize_board /
image_to_fen expect a crop of just the 8x8 board; find_board / read_screenshot
accept a full screenshot and locate the board themselves.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple, Union

import chess
import numpy as np
from PIL import Image

# Every tile is resampled to this size before matching, so tiles from images of
# different resolutions are directly comparable.
TILE = 32

# When splitting a square, ignore this fraction on each side and match only its
# centre. Pieces sit centred, so this drops the square borders where a few pixels
# of grid misalignment (screenshots vary in size / frame) would otherwise smear a
# piece across the boundary and wreck the match.
_INSET = 0.10

# A border row/column is "chrome" (frame or margin) when its pixels are nearly
# uniform; a real board line crosses 8 alternating squares, so its spread is high.
_UNIFORM_STD = 25.0   # below this = uniform line -> trim it
_MAX_TRIM = 0.15      # never trim more than this fraction of a side (safety)

# A pixel belongs to the piece (not the square) when it differs from the empty
# square by more than this, as squared L2 distance over RGB (0..255 per channel).
_INK_THRESHOLD = 1600  # ~40 per-channel

# find_board first searches a downscaled copy for speed; this is the target for
# its longest side. Big enough that each board cell keeps a sampleable background
# ring in the coarse pass; the coarse hit is then refined at full resolution.
_SEARCH_DOWNSCALE = 600

ImageLike = Union[str, Image.Image]
_Key = Tuple[str, str]  # (piece symbol or '.', square colour 'l'/'d')


@dataclass
class Profile:
    """A calibrated board theme: everything needed to read positions from it."""
    tile: int
    white_bottom: bool
    templates: Dict[_Key, np.ndarray]  # (symbol|'.', colour) -> mean full tile
    # Highlighted-square look, learned incrementally while watching a game (the
    # last-move tint carries no piece at calibration time, so this starts empty
    # and fills as moves are seen). Persisted with the profile so each reuse
    # starts richer -- both for reading pieces on highlighted squares and for
    # matching a move by its highlighted from/to squares.
    hl_templates: Dict[_Key, np.ndarray] = field(default_factory=dict)
    # Screen box (l, t, r, b) of the board at the last successful watch. Reuse
    # tries here first, so it can skip the slow full-screen search when the board
    # has not moved. None until a session has located it.
    last_region: tuple = None


def _as_image(img: ImageLike) -> Image.Image:
    return Image.open(img) if isinstance(img, str) else img


def _square_colour(sq: chess.Square) -> str:
    """'l' for a light square, 'd' for a dark one (a1 is dark)."""
    return "l" if (chess.square_file(sq) + chess.square_rank(sq)) % 2 else "d"


def _other(colour: str) -> str:
    return "d" if colour == "l" else "l"


def _screen_to_square(row: int, col: int, white_bottom: bool) -> chess.Square:
    """Map a screen tile (row 0 = top, col 0 = left) to a chess square.

    white_bottom=True is the usual orientation (White plays from the bottom);
    pass False for a board shown flipped (Black at the bottom).
    """
    if white_bottom:
        return chess.square(col, 7 - row)
    return chess.square(7 - col, row)


def _board_bbox(img: Image.Image) -> Tuple[int, int, int, int]:
    """Locate the 8x8 board inside `img`, trimming a uniform frame/margin.

    Screenshots wrap the board in a thin frame (and sometimes chrome) of varying
    thickness, and their overall size varies. Trimming the uniform border lines
    normalizes every image to the board itself, so the same chess square always
    lands in the same tile regardless of how the shot was cropped.
    """
    grey = np.asarray(img.convert("RGB"), dtype=np.float32).mean(axis=2)
    h, w = grey.shape

    def trim(n: int, line):
        limit = int(n * _MAX_TRIM)
        i = 0
        while i < limit and float(line(i).std()) < _UNIFORM_STD:
            i += 1
        return i

    left = trim(w, lambda i: grey[:, i])
    right = w - trim(w, lambda i: grey[:, w - 1 - i])
    top = trim(h, lambda i: grey[i, :])
    bottom = h - trim(h, lambda i: grey[h - 1 - i, :])
    return left, top, right, bottom


def _tiles(img: Image.Image, tile: int, trim: bool = True):
    """Yield (row, col, tile_array) for the 64 squares, top-left first.

    The board is first located inside the image (frame trimmed), then split into
    8x8. Only the centre of each square is sampled (see _INSET) and resampled to
    tile x tile so all tiles share one shape and small misalignments don't hurt.

    trim=False skips the per-image frame trim and treats the whole image as the
    board. The watch uses this: it fixes the tight board ONCE at setup, because
    re-trimming every frame is content-dependent (an overlay in a border strip
    changes the trim) and would shift the grid frame to frame.
    """
    img = img.convert("RGB")
    left, top, right, bottom = _board_bbox(img) if trim else (0, 0, img.width, img.height)
    bw, bh = right - left, bottom - top
    for r in range(8):
        for c in range(8):
            x0, x1 = left + c * bw / 8, left + (c + 1) * bw / 8
            y0, y1 = top + r * bh / 8, top + (r + 1) * bh / 8
            mx, my = (x1 - x0) * _INSET, (y1 - y0) * _INSET
            box = (round(x0 + mx), round(y0 + my), round(x1 - mx), round(y1 - my))
            crop = img.crop(box).resize((tile, tile))
            yield r, c, np.asarray(crop, dtype=np.float32)


def _composite(piece_tile: np.ndarray, from_empty: np.ndarray,
               onto_empty: np.ndarray) -> np.ndarray:
    """Move a piece from one square colour onto another.

    The silhouette is the set of pixels where `piece_tile` differs from the
    empty square it was captured on; those keep the piece's own colour, the rest
    take the destination empty square.
    """
    ink = np.sum((piece_tile - from_empty) ** 2, axis=2) > _INK_THRESHOLD
    return np.where(ink[..., None], piece_tile, onto_empty)


def _brighter_end(tiles) -> str:
    """Return 'bottom' or 'top' -- whichever end's pieces are lighter.

    In the start position both back ranks are full, and White's pieces are always
    lighter than Black's, so this tells White's side apart from a single image --
    no need to be told whether the board is shown flipped.
    """
    def end_luminance(rows):
        lums = []
        for row, _col, arr in tiles:
            if row in rows:
                grey = arr.mean(axis=2)
                bg = np.median(grey)
                ink = grey[np.abs(grey - bg) > 30]   # the piece, not the square
                if ink.size > 20:
                    lums.append(float(ink.mean()))
        return np.mean(lums) if lums else 0.0
    return "bottom" if end_luminance((6, 7)) >= end_luminance((0, 1)) else "top"


def calibrate_profile(start_image: ImageLike, white_bottom: bool = None,
                      tile: int = TILE) -> Profile:
    """Learn a board theme from ONE image of the standard start position.

    `white_bottom` may be left None: the orientation is then read from the image
    (the back rank with the lighter pieces is White's), so a board shown flipped
    calibrates correctly without being told.
    """
    tiles = list(_tiles(_as_image(start_image), tile))
    if white_bottom is None:
        white_bottom = _brighter_end(tiles) == "bottom"

    start = chess.Board()  # standard opening setup
    buckets: Dict[_Key, list] = {}
    for row, col, arr in tiles:
        sq = _screen_to_square(row, col, white_bottom)
        piece = start.piece_at(sq)
        sym = piece.symbol() if piece else "."
        buckets.setdefault((sym, _square_colour(sq)), []).append(arr)

    templates: Dict[_Key, np.ndarray] = {
        key: np.mean(arrs, axis=0) for key, arrs in buckets.items()
    }

    # Fill in the piece/colour pairs the opening setup never shows by
    # compositing the piece onto the empty square of the missing colour.
    empties = {c: templates.get((".", c)) for c in ("l", "d")}
    symbols = {sym for (sym, _c) in templates if sym != "."}
    for sym in symbols:
        for colour in ("l", "d"):
            if (sym, colour) in templates:
                continue
            other = _other(colour)
            src = templates.get((sym, other))
            if src is None or empties[colour] is None or empties[other] is None:
                continue
            templates[(sym, colour)] = _composite(src, empties[other], empties[colour])

    return Profile(tile=tile, white_bottom=white_bottom, templates=templates)


def _match_tile(arr: np.ndarray, mats: np.ndarray, syms, shift: int) -> str:
    """Nearest-template symbol for one tile, tolerant to a small (+/-`shift` px)
    misregistration.

    A rigid pixel-by-pixel compare (shift=0) collapses when the grid is a couple
    of px off: the piece then sits shifted inside its cell, so every pixel differs
    and the RIGHT template no longer wins -- this is what made whole back ranks
    read as garbage on a slightly mis-framed board. We instead take, per template,
    its BEST distance over a tiny shift window (the piece is the same, just nudged)
    and then the closest template. `shift=1` fixes it for ~free; larger only if the
    localization is really loose.
    """
    n = arr.shape[0]
    best = ((arr[None] - mats) ** 2).mean(axis=(1, 2, 3))     # shift (0,0)
    for dy in range(-shift, shift + 1):
        for dx in range(-shift, shift + 1):
            if dy == 0 and dx == 0:
                continue
            a = arr[max(0, dy):n + min(0, dy), max(0, dx):n + min(0, dx)]
            m = mats[:, max(0, -dy):n + min(0, -dy), max(0, -dx):n + min(0, -dx)]
            best = np.minimum(best, ((a[None] - m) ** 2).mean(axis=(1, 2, 3)))
    return syms[int(best.argmin())]


def recognize_board(image: ImageLike, profile: Profile,
                    side_to_move: chess.Color = chess.WHITE,
                    white_bottom: bool = None, extra: dict = None,
                    trim: bool = True, shift: int = 1) -> chess.Board:
    """Recognize the piece placement in `image` using a calibrated `profile`.

    `white_bottom` overrides the profile's orientation for this read (None keeps
    the profile default); pass detect_orientation()'s result to auto-orient.
    `extra` is an optional second template set (same (sym, colour) keys) matched
    alongside the profile's -- the watch feeds it live-learned HIGHLIGHTED-square
    templates, so a piece on a last-move square is read correctly.
    `shift` makes the per-square match tolerant to a few px of grid misalignment
    (see _match_tile); 0 restores the exact rigid compare.

    Note: an image only reveals piece placement. Side-to-move defaults to White
    and castling/en-passant are left empty -- the caller (the watch mode) fixes
    those from move context, not from a single frame.
    """
    wb = profile.white_bottom if white_bottom is None else white_bottom
    # Per-colour template stacks (profile + any extra highlighted-square set), so a
    # tile is compared against all candidates of its own square colour in one go.
    stacks: Dict[str, list] = {}
    for templates in (profile.templates, extra):
        if not templates:
            continue
        for (sym, colour), tmpl in templates.items():
            arrs, syms = stacks.setdefault(colour, ([], []))
            arrs.append(tmpl)
            syms.append(sym)
    stacks = {c: (np.stack(a), s) for c, (a, s) in stacks.items()}

    board = chess.Board.empty()
    for row, col, arr in _tiles(_as_image(image), profile.tile, trim=trim):
        sq = _screen_to_square(row, col, wb)
        stk = stacks.get(_square_colour(sq))
        if stk is None:
            continue
        sym = _match_tile(arr, stk[0], stk[1], shift)
        if sym != ".":
            board.set_piece_at(sq, chess.Piece.from_symbol(sym))

    board.turn = side_to_move
    return board


def tiles_by_square(image: ImageLike, profile: Profile, white_bottom: bool,
                    trim: bool = True) -> dict:
    """Map each chess square to its (resampled) tile array -- used to learn the
    appearance of specific squares (e.g. a highlighted last-move square)."""
    return {_screen_to_square(row, col, white_bottom): arr
            for row, col, arr in _tiles(_as_image(image), profile.tile, trim=trim)}


def image_to_fen(image: ImageLike, profile: Profile,
                 side_to_move: chess.Color = chess.WHITE,
                 white_bottom: bool = None) -> str:
    """Convenience wrapper: recognized position as a FEN string."""
    return recognize_board(image, profile, side_to_move, white_bottom).fen()


def _checker_score(grey: np.ndarray, side: float) -> float:
    """How much a square region looks like an 8x8 two-tone checker.

    Samples each cell near its corners (never its centre, where a piece sits), so
    pieces don't spoil the measure. High when the two square colours are distinct
    and each colour group is internally uniform -- i.e. a real board.
    """
    h, w = grey.shape
    c = side / 8.0
    means = np.empty((8, 8))
    for i in range(8):
        for j in range(8):
            vals = []
            for dx in (0.2, 0.8):
                for dy in (0.2, 0.8):
                    y, x = int((i + dy) * c), int((j + dx) * c)
                    if 0 <= y < h and 0 <= x < w:
                        vals.append(grey[y, x])
            means[i, j] = float(np.mean(vals)) if vals else 0.0
    parity = (np.indices((8, 8)).sum(0) & 1).astype(bool)
    a, b = means[~parity], means[parity]
    return abs(a.mean() - b.mean()) - 0.6 * (a.std() + b.std())


def _fit_axis(proj: np.ndarray, size0: int, start0: int,
              size_search: int, start_search: int) -> Tuple[int, int, float]:
    """Fit an 8-square grid to a 1-D edge projection; return (start, size, score).

    The 9 board lines are evenly spaced, so we pick the (start, size) that
    MAXIMIZES THE WEAKEST of all 9. Requiring every line -- the 7 internal
    boundaries AND the 2 outer edges -- to be strong pins offset and scale
    precisely: it rejects UI clutter (a stray strong edge can't fake nine evenly
    spaced ones) and, crucially, a grid shifted by one square, which would place
    an outer edge in empty surroundings where there is no line. `score` is that
    weakest-line strength (how confident the fit is).
    """
    n = len(proj)
    best = None
    for size in range(max(8, size0 - size_search), size0 + size_search + 1):
        span = size * 8
        for start in range(max(0, start0 - start_search), start0 + start_search + 1):
            if start + span >= n:   # the 9th line sits at start + span
                continue
            weakest = min(proj[start + k * size] for k in range(9))
            if best is None or weakest > best[0]:
                best = (weakest, start, size)
    return best[1], best[2], best[0]


def find_board(image: ImageLike) -> Tuple[int, int, int, int]:
    """Locate the chessboard inside a screenshot; return its (l, t, r, b) box.

    A board is the one square region with a clean 8x8 two-tone checker pattern,
    so a coarse search over a downscaled copy scores candidate windows by
    _checker_score to find it roughly. The exact edges are then pinned by fitting
    the 8x8 grid to the board's line structure (every square boundary is a
    full-height light<->dark transition -> 9 evenly-spaced edge peaks per axis),
    which locks offset and scale far tighter than the checker score can. Works on
    a full desktop capture as well as an already-cropped board.
    """
    img = _as_image(image).convert("RGB")
    w0, h0 = img.size
    f = max(1, round(max(w0, h0) / _SEARCH_DOWNSCALE))
    small = np.asarray(img.resize((w0 // f, h0 // f)).convert("L"), dtype=np.float64)
    h, w = small.shape
    integ = np.zeros((h + 1, w + 1))
    integ[1:, 1:] = small.cumsum(0).cumsum(1)

    # Coarse locate: score every candidate window by how much its 8x8 cells form
    # a two-tone checker, sampling each cell's BACKGROUND RING (the centre, where a
    # piece sits, is excluded). That way a board full of pieces still scores as a
    # board -- otherwise the pieces' variance sinks it below any clean two-tone
    # patch of UI. Vectorized over all window positions via the integral image.
    def win_box(oy, ox, bh, bw, ny, nx):
        return (integ[oy + bh: oy + bh + ny, ox + bw: ox + bw + nx]
                - integ[oy: oy + ny, ox + bw: ox + bw + nx]
                - integ[oy + bh: oy + bh + ny, ox: ox + nx]
                + integ[oy: oy + ny, ox: ox + nx])

    parity = (np.indices((8, 8)).sum(0) & 1).astype(bool)
    best = None
    for c in range(6, min(h, w) // 8 + 1):
        board = 8 * c
        ny, nx = h - board + 1, w - board + 1
        if ny <= 0 or nx <= 0:
            continue
        cs = max(1, c // 3)          # corner patch: a piece never reaches the corners
        means = np.empty((8, 8, ny, nx))
        for i in range(8):
            for j in range(8):
                oy, ox = i * c, j * c
                means[i, j] = (win_box(oy, ox, cs, cs, ny, nx)
                               + win_box(oy, ox + c - cs, cs, cs, ny, nx)
                               + win_box(oy + c - cs, ox, cs, cs, ny, nx)
                               + win_box(oy + c - cs, ox + c - cs, cs, cs, ny, nx)
                               ) / (4 * cs * cs)
        a, b = means[~parity], means[parity]
        score = np.abs(a.mean(0) - b.mean(0)) - 0.6 * (a.std(0) + b.std(0))
        yy, xx = np.unravel_index(int(np.argmax(score)), score.shape)
        if best is None or score[yy, xx] > best[0]:
            best = (float(score[yy, xx]), int(xx) * f, int(yy) * f, board * f)

    _, bx, by, bs = best

    # Lock onto the board at full resolution with the (piece-robust) checker
    # score before the grid snap -- this keeps us on the board and away from
    # surrounding UI, so the tight snap below never wanders onto it.
    grey = np.asarray(img.convert("L"), dtype=np.float64)
    hf, wf = grey.shape
    rng, step = 2 * f + 6, max(2, f // 3)
    refined = None
    for ds in range(-rng, rng + 1, step):
        s = bs + ds
        if s < 32:
            continue
        for dy in range(-rng, rng + 1, step):
            for dx in range(-rng, rng + 1, step):
                x, y = bx + dx, by + dy
                if x < 0 or y < 0 or x + s > wf or y + s > hf:
                    continue
                sc = _checker_score(grey[y:y + s, x:x + s], s)
                if refined is None or sc > refined[0]:
                    refined = (sc, x, y, s)
    _, bx, by, bs = refined

    # Precise edges: project edge energy in the approximate area and snap the grid
    # to the square boundaries (tight search, so it can only refine, not wander).
    pad = bs // 8
    x0, x1 = max(0, bx - pad), min(wf, bx + bs + pad)
    y0, y1 = max(0, by - pad), min(hf, by + bs + pad)
    sub = grey[y0:y1, x0:x1]
    v_proj = np.abs(np.diff(sub, axis=1)).sum(axis=0)   # vertical lines (over x)
    h_proj = np.abs(np.diff(sub, axis=0)).sum(axis=1)   # horizontal lines (over y)

    size0 = max(8, bs // 8)
    size_search, start_search = max(3, f), pad
    sx, wsz, scx = _fit_axis(v_proj, size0, bx - x0, size_search, start_search)
    sy, hsz, scy = _fit_axis(h_proj, size0, by - y0, size_search, start_search)

    # A board is SQUARE: if the two axes disagree on the square size, one was
    # fooled (e.g. a player bar above/below stretched the row fit). Trust the more
    # confident axis's size and re-fit the other axis's offset with it fixed.
    if wsz != hsz:
        if scx >= scy:
            size = wsz
            sy, _, _ = _fit_axis(h_proj, size, by - y0, 0, start_search)
        else:
            size = hsz
            sx, _, _ = _fit_axis(v_proj, size, bx - x0, 0, start_search)
    else:
        size = wsz
    left, top = x0 + sx, y0 + sy
    return left, top, left + 8 * size, top + 8 * size


def snap_to_startpos(image: ImageLike, box: Tuple[int, int, int, int]
                     ) -> Tuple[int, int, int, int]:
    """Nudge `box` so its 8x8 grid best matches a START position's OCCUPANCY --
    the two ranks at each end filled, the four middle ranks empty (symmetric, so
    orientation doesn't matter). Template-free: each cell counts as occupied when
    its centre differs from its corners (a piece), empty when it doesn't.

    Because a player bar / clock / coordinates above or beside the board do NOT
    have that pattern, maximizing the match pulls the box off them and onto the
    real board -- exactly where edge-projection fitting can drift. Use only at
    watch setup, when the board is known to be at the initial position.
    """
    grey = np.asarray(_as_image(image).convert("L"), dtype=np.float64)
    h, w = grey.shape
    l0, t0, r0, _b0 = box
    size0 = r0 - l0
    expected = [[(i in (0, 1, 6, 7)) for j in range(8)] for i in range(8)]

    def score(l, t, size):
        if l < 0 or t < 0 or l + size >= w or t + size >= h or size < 32:
            return -1
        c = size / 8.0
        hits = 0
        for i in range(8):
            for j in range(8):
                center = grey[int(t + (i + 0.5) * c), int(l + (j + 0.5) * c)]
                corners = (grey[int(t + (i + 0.2) * c), int(l + (j + 0.2) * c)]
                           + grey[int(t + (i + 0.2) * c), int(l + (j + 0.8) * c)]
                           + grey[int(t + (i + 0.8) * c), int(l + (j + 0.2) * c)]
                           + grey[int(t + (i + 0.8) * c), int(l + (j + 0.8) * c)]) / 4.0
                if (abs(center - corners) > 25) == expected[i][j]:
                    hits += 1
        return hits

    best = (score(l0, t0, size0), l0, t0, size0)
    off, dsz = size0 // 8, size0 // 12          # offset up to ~1 square, size ~±8%
    for step in (6, 1):                          # coarse then fine
        _, cl, ct, cs = best
        for dl in range(-off, off + 1, step):
            for dt in range(-off, off + 1, step):
                for ds in range(-dsz, dsz + 1, step):
                    s = score(cl + dl, ct + dt, cs + ds)
                    if s > best[0]:
                        best = (s, cl + dl, ct + dt, cs + ds)
        off, dsz = 5, 5                          # fine pass: small local search
    _, l, t, size = best
    return l, t, l + size, t + size


def snap_to_board(image: ImageLike, box: Tuple[int, int, int, int]
                  ) -> Tuple[int, int, int, int]:
    """Refine `box` to sit tight on the 8x8 board by hill-climbing the checker
    score (corner-sampled, piece-robust). Works for ANY position -- unlike
    snap_to_startpos, which needs the initial setup -- and pulls the box off an
    adjacent player bar / clock (not a checker). Use for mid-game tune-in."""
    grey = np.asarray(_as_image(image).convert("L"), dtype=np.float64)
    h, w = grey.shape
    l0, t0, r0, _b0 = box
    size0 = r0 - l0

    def score(l, t, size):
        if l < 0 or t < 0 or l + size >= w or t + size >= h or size < 32:
            return -1e9
        return _checker_score(grey[t:t + size, l:l + size], size)

    best = (score(l0, t0, size0), l0, t0, size0)
    off, dsz = size0 // 6, size0 // 10          # search up to ~1 rank of offset
    for step in (max(2, off // 6), 1):           # coarse then fine
        _, cl, ct, cs = best
        for dl in range(-off, off + 1, step):
            for dt in range(-off, off + 1, step):
                for ds in range(-dsz, dsz + 1, step):
                    s = score(cl + dl, ct + dt, cs + ds)
                    if s > best[0]:
                        best = (s, cl + dl, ct + dt, cs + ds)
        off, dsz = 5, 5
    _, l, t, size = best
    return l, t, l + size, t + size


def _plausibility(board: chess.Board) -> float:
    """Score how much a recognized position looks like a real one (higher=better).

    The key signal is the kings: White's king normally sits below Black's. Since
    piece COLOURS are known, this breaks the 180-degree flip ambiguity that a
    pawn-only check cannot (a rotation maps rank 2<->7, so pawn positions stay
    legal both ways). Pawns stranded on the back ranks are penalized too.
    """
    wk, bk = board.king(chess.WHITE), board.king(chess.BLACK)
    if wk is None or bk is None:
        return -100.0
    score = float(chess.square_rank(bk) - chess.square_rank(wk))
    for sq, piece in board.piece_map().items():
        if piece.piece_type == chess.PAWN and chess.square_rank(sq) in (0, 7):
            score -= 3.0
    return score


def detect_orientation(image: ImageLike, profile: Profile) -> bool:
    """Return True if the board is shown with White at the bottom.

    Reads the crop both ways and keeps the more plausible position (see
    _plausibility). Boards get flipped (e.g. shown from Black's side), so the
    watch mode calls this once to lock orientation before following moves.
    """
    both = [(_plausibility(recognize_board(image, profile, white_bottom=wb)), wb)
            for wb in (True, False)]
    both.sort(reverse=True)
    return both[0][1]


def read_screenshot(image: ImageLike, profile: Profile,
                    side_to_move: chess.Color = chess.WHITE):
    """Full pipeline: locate the board in a screenshot, orient it, read it.

    find_board pins the exact board edges (grid-line fit), so we read the located
    crop directly; recognize's _board_bbox still trims any thin frame.

    Returns (board, (l, t, r, b), white_bottom).
    """
    img = _as_image(image)
    left, top, right, bottom = find_board(img)
    crop = img.crop((left, top, right, bottom))
    white_bottom = detect_orientation(crop, profile)
    board = recognize_board(crop, profile, side_to_move, white_bottom=white_bottom)
    return board, (left, top, right, bottom), white_bottom


def save_profile(profile: Profile, path: str) -> None:
    """Persist a calibrated theme profile, so it can be reused later without
    pointing at a start position again (one profile per board theme)."""
    import os
    import pickle
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(profile, f)


def load_profile(path: str) -> Profile:
    """Load a profile saved by save_profile()."""
    import pickle
    with open(path, "rb") as f:
        prof = pickle.load(f)
    if getattr(prof, "hl_templates", None) is None:   # profile saved before this field
        prof.hl_templates = {}
    if not hasattr(prof, "last_region"):
        prof.last_region = None
    return prof


def highlighted_squares(image: ImageLike, profile: Profile, white_bottom: bool,
                        trim: bool = True) -> set:
    """Squares whose background is tinted vs the calibrated empty square: the last
    move's from/to squares (highlighted by chess.com and friends).

    Samples the TRUE square corners (where even a big piece never reaches) and
    compares their colour to the empty square's background colour. Returns {} if
    the result looks unreliable (nothing tinted, or too many squares tinted).
    """
    img = _as_image(image).convert("RGB")
    left, top, right, bottom = (_board_bbox(img) if trim
                                else (0, 0, img.width, img.height))
    arr = np.asarray(img, dtype=np.float64)
    bg = {c: np.median(profile.templates[(".", c)].reshape(-1, 3), axis=0)
          for c in ("l", "d") if (".", c) in profile.templates}

    cw, ch = (right - left) / 8.0, (bottom - top) / 8.0
    cs = max(2, int(min(cw, ch) * 0.16))       # small corner patch
    scores = {}
    for row in range(8):
        for col in range(8):
            sq = _screen_to_square(row, col, white_bottom)
            colour = _square_colour(sq)
            if colour not in bg:
                continue
            x0, y0 = left + col * cw, top + row * ch
            corners = []
            for px, py in ((x0, y0), (x0 + cw - cs, y0),
                           (x0, y0 + ch - cs), (x0 + cw - cs, y0 + ch - cs)):
                patch = arr[int(py):int(py) + cs, int(px):int(px) + cs]
                if patch.size:
                    corners.append(patch.reshape(-1, 3).mean(axis=0))
            if corners:
                scores[sq] = float(np.sum((np.mean(corners, axis=0) - bg[colour]) ** 2))

    if not scores:
        return set()
    median = sorted(scores.values())[len(scores) // 2]
    thresh = max(6.0 * median, 500.0)          # tint stands out clearly above bg noise
    flagged = {sq for sq, d in scores.items() if d > thresh}
    return flagged if len(flagged) <= 4 else set()   # >4 => not a clean last-move highlight


def highlighted_squares_learned(image: ImageLike, profile: Profile,
                                white_bottom: bool, trim: bool = True) -> set:
    """Squares that look highlighted (last-move tint), decided by the LEARNED
    highlighted-empty templates rather than a threshold guess.

    A square is highlighted when its centre tile is closer to the highlighted
    empty of its colour than to the normal empty. This is robust to a piece on
    the square: the discriminator is the BACKGROUND tint, which a centred piece
    does not cover, and -- crucially -- a low-contrast piece (the very case a
    plain read misses, e.g. a king that lands on a highlighted square and reads
    as empty) only makes the tile look MORE like the highlighted empty, so it is
    still flagged. Needs profile.hl_templates populated (learned from earlier
    moves); returns set() otherwise, or when the result looks unreliable.
    """
    hl = getattr(profile, "hl_templates", None) or {}
    pairs = {c: (profile.templates.get((".", c)), hl.get((".", c)))
             for c in ("l", "d")}
    if not any(n is not None and h is not None for n, h in pairs.values()):
        return set()
    found = set()
    for sq, tile in tiles_by_square(image, profile, white_bottom, trim).items():
        normal, highlighted = pairs[_square_colour(sq)]
        if normal is None or highlighted is None:
            continue
        sep = float(np.mean((normal - highlighted) ** 2))
        if sep < 25.0:
            continue                                  # empties too alike to tell them apart
        dn = float(np.mean((tile - normal) ** 2))
        dh = float(np.mean((tile - highlighted) ** 2))
        # Require a clear margin, scaled to how far apart the two empties are:
        # a highlighted background (empty or a low-contrast piece over it -- the
        # case that matters) gives dn - dh ~ sep, while a piece far from BOTH
        # empties gives only noise, which must NOT be mistaken for a tint.
        if dn - dh > 0.25 * sep:
            found.add(sq)
    # A clean last-move highlight is 2 squares (4 for a castle). Many more means
    # the classifier is over-firing on this frame -> treat as unreliable.
    return found if len(found) <= 5 else set()


def _infer_castling(board: chess.Board) -> int:
    """Castling-rights bitmask guessed from piece positions: a right is assumed
    present when the king AND the matching rook are on their home squares. We
    over-assume on purpose -- the real board never shows an illegal castle, but a
    missing right would block a legal one."""
    mask = 0
    if board.piece_at(chess.E1) == chess.Piece(chess.KING, chess.WHITE):
        if board.piece_at(chess.H1) == chess.Piece(chess.ROOK, chess.WHITE):
            mask |= chess.BB_H1
        if board.piece_at(chess.A1) == chess.Piece(chess.ROOK, chess.WHITE):
            mask |= chess.BB_A1
    if board.piece_at(chess.E8) == chess.Piece(chess.KING, chess.BLACK):
        if board.piece_at(chess.H8) == chess.Piece(chess.ROOK, chess.BLACK):
            mask |= chess.BB_H8
        if board.piece_at(chess.A8) == chess.Piece(chess.ROOK, chess.BLACK):
            mask |= chess.BB_A8
    return mask


def recognize_position(image: ImageLike, profile: Profile,
                       white_bottom: bool = None, trim: bool = True) -> chess.Board:
    """Full position from an image (for mid-game tune-in with a saved profile):
    placement PLUS side-to-move and castling rights inferred from the board.

    Side to move = the player who did NOT just move, i.e. NOT the colour sitting
    on the highlighted last-move square (none highlighted => White / start).
    Castling = assumed available unless the king/rook are off their home squares.
    `trim=False` when the crop is ALREADY the tight board (e.g. a framing pinned by
    read_with_profile): re-trimming an exact crop shifts the grid and wrecks a rank.
    """
    if white_bottom is None:
        white_bottom = detect_orientation(image, profile)
    board = recognize_board(image, profile, white_bottom=white_bottom, trim=trim)

    board.turn = chess.WHITE
    for sq in highlighted_squares(image, profile, white_bottom, trim=trim):
        piece = board.piece_at(sq)
        if piece is not None:                  # the highlighted 'to' square holds the mover
            board.turn = not piece.color
            break
    board.castling_rights = _infer_castling(board)
    return board


def _read_quality(board: chess.Board) -> float:
    """Score how much a recognized PLACEMENT looks like a real board -- used to
    pick the framing/orientation when reusing a profile. Exactly one king per side
    is required (a mis-framed read smears extra/duplicate kings), then White's king
    should sit below Black's (orientation), pawns must not sit on the back ranks,
    and neither side may show more than eight -- with a mild bonus for a fuller
    board (a well-framed one shows all its pieces; a misframe loses them)."""
    pm = board.piece_map()
    wk = [s for s, p in pm.items() if p.symbol() == "K"]
    bk = [s for s, p in pm.items() if p.symbol() == "k"]
    if len(wk) != 1 or len(bk) != 1:
        return -1e9
    score = float(chess.square_rank(bk[0]) - chess.square_rank(wk[0]))
    score -= 5.0 * sum(p.piece_type == chess.PAWN and chess.square_rank(s) in (0, 7)
                       for s, p in pm.items())
    for sym in ("P", "p"):
        score -= 3.0 * max(0, sum(p.symbol() == sym for p in pm.values()) - 8)
    score += 0.1 * len(pm)
    return score


def _residual_at(arr: np.ndarray, left: int, top: int, size: int,
                 tile: int, stacks: dict) -> float:
    """Mean best-match template distance over the 64 squares at a framing. Low = a
    crisp read (each piece squarely in its cell); high = misframed. ORIENTATION-
    INDEPENDENT (a square's colour is the same whichever way up the board is read),
    so it can pin the framing with a single orientation."""
    ih, iw = arr.shape[0], arr.shape[1]
    if left < 0 or top < 0 or left + size > iw or top + size > ih or size < 64:
        return 1e18
    sub = arr[top:top + size, left:left + size]
    cell = size / 8.0
    tot = 0.0
    for r in range(8):
        ys = np.linspace((r + _INSET) * cell, (r + 1 - _INSET) * cell - 1, tile).astype(int)
        for c in range(8):
            xs = np.linspace((c + _INSET) * cell, (c + 1 - _INSET) * cell - 1, tile).astype(int)
            st = stacks.get(_square_colour(_screen_to_square(r, c, True)))
            if st is None:
                continue
            tot += float(((sub[np.ix_(ys, xs)][None] - st) ** 2).mean(axis=(1, 2, 3)).min())
    return tot / 64.0


def _refine_framing(image: ImageLike, box: Tuple[int, int, int, int],
                    profile: Profile) -> Tuple[int, int, int, int]:
    """Pin the exact SQUARE board box by minimizing the read residual, via iterated
    global 1-D scans of left / top / size. find_board only gets within ~20-40px on
    a cluttered screen (a board wedged between UI panels + player bars); the grid
    lines alone don't nail it, but the residual has a clean minimum at the true
    framing, and 1-D global scans avoid the local optima a joint descent falls into.
    Orientation-independent, so we scan once."""
    arr = np.asarray(_as_image(image).convert("RGB"), dtype=np.float32)
    stacks = {c: np.stack([np.asarray(t, dtype=np.float32)
                           for (s, cc), t in profile.templates.items() if cc == c])
              for c in ("l", "d") if any(cc == c for (_s, cc) in profile.templates)}
    l, t, r, b = box
    # Scan the CENTRE and size, not the corner: resizing about the centre keeps the
    # board put, so the size scan is not fighting the offset (a corner scan gets
    # stuck a few px off, enough to flip a near-symmetric start's orientation).
    cx, cy, S = (l + r) // 2, (t + b) // 2, min(r - l, b - t)
    reach = max(30, S // 9)

    def resid(cx, cy, s):
        return _residual_at(arr, cx - s // 2, cy - s // 2, s, profile.tile, stacks)

    def scan(kind, lo, hi, step):
        cur = {"x": cx, "y": cy, "s": S}[kind]
        best = (resid(cx, cy, S), cur)
        for v in range(lo, hi, step):
            rr = resid(v if kind == "x" else cx,
                       v if kind == "y" else cy,
                       v if kind == "s" else S)
            if rr < best[0]:
                best = (rr, v)
        return best[1]

    # Coarse-to-fine: shrink the search window each pass so later passes are cheap.
    for step, frac in ((3, 1.0), (2, 0.4), (1, 0.15)):
        pr = max(6, int(reach * frac))
        sr = max(8, int(S * 0.13 * frac))
        cx = scan("x", cx - pr, cx + pr, step)
        cy = scan("y", cy - pr, cy + pr, step)
        S = scan("s", S - sr, S + sr, step)
    L, T = cx - S // 2, cy - S // 2
    return (L, T, L + S, T + S)


def read_with_profile(image: ImageLike, box: Tuple[int, int, int, int],
                      profile: Profile):
    """Locate + orient + read a board for MID-GAME reuse of a saved profile.

    Fast path: try cheap localizations of find_board's box (as-is, the two snaps),
    each frame-trimmed, and if one READS a sane position (one king a side, right
    way up; see _read_quality) keep the best. This handles boards find_board frames
    well. Slow path (only when none reads): the board is wedged in clutter and the
    box is tens of px off, so pin the exact framing by minimizing the read residual
    (_refine_framing), then take the orientation from plausibility. The read is
    shift-tolerant, so a couple of px is fine.

    Returns (board, (l, t, r, b), white_bottom), or (None, box, None) if nothing
    reads as a sane position.
    """
    img = _as_image(image).convert("RGB")
    l, t, r, b = box
    bx0, by0, bx1, by1 = _board_bbox(img.crop((l, t, r, b)))     # trim any frame/bar
    tight = (l + bx0, t + by0, l + bx1, t + by1)
    best = None                                        # (quality, board, tight, wb)
    if tight[2] - tight[0] >= 32 and tight[3] - tight[1] >= 32:
        crop = img.crop(tight)                          # already tight -> trim=False (no double-trim)
        for wb in (True, False):
            board = recognize_position(crop, profile, white_bottom=wb, trim=False)
            q = _read_quality(board)
            if best is None or q > best[0]:
                best = (q, board, tight, wb)

    if best is not None and best[0] > 0:               # find_board framed it well already
        return best[1], best[2], best[3]

    # Nothing framed cleanly -> pin the exact box by residual, then take the
    # orientation from the read (kings tell which way up; queens/pawns can't).
    tight = _refine_framing(img, box, profile)
    crop = img.crop(tight)
    refined = None
    for wb in (True, False):
        board = recognize_position(crop, profile, white_bottom=wb, trim=False)
        q = _read_quality(board)
        if refined is None or q > refined[0]:
            refined = (q, board, wb)
    if refined[0] > 0:
        return refined[1], tight, refined[2]
    if best is not None and best[0] > -1e8:            # fall back to best cheap read
        return best[1], best[2], best[3]
    return None, tuple(box), None


if __name__ == "__main__":  # tiny CLI for real screenshots
    import argparse

    ap = argparse.ArgumentParser(
        description="Calibrate a theme from a start-position screenshot, then read "
                    "a FEN from another screenshot of the same theme. Both may be "
                    "full-screen captures: the board is located automatically.")
    ap.add_argument("start_image", help="screenshot with the board in the start position")
    ap.add_argument("position_image", help="screenshot with the board to read")
    args = ap.parse_args()

    start_l, start_t, start_r, start_b = find_board(start_image := _as_image(args.start_image))
    prof = calibrate_profile(start_image.crop((start_l, start_t, start_r, start_b)))
    board, bbox, white_bottom = read_screenshot(args.position_image, prof)
    print(board.fen())
    print("board at %s, white_bottom=%s" % (bbox, white_bottom))
