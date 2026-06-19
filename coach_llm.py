"""LLM verbalization backend for the move coach -- standalone, no server.

This turns the ground-truth facts from `move_review.analyse_move` into a short
coach comment by calling the Claude API directly. It is deliberately decoupled
from everything else (BrainMaster, learning bases): the only inputs are the
facts dict and a language code, and the only output is a string (or None).

Grounding is the whole point: the model is given engine-computed facts and is
instructed to *verbalize* them, never to analyze. It must not invent moves,
evaluations, or variations beyond what the facts contain.

Soft dependency: if the `anthropic` package is missing or no API key is
configured, `comment()` returns None and the caller falls back to the offline
template. The key is read from the ANTHROPIC_API_KEY env var first, then from
`config.anthropic_api_key` -- it never has to be hard-coded.
"""
from __future__ import annotations

import os
from typing import Optional

from config import config

MODEL = "claude-opus-4-8"

# Stable, byte-constant system prompt -> cacheable prefix (prompt caching).
# Do NOT interpolate per-request data here; the facts go in the user turn.
_SYSTEM = (
    "You are a chess coach commenting on a single move that a student just "
    "played. You are given GROUND-TRUTH facts already computed by a strong "
    "engine: the verdict, the evaluation before and after, the win-percentage "
    "drop, the engine's best move and best line, and the game phase.\n"
    "Your job is to VERBALIZE these facts as a concise, encouraging coach -- "
    "not to analyze the position yourself.\n"
    "Hard rules:\n"
    "- Never invent moves, evaluations, or variations that are not in the "
    "facts. Refer only to the moves given (in SAN).\n"
    "- Do not contradict the verdict or the numbers.\n"
    "- Keep it to 1-3 sentences. Explain *why* in plain language a club player "
    "understands (what the better move achieves, what the played move allowed).\n"
    "- No markdown, no move numbers you were not given, no preamble."
)


def _facts_to_prompt(facts: dict, lang: str) -> str:
    """Render the facts as an explicit, unambiguous block for the model."""
    best_line = " ".join(facts.get("best_line_san") or [])
    return (
        f"Write the comment in language code '{lang}'.\n\n"
        f"Facts:\n"
        f"- mover: {facts.get('mover')}\n"
        f"- move played: {facts.get('move_san')}\n"
        f"- verdict: {facts.get('verdict')}\n"
        f"- eval before (White POV): {facts.get('eval_before')}\n"
        f"- eval after (White POV): {facts.get('eval_after')}\n"
        f"- win-percentage drop: {facts.get('win_drop')}\n"
        f"- centipawn loss: {facts.get('cp_loss')}\n"
        f"- engine best move: {facts.get('best_move_san')}\n"
        f"- engine best line: {best_line}\n"
        f"- game phase: {facts.get('phase')}\n"
        f"- FEN: {facts.get('fen')}\n"
    )


def _api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY") or (getattr(config, "anthropic_api_key", "") or "")


def is_available() -> bool:
    """True if an LLM comment could be produced (key present and SDK importable)."""
    if not _api_key():
        return False
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return True


def comment(facts: dict, lang: str = "en") -> Optional[str]:
    """Return an LLM coach comment for the move, or None if unavailable/failed
    (so the caller can fall back to the offline template)."""
    key = _api_key()
    if not key:
        return None
    try:
        import anthropic
    except Exception:
        return None

    try:
        client = anthropic.Anthropic(api_key=key)
        # Simple, grounded verbalization -> low effort, no extended thinking.
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            output_config={"effort": "low"},
            system=[{
                "type": "text",
                "text": _SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": _facts_to_prompt(facts, lang)}],
        )
        if response.stop_reason == "refusal":
            return None
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return text or None
    except Exception as e:
        print(f"coach_llm.comment failed: {e}")
        return None
