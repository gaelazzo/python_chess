"""Shared helpers for the in-game event loops.

Extracted from the duplicated bodies of the four play/review loops in
chessMain.py (playAGame, playBrainMasterSet, solvePositionsFromBase, playOpeningLine).
Only the genuinely identical leaf pieces live here; the per-mode control flow
(move input, navigation, skip/solution, save/load) stays in each loop.

Depends only on app_context, BoardScreen, UCIEngines and pygame — never on
chessMain — so there is no circular import.
"""
from __future__ import annotations

import pygame as p
import pyperclip

from app_context import app
import BoardScreen as BS
import UCIEngines

# Colours for the right-click help overlay (were ORANGE / BLACK in chessMain).
_HELP_BG = (100, 100, 0)
_HELP_FG = (0, 0, 0)


def engine_callback(text: str) -> None:
    """Draw the engine evaluation string on the board."""
    BS.drawCpu(app.screen, text)


def draw_help_overlay(help_text, height: int = 400) -> None:
    """Draw the right-click help panel over the board and flip the display.

    The panel is kept INSIDE the board area (its height is capped to the board
    and the line spacing is shrunk to fit) so that the normal board redraw fully
    clears it when the panel is dismissed -- otherwise a tall panel would spill
    into the CPU strip below the board, which the board redraw doesn't repaint.
    The `height` argument is kept for backwards-compatibility but ignored.
    """
    top = 50
    n = max(1, len(help_text))
    max_box = BS.BOARD_HEIGHT - top
    line_step = min(30, max(16, (max_box - 20) // n))
    box_h = min(n * line_step + 20, max_box)
    p.draw.rect(app.screen, _HELP_BG, (50, top, 600, box_h))
    p.draw.rect(app.screen, _HELP_FG, (50, top, 600, box_h), 2)
    for i, line in enumerate(help_text):
        text = app.myfont.render(line, True, _HELP_FG)
        app.screen.blit(text, (60, top + 10 + i * line_step))
    p.display.flip()


def toggle_book(gs) -> None:
    """Toggle the opening-book panel and redraw it."""
    BS.show_book = not BS.show_book
    BS.drawBook(app.screen, gs)


def toggle_pgn(gs) -> None:
    """Toggle the move-list (PGN) panel and redraw it."""
    BS.show_pgn = not BS.show_pgn
    BS.drawPgn(app.screen, gs)


def toggle_engine(gs) -> None:
    """Turn the analysis engine on/off for the current position."""
    BS.show_cpu = True
    UCIEngines.engine_on_off(gs.board(), engine_callback)


def copy_to_clipboard(value: str, message: str, gs, pause: float = 2) -> None:
    """Copy `value` to the clipboard, flash `message` on the board, then pause.

    The caller supplies `value` so each mode keeps its own source (e.g. the live
    `gs` vs. the stored `pos` for the PGN), preserving existing behaviour.
    """
    pyperclip.copy(value)
    BS.drawEndGameText(app.screen, gs, message)
    app.delay(pause)
