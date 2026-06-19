"""Pawn-structure signatures: the spine of the opening-ideas model.

A structure is identified by the configuration of the PAWNS alone. Open and
semi-open files are *derived* from it (a file with no pawn is open, with one
colour's pawn missing is semi-open), so they are never stored separately -- the
pawn placement already describes everything.

Two ideas drive the design:

* Colour inversion. The signature is colour-normalised: a structure and its
  colours-reversed twin (e.g. "a Queen's Gambit Declined with reversed colours")
  map to the SAME signature. `orientation()` tells you which face you are on, so
  the plans can be shown with the correct side.

* Forward derivation. Pawns only ever advance, capture sideways, or vanish --
  never retreat and never reappear. So structures form a forward order:
  `can_derive(a, b)` is True when b can plausibly arise from a by legal pawn
  motion. This is the approximate ("mezza idea") backbone for inheriting ideas
  between structures and for move-order steering.

`files` restricts the signature to a set of file indices (0=a .. 7=h). It
defaults to the global `STRUCTURE_FILES` (c-f); pass an explicit set only for
analysis/tests. Pass `ALL_FILES` for the exact pawn placement.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

import chess

# (colour, file, rank): colour is +1 White / -1 Black; file/rank are 0..7.
Pawn = Tuple[int, int, int]

# Handy presets for the `files` granularity knob.
CENTRE_DE = frozenset({3, 4})           # d, e -- the bare central identity
CENTRE_CF = frozenset({2, 3, 4, 5})     # c, d, e, f -- centre + inner flanks
ALL_FILES = frozenset(range(8))         # every file (exact structure)

# THE global granularity: which files define a structure's identity, for every
# position. Decided c-f -- c = queenside plan, d/e = centre, f = the ...f5/f4
# break; the true flanks (a, b, g, h) and the pieces live at the POSITION level.
# It must be a single global choice: the file-set is part of the key that
# identifies a structure, so it cannot itself depend on the structure.
STRUCTURE_FILES = CENTRE_CF


def _raw_pawns(board: chess.Board, files: Optional[Iterable[int]] = None) -> List[Pawn]:
    fset = None if files is None else frozenset(files)
    out: List[Pawn] = []
    for colour, chess_colour in ((1, chess.WHITE), (-1, chess.BLACK)):
        for sq in board.pieces(chess.PAWN, chess_colour):
            f, r = chess.square_file(sq), chess.square_rank(sq)
            if fset is None or f in fset:
                out.append((colour, f, r))
    return out


def _mirror(pawns: Iterable[Pawn]) -> List[Pawn]:
    """Colours-reversed twin: swap colour and flip the rank (board.mirror())."""
    return [(-c, f, 7 - r) for (c, f, r) in pawns]


def _canon(pawns: Iterable[Pawn]) -> Tuple[Pawn, ...]:
    a = tuple(sorted(pawns))
    b = tuple(sorted(_mirror(pawns)))
    return min(a, b)


def signature(board: chess.Board, files: Optional[Iterable[int]] = None) -> Tuple[Pawn, ...]:
    """Colour-normalised pawn signature (hashable). Equal signatures == same
    structure family, reversed colours included. Uses the global STRUCTURE_FILES
    (c-f) unless `files` is given."""
    if files is None:
        files = STRUCTURE_FILES
    return _canon(_raw_pawns(board, files))


def raw_signature(board: chess.Board, files: Optional[Iterable[int]] = None) -> Tuple[Pawn, ...]:
    """Colour-TRUE pawn signature (NO mirror folding). Use it to match a concrete
    target where the two sides must not be swapped -- e.g. mining a side's plans,
    where folding the colours-reversed twin would mix White's and Black's plans."""
    if files is None:
        files = STRUCTURE_FILES
    return tuple(sorted(_raw_pawns(board, files)))


def orientation(board: chess.Board, files: Optional[Iterable[int]] = None) -> int:
    """+1 if the board matches its canonical signature as-is, -1 if it matches
    via the colours-reversed twin (so callers can swap the sides of the plans)."""
    if files is None:
        files = STRUCTURE_FILES
    pawns = _raw_pawns(board, files)
    return 1 if tuple(sorted(pawns)) <= tuple(sorted(_mirror(pawns))) else -1


def _reachable(colour: int, frm: Tuple[int, int], to: Tuple[int, int]) -> bool:
    """Can a `colour` pawn on `frm` (file,rank) reach `to` by forward moves and
    sideways captures? Each file shift needs one rank of advance (a capture)."""
    df = abs(to[0] - frm[0])
    dr = (to[1] - frm[1]) if colour == 1 else (frm[1] - to[1])
    return dr >= 0 and df <= dr


def _matches_all(to_list, from_list, reachable) -> bool:
    """True if every 'to' pawn can be matched to a DISTINCT 'from' pawn that can
    reach it (bipartite matching via augmenting paths; <=8 pawns, trivial)."""
    match_from = [-1] * len(from_list)   # from index -> to index

    def assign(ti: int, seen: List[bool]) -> bool:
        for fi, fp in enumerate(from_list):
            if not seen[fi] and reachable(fp, to_list[ti]):
                seen[fi] = True
                if match_from[fi] == -1 or assign(match_from[fi], seen):
                    match_from[fi] = ti
                    return True
        return False

    for ti in range(len(to_list)):
        if not assign(ti, [False] * len(from_list)):
            return False
    return True


def can_derive(board_from: chess.Board, board_to: chess.Board,
               files: Optional[Iterable[int]] = None) -> bool:
    """True if `board_to`'s pawn structure can plausibly arise from
    `board_from`'s by legal pawn motion (forward-only; capture budget is NOT
    checked -- the deliberate approximation). Directional: A->B does not imply
    B->A."""
    if files is None:
        files = STRUCTURE_FILES
    pf, pt = _raw_pawns(board_from, files), _raw_pawns(board_to, files)
    for colour in (1, -1):
        frm = [(f, r) for (c, f, r) in pf if c == colour]
        to = [(f, r) for (c, f, r) in pt if c == colour]
        if len(to) > len(frm):
            return False
        if not _matches_all(to, frm, lambda a, b, col=colour: _reachable(col, a, b)):
            return False
    return True
