"""Store of opening IDEAS / PLANS, keyed by the pawn-structure signature (c-f).

This is the AUTHORING backend. On the analysis board the user edits a structure's
dossier (plans, breaks, key squares, notes) and it is saved here, keyed by the
structure signature -- so one dossier is SHARED by every position, move order and
opening that reaches the same structure (no duplication). The miner's masters
suggestions live alongside, under "mined". Later the same data is shown read-only
while analysing or drilling openings.

File: data/opening_ideas.json  ->  { sig_key: {"dossier": {...}, "mined": {...},
                                               "fen_sample": "<a FEN of that structure>"} }

Pure backend: no pygame, no network -- unit-testable headless. The signature is
COLOUR-TRUE (raw_signature) for now, so White's and Black's plans never mix;
colour-inversion folding can be added later as an enhancement.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List

import chess

import pawn_structure as ps

# "main_idea" is the headline idea(s), shown with the chess "with the idea"
# triangle (△); the rest is the fuller dossier.
DOSSIER_FIELDS = ("main_idea", "character", "plans_white", "plans_black", "breaks", "key_squares", "notes")
LIST_FIELDS = ("main_idea", "plans_white", "plans_black", "breaks", "key_squares")


def _base_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DATA_FOLDER = os.path.join(_base_path(), "data")
STORE_PATH = os.path.join(DATA_FOLDER, "opening_ideas.json")

_store: Dict[str, dict] | None = None


def signature_key(board: chess.Board) -> str:
    """Stable string key from the colour-true c-f pawn signature."""
    return ";".join(f"{c}{f}{r}" for (c, f, r) in ps.raw_signature(board))


def structure_label(board: chess.Board) -> str:
    """Readable c-f skeleton, e.g. 'W: c2 d5 e4 f2   B: c7 d6 e5 f7'."""
    raw = ps.raw_signature(board)
    w = " ".join(chess.square_name(chess.square(f, r)) for (c, f, r) in raw if c == 1)
    b = " ".join(chess.square_name(chess.square(f, r)) for (c, f, r) in raw if c == -1)
    return f"W: {w or '-'}   B: {b or '-'}"


def _load() -> Dict[str, dict]:
    global _store
    if _store is None:
        try:
            with open(STORE_PATH, encoding="utf-8") as f:
                _store = json.load(f)
        except (OSError, ValueError):
            _store = {}
    return _store


def _save() -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(_load(), f, indent=2, ensure_ascii=False)


def reload() -> None:
    """Drop the in-memory cache (next access re-reads the file). For tests."""
    global _store
    _store = None


def get_dossier(board: chess.Board) -> dict:
    """The curated dossier for this structure (empty dict if none)."""
    return _load().get(signature_key(board), {}).get("dossier", {})


def set_dossier(board: chess.Board, dossier: dict) -> None:
    """Save/replace the curated dossier for this structure and persist."""
    store = _load()
    entry = store.setdefault(signature_key(board), {})
    entry["dossier"] = dossier
    entry.setdefault("fen_sample", board.fen())   # one concrete FEN, for reference
    _save()


def has_dossier(board: chess.Board) -> bool:
    return any(get_dossier(board).get(f) for f in DOSSIER_FIELDS)


def get_mined(board: chess.Board) -> dict:
    """The miner's masters suggestions for this structure (empty if none)."""
    return _load().get(signature_key(board), {}).get("mined", {})


def set_mined(board: chess.Board, mined: dict) -> None:
    store = _load()
    entry = store.setdefault(signature_key(board), {})
    entry["mined"] = mined
    entry.setdefault("fen_sample", board.fen())
    _save()


def dossier_lines(board: chess.Board) -> List[str]:
    """Render the dossier as display lines (for the read-only ideas panel)."""
    d = get_dossier(board)
    if not d:
        return []
    out: List[str] = []
    if d.get("main_idea"):
        out.append("△ " + ", ".join(d["main_idea"]))   # △ with the idea
    if d.get("character"):
        out.append(d["character"])
    for label, key in (("White:", "plans_white"), ("Black:", "plans_black"),
                       ("Breaks:", "breaks"), ("Keys:", "key_squares")):
        vals = d.get(key) or []
        if vals:
            out.append(f"{label} " + ", ".join(vals))
    if d.get("notes"):
        out.append(d["notes"].split("\n")[0])   # masters report can be long -> just its header line
    return out
