"""Makes chess moves contained in free text readable aloud.

Used before text-to-speech, so that tokens like 'Qe4' or 'Nxf3' are
read as 'Queen to e4' / 'Knight takes f3' instead of letter by letter.

`expand_moves_for_speech` is a pure function (no dependency on the speech
engine), so it is easily testable in isolation.
"""
from __future__ import annotations

import re

PIECE_NAMES = {
    "K": "King", "Q": "Queen", "R": "Rook", "B": "Bishop", "N": "Knight",
}

# Recognized SAN tokens (alternatives in order: longest/most specific first).
_CASTLE = r"O-O-O|O-O|0-0-0|0-0"
# piece + optional disambiguation + optional 'x' + destination square + check/mate
_PIECE_MOVE = r"[KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?"
# pawn capture (e.g. exd5), with optional promotion
_PAWN_CAPTURE = r"[a-h]x[a-h][1-8](?:=[QRBN])?[+#]?"
# pawn push promotion (e.g. e8=Q): the '=' makes it unambiguous
_PAWN_PROMO = r"[a-h][18]=[QRBN][+#]?"
# NB: "bare" pawn moves (e.g. 'e4') are NOT included on purpose:
# they are ambiguous with references to the square (e.g. "the e4 square is weak").

_MOVE_RE = re.compile(
    rf"\b(?:{_CASTLE}|{_PIECE_MOVE}|{_PAWN_CAPTURE}|{_PAWN_PROMO})"
)


def _expand_move(token: str) -> str:
    """Expands a single SAN move token into its spoken English form."""
    if token in ("O-O", "0-0"):
        return "castles kingside"
    if token in ("O-O-O", "0-0-0"):
        return "castles queenside"

    m = token
    suffix = ""
    if m.endswith("+"):
        m, suffix = m[:-1], " check"
    elif m.endswith("#"):
        m, suffix = m[:-1], " checkmate"

    promo = ""
    if "=" in m:
        m, _, pc = m.partition("=")
        promo = " promotes to " + PIECE_NAMES.get(pc, pc)

    capture = "x" in m
    m = m.replace("x", "")

    dest = m[-2:]          # the destination square is always the last file+rank
    head = m[:-2]          # piece letter and/or disambiguation

    parts: list[str] = []
    is_pawn = not (head and head[0] in PIECE_NAMES)
    if is_pawn:
        disamb = head      # e.g. the 'e' of 'exd5'
    else:
        parts.append(PIECE_NAMES[head[0]])
        disamb = head[1:]
    if disamb:
        parts.append(disamb)

    if capture:
        parts.append("takes")
    elif not is_pawn or disamb:
        # 'to' for piece moves; a "bare" pawn push never reaches here
        parts.append("to")
    parts.append(dest)

    return " ".join(parts) + promo + suffix


def expand_moves_for_speech(text: str) -> str:
    """Replaces every SAN move found in `text` with its spoken form.

    Examples: 'Qe4' -> 'Queen to e4', 'Nxf3' -> 'Knight takes f3',
    'exd5' -> 'e takes d5', 'O-O' -> 'castles kingside'.
    """
    if not text:
        return text
    return _MOVE_RE.sub(lambda mo: _expand_move(mo.group(0)), text)
