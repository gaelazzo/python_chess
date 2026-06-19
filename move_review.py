"""Coach-style review of a single played move.

The design separates two responsibilities so the verbal output can never be
"scacchisticamente" wrong:

  * a deterministic *facts* layer (`analyse_move`) that uses the engine and
    python-chess to produce ground-truth data about the move -- best move, eval
    before/after, win-percentage drop, centipawn loss, a Lichess-style verdict.
    No language model is involved here, so it cannot hallucinate moves or
    miscount material.
  * a *verbalization* layer that turns those facts into prose. The PRIMARY
    path is `verbalize_template` (deterministic, engine-grounded, no network).
    An LLM backend (`coach_llm`) is an OPTIONAL enhancement, off by default and
    enabled via `config.coach_use_llm`; it only *verbalizes* the same facts and
    falls back to the template on any problem.

The LLM backend is a standalone module, intentionally unrelated to BrainMaster
(courses / spaced repetition) -- the coach has its own concern.
"""
from __future__ import annotations

import math
from typing import Optional

import chess

from config import config


# --- Win-percentage model (Lichess) --------------------------------------
# Maps a centipawn score (mover's point of view) to a 0..100 winning chance.
# This is what move quality should be judged on: losing 1.00 at a dead-even
# position matters far more than losing 1.00 when already +6.
_WIN_K = 0.00368208
MATE_CP = 10000          # centipawn stand-in for a forced mate, for the model
PV_LEN = 5               # plies of the engine's best line we keep for context


def win_percent(cp: int) -> float:
    """Winning chance (0..100) for the side to move, from a centipawn score."""
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-_WIN_K * cp)) - 1.0)


# --- Verdict thresholds (drop in win-percentage points) -------------------
# Tunable: these mirror the common annotation bands (?!, ?, ??).
INACCURACY = 10.0
MISTAKE = 20.0
BLUNDER = 30.0

_LABELS = {
    "best": "Best move",
    "good": "Good move",
    "inaccuracy": "Inaccuracy",
    "mistake": "Mistake",
    "blunder": "Blunder",
}


def classify(win_drop: float, is_best: bool = False) -> str:
    """Verdict string from the win-percentage drop caused by the move."""
    if is_best:
        return "best"
    if win_drop >= BLUNDER:
        return "blunder"
    if win_drop >= MISTAKE:
        return "mistake"
    if win_drop >= INACCURACY:
        return "inaccuracy"
    return "good"


# Only-move: the best move is essentially forced when the 2nd-best is far worse.
# Measured in win-percentage points (not centipawns), so two winning moves at a
# decided position don't count as "only move" while a single move that holds an
# even game does.
ONLY_MOVE_WIN_GAP = 20.0


def _is_only_move(cp_best: int, cp_second: int) -> bool:
    """True if the best move's win% clears the 2nd-best by ONLY_MOVE_WIN_GAP."""
    return win_percent(cp_best) - win_percent(cp_second) >= ONLY_MOVE_WIN_GAP


def _fmt_white(povscore: chess.engine.PovScore) -> str:
    """Signed eval from White's POV ('+0.80', '-1.23', '+M5', '-M3'), matching
    the convention used by the engine panel."""
    s = povscore.white()
    mate = s.mate()
    if mate is not None:
        return f"{'+' if mate >= 0 else '-'}M{abs(mate)}"
    cp = s.score()
    return f"{cp / 100:+.2f}" if cp is not None else ""


def _phase(board: chess.Board) -> str:
    """Coarse game phase from move number and remaining non-pawn material."""
    npm = (
        3 * (len(board.pieces(chess.KNIGHT, chess.WHITE)) + len(board.pieces(chess.KNIGHT, chess.BLACK)))
        + 3 * (len(board.pieces(chess.BISHOP, chess.WHITE)) + len(board.pieces(chess.BISHOP, chess.BLACK)))
        + 5 * (len(board.pieces(chess.ROOK, chess.WHITE)) + len(board.pieces(chess.ROOK, chess.BLACK)))
        + 9 * (len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK)))
    )
    if npm <= 13:
        return "endgame"
    if board.fullmove_number <= 12:
        return "opening"
    return "middlegame"


