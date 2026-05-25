"""Rende leggibili a voce le mosse di scacchi contenute in un testo libero.

Usato prima del text-to-speech, cosi' i token come 'Qe4' o 'Nxf3' vengono
letti come 'Queen to e4' / 'Knight takes f3' invece che lettera per lettera.

`expand_moves_for_speech` e' una funzione pura (nessuna dipendenza dal motore
vocale), quindi e' facilmente testabile in isolamento.
"""
from __future__ import annotations

import re

PIECE_NAMES = {
    "K": "King", "Q": "Queen", "R": "Rook", "B": "Bishop", "N": "Knight",
}

# Token SAN riconosciuti (alternative in ordine: prima le piu' lunghe/specifiche).
_CASTLE = r"O-O-O|O-O|0-0-0|0-0"
# pezzo + eventuale disambiguazione + eventuale 'x' + casa di arrivo + check/matto
_PIECE_MOVE = r"[KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?"
# cattura di pedone (es. exd5), con eventuale promozione
_PAWN_CAPTURE = r"[a-h]x[a-h][1-8](?:=[QRBN])?[+#]?"
# promozione di pedone in spinta (es. e8=Q): la '=' la rende inequivocabile
_PAWN_PROMO = r"[a-h][18]=[QRBN][+#]?"
# NB: le mosse di pedone "nude" (es. 'e4') NON sono incluse di proposito:
# sono ambigue con i riferimenti alla casa (es. "la casa e4 e' debole").

_MOVE_RE = re.compile(
    rf"\b(?:{_CASTLE}|{_PIECE_MOVE}|{_PAWN_CAPTURE}|{_PAWN_PROMO})"
)


def _expand_move(token: str) -> str:
    """Espande un singolo token-mossa SAN nella sua forma parlata in inglese."""
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

    dest = m[-2:]          # la casa di arrivo sono sempre gli ultimi file+riga
    head = m[:-2]          # lettera del pezzo e/o disambiguazione

    parts: list[str] = []
    is_pawn = not (head and head[0] in PIECE_NAMES)
    if is_pawn:
        disamb = head      # es. la 'e' di 'exd5'
    else:
        parts.append(PIECE_NAMES[head[0]])
        disamb = head[1:]
    if disamb:
        parts.append(disamb)

    if capture:
        parts.append("takes")
    elif not is_pawn or disamb:
        # 'to' per le mosse di pezzo; una spinta di pedone "nuda" non arriva qui
        parts.append("to")
    parts.append(dest)

    return " ".join(parts) + promo + suffix


def expand_moves_for_speech(text: str) -> str:
    """Sostituisce ogni mossa SAN trovata in `text` con la sua forma parlata.

    Esempi: 'Qe4' -> 'Queen to e4', 'Nxf3' -> 'Knight takes f3',
    'exd5' -> 'e takes d5', 'O-O' -> 'castles kingside'.
    """
    if not text:
        return text
    return _MOVE_RE.sub(lambda mo: _expand_move(mo.group(0)), text)