# --- Deterministic "why": read straight off the engine eval ----------------
# We do NOT count pieces. The engine's evaluation already folds in material,
# tactics and position over the whole line "for free", so the *size of the
# eval swing the move caused* (in pawns) is the honest measure of what it cost.
# These bands translate that swing into a material word. Tunable.
VALUE_BANDS = [
    (8.0, "a queen"),
    (4.5, "a rook"),
    (2.0, "a piece"),
    (1.4, "the exchange"),
    (0.8, "a pawn"),
]


def _value_word(drop_pawns: float) -> Optional[str]:
    """Material word for an eval swing of `drop_pawns` pawns, or None below ~a
    pawn. Magnitude only -- the caller decides win/lose framing."""
    drop = abs(drop_pawns)
    for threshold, word in VALUE_BANDS:
        if drop >= threshold:
            return word
    return None


def _explain(sc_before, sc_after, is_best: bool, verdict: str) -> dict:
    """Classify *why* the move is good/bad from the engine eval alone.

    `sc_before` / `sc_after` are the scores from the MOVER's point of view
    (position before the move under best play, and after the move). Returns
    {kind, material, mate} -- all JSON-serializable. Mate is read off the score;
    everything else is the magnitude of the eval the move shed, gated by the
    win%-based `verdict` so a tiny eval wobble at a decided position isn't
    reported as "losing a pawn"."""
    reason = {"kind": "positional", "material": None, "mate": None}

    if is_best:
        if sc_before.is_mate() and (sc_before.mate() or 0) > 0:
            reason.update(kind="best_mates", mate=sc_before.mate())
        return reason

    # Sub-optimal move.
    if sc_after.is_mate() and (sc_after.mate() or 0) < 0:
        reason.update(kind="allows_mate", mate=sc_after.mate())
        return reason
    if sc_before.is_mate() and (sc_before.mate() or 0) > 0:
        reason.update(kind="missed_mate", mate=sc_before.mate())
        return reason

    if verdict in ("inaccuracy", "mistake", "blunder"):
        drop = (sc_before.score(mate_score=MATE_CP)
                - sc_after.score(mate_score=MATE_CP)) / 100.0
        word = _value_word(drop)
        if word:
            reason.update(kind="loses_value", material=word)
    return reason


def analyse_move(board: chess.Board, move: chess.Move, *,
                 engine=None, time: Optional[float] = None,
                 depth: Optional[int] = None) -> dict:
    """Build the ground-truth facts for `move` played in `board` (position
    BEFORE the move). Returns a JSON-serializable dict ready for both the
    offline template and the server-side LLM. Raises if no engine is available.

    `board` is not mutated.
    """
    import UCIEngines  # lazy: keeps this module importable without the engine stack

    eng = engine or UCIEngines.engine
    if eng is None:
        raise RuntimeError("No engine available for move review")

    limit = chess.engine.Limit(depth=depth) if depth else chess.engine.Limit(time=time or 0.5)
    mover = board.turn

    # multipv=2: the runner-up line lets us tell whether the best move was the
    # only good one. analyse() returns a list when multipv is given.
    infos = eng.analyse(board, limit, multipv=2)
    info_before = infos[0]
    second = infos[1] if len(infos) > 1 else None
    pv = list(info_before.get("pv", []) or [])
    best_move = pv[0] if pv else None
    best_line_san = UCIEngines.pv_to_san(board, pv[:PV_LEN]) if pv else []
    cp_before = info_before["score"].pov(mover).score(mate_score=MATE_CP)

    only_move = False
    second_eval = None
    if second is not None:
        only_move = _is_only_move(cp_before, second["score"].pov(mover).score(mate_score=MATE_CP))
        second_eval = _fmt_white(second["score"])

    board_after = board.copy(stack=False)
    board_after.push(move)
    info_after = eng.analyse(board_after, limit)
    cp_after = info_after["score"].pov(mover).score(mate_score=MATE_CP)
    pv_after = list(info_after.get("pv", []) or [])
    refutation_san = UCIEngines.pv_to_san(board_after, pv_after[:PV_LEN]) if pv_after else []

    is_best = best_move is not None and move == best_move
    win_drop = 0.0 if is_best else max(0.0, win_percent(cp_before) - win_percent(cp_after))
    cp_loss = 0 if is_best else max(0, cp_before - cp_after)
    verdict = classify(win_drop, is_best)
    reason = _explain(info_before["score"].pov(mover), info_after["score"].pov(mover),
                      is_best, verdict)

    return {
        "fen": board.fen(),
        "mover": "white" if mover == chess.WHITE else "black",
        "move_uci": move.uci(),
        "move_san": board.san(move),
        "is_best": is_best,
        "best_move_san": board.san(best_move) if best_move else None,
        "best_line_san": best_line_san,
        "eval_before": _fmt_white(info_before["score"]),
        "eval_after": _fmt_white(info_after["score"]),
        "cp_before": cp_before,
        "cp_after": cp_after,
        "cp_loss": cp_loss,
        "win_drop": round(win_drop, 1),
        "verdict": verdict,
        "phase": _phase(board),
        "refutation_san": refutation_san,
        "reason": reason,
        "only_move": only_move,
        "second_eval": second_eval,
    }


def _reason_sentence(facts: dict) -> Optional[str]:
    """One plain-language 'why' sentence from the engine-derived reason, or None
    when the move is just a positional choice (no concrete tactic/material)."""
    reason = facts.get("reason") or {}
    kind = reason.get("kind")
    best = facts.get("best_move_san")
    mate = reason.get("mate")
    mat = reason.get("material")
    ref = facts.get("refutation_san") or []

    if kind == "allows_mate":
        return f"It allows mate in {abs(mate)}" + (f" ({' '.join(ref[:4])})." if ref else ".") if mate else "It allows a forced mate."
    if kind == "missed_mate":
        return f"{best} was a forced mate in {abs(mate)}." if (best and mate) else "A forced mate was available."
    if kind == "best_mates":
        return f"It forces mate in {abs(mate)}." if mate else "It forces mate."
    if kind == "loses_value":
        s = f"It loses about {mat}"
        # Name the punishing line only when it actually punishes (a capture/check).
        if ref and any(c in ref[0] for c in "x+#"):
            return s + f" to {' '.join(ref[:3])}."
        return s + "."
    return None


def verbalize_template(facts: dict) -> str:
    """Deterministic English coach comment from the facts dict (primary path)."""
    verdict = facts.get("verdict", "")
    parts = [f"{_LABELS.get(verdict, 'Move')}."]

    why = _reason_sentence(facts)
    if why:
        parts.append(why)

    only_move = facts.get("only_move")
    # When the player FOUND the only good move, praise it here; when they missed
    # it, the emphasis rides on the "Best was ..." clause below instead.
    # (We deliberately don't quote the runner-up's eval -- in lost positions it
    # reads as an absurd number.)
    if only_move and facts.get("is_best"):
        parts.append("The only good move.")

    parts.append(f"Eval {facts.get('eval_before', '')} -> {facts.get('eval_after', '')} (White POV).")

    # Whenever the move was not the engine's top choice, name the best move --
    # including "good" moves -- unless the reason already did (missed mate
    # references the best move).
    reason_kind = (facts.get("reason") or {}).get("kind")
    if not facts.get("is_best") and verdict != "best" and facts.get("best_move_san") \
            and reason_kind != "missed_mate":
        line = " ".join(facts.get("best_line_san") or [])
        tail = " -- the only move" if only_move else ""
        parts.append(f"Best was {facts['best_move_san']}{tail}" + (f" ({line})." if line else "."))

    return " ".join(parts)


def review_move(board: chess.Board, move: chess.Move, *,
                lang: Optional[str] = None, time: Optional[float] = None,
                depth: Optional[int] = None) -> str:
    """Hybrid entry point: compute the facts, then verbalize them with the LLM
    coach when the server is reachable, otherwise with the offline template."""
    import UCIEngines
    if not UCIEngines.is_engine_ready():
        return "No engine configured -- Tools > Setup > Choose engine"

    facts = analyse_move(board, move, time=time, depth=depth)
    lang = lang or (getattr(config, "coach_lang", None) or "en")

    # The deterministic, engine-grounded comment is the PRIMARY output.
    # The LLM is an OPTIONAL enhancement, off by default (opt-in via
    # config.coach_use_llm). It only verbalizes the same facts, never analyzes,
    # and falls back to the template on any problem.
    if getattr(config, "coach_use_llm", False):
        try:
            import coach_llm
            text = coach_llm.comment(facts, lang)
            if text:
                return text
        except Exception as e:
            print(f"review_move: LLM coach failed, using template: {e}")

    return verbalize_template(facts)
