"""Shared helpers for the in-game event loops.

Extracted from the duplicated bodies of the four play/review loops in
chessMain.py (playAGame, playBrainMasterSet, solvePositionsFromBase, playOpeningLine).
Only the genuinely identical leaf pieces live here; the per-mode control flow
(move input, navigation, skip/solution, save/load) stays in each loop.

Depends only on app_context, BoardScreen, UCIEngines and pygame — never on
chessMain — so there is no circular import.
"""
from __future__ import annotations

import sys
from typing import Optional

import pygame as p
import pyperclip

from app_context import app
import BoardScreen as BS
import UCIEngines

# Colours for the right-click help overlay (were ORANGE / BLACK in chessMain).
_HELP_BG = (100, 100, 0)
_HELP_FG = (0, 0, 0)


def engine_callback(text) -> None:
    """Draw the engine evaluation lines through the shared engine panel.

    Invoked from UCIEngines.poll() outside the main render path, so it presents
    its own rectangle (like play_game._draw_engine)."""
    BS.engine.visible = BS.show_cpu
    BS.engine.render(app.screen, text)
    p.display.update(BS.engine.rect)


def stop_speech_on_input(event) -> None:
    """If the event is user input (key press or mouse click),
    stop the in-progress TTS reading of the comments. To be called at the start
    of the for-event loop in every mode.

    Lazy import of `voce` to avoid cycles with GameState.
    """
    if event.type in (p.KEYDOWN, p.MOUSEBUTTONDOWN):
        try:
            from GameState import voce
            voce.stop()
        except Exception:
            pass


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


def _wrap_text(text: str, font: p.font.Font, max_width: int) -> list:
    """Word-wrap `text` (honouring explicit newlines) to `max_width` pixels."""
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            trial = word if not current else current + " " + word
            if font.size(trial)[0] <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _digit_key(key):
    """The 0-9 digit a pygame key maps to (top row or keypad), else None."""
    if p.K_0 <= key <= p.K_9:
        return key - p.K_0
    if p.K_KP0 <= key <= p.K_KP9:
        return key - p.K_KP0
    return None


def show_text_popup(title: str, text: str, copy: bool = True,
                    action_label: str = None, action=None, on_digit=None) -> None:
    """Modal popup over the RIGHT panel area: a title bar, the wrapped `text`, a
    Close button and -- if `action_label`/`action` are given -- an extra action
    button (runs `action()`, then closes). Blocks until Esc/Enter/a button click.

    With `copy=True` the body is put on the clipboard (so it can be pasted into
    notes), and the title shows a hint. Draws only over its own rectangle (the
    board stays as it was behind it); the caller repaints afterwards.
    """
    screen = app.screen
    if copy:
        try:
            pyperclip.copy(text)
            title = title + "   [copied]"
        except Exception:
            pass
    margin, pad = 10, 12
    x = BS.MOVE_LOG_X + margin
    w = BS.SCREEN_WIDTH - BS.MOVE_LOG_X - 2 * margin
    y = BS.BOARD_Y + margin
    h = BS.SIDE_HEIGHT - 2 * margin
    box = p.Rect(x, y, w, h)

    title_font = p.font.SysFont("Arial", 20, bold=True)
    body_font = p.font.SysFont("Arial", 18)
    title_h = title_font.get_height() + 2 * pad
    btn_h, close_w = 34, 130
    by = y + h - btn_h - pad
    has_action = bool(action_label and action)
    if has_action:
        act_w = body_font.size(action_label)[0] + 24
        gap = 14
        x0 = x + (w - (act_w + gap + close_w)) // 2
        act_btn = p.Rect(x0, by, act_w, btn_h)
        btn = p.Rect(x0 + act_w + gap, by, close_w, btn_h)
    else:
        act_btn = None
        btn = p.Rect(x + (w - close_w) // 2, by, close_w, btn_h)

    lines = _wrap_text(text, body_font, w - 2 * pad)

    closed = False
    while not closed:
        app.clock.tick(60)
        mouse = p.mouse.get_pos()

        p.draw.rect(screen, (28, 30, 38), box)
        p.draw.rect(screen, (200, 200, 210), box, 2)
        p.draw.rect(screen, (40, 60, 90), (x, y, w, title_h))
        ts = title_font.render(title, True, p.Color("white"))
        screen.blit(ts, (x + pad, y + (title_h - ts.get_height()) // 2))

        prev_clip = screen.get_clip()
        screen.set_clip(p.Rect(x, y + title_h, w, h - title_h - btn_h - 2 * pad))
        ty = y + title_h + pad
        for line in lines:
            surf = body_font.render(line, True, p.Color("white"))
            screen.blit(surf, (x + pad, ty))
            ty += surf.get_height() + 4
        screen.set_clip(prev_clip)

        if act_btn:
            ah = act_btn.collidepoint(mouse)
            p.draw.rect(screen, (70, 120, 90) if ah else (50, 90, 65), act_btn)
            p.draw.rect(screen, (200, 200, 210), act_btn, 1)
            asf = body_font.render(action_label, True, p.Color("white"))
            screen.blit(asf, asf.get_rect(center=act_btn.center))

        hover = btn.collidepoint(mouse)
        p.draw.rect(screen, (90, 110, 150) if hover else (60, 70, 95), btn)
        p.draw.rect(screen, (200, 200, 210), btn, 1)
        bs = body_font.render("Close (Esc)", True, p.Color("white"))
        screen.blit(bs, bs.get_rect(center=btn.center))

        p.display.update(box)

        for e in p.event.get():
            if e.type == p.QUIT:
                p.quit()
                sys.exit()
            elif e.type == p.KEYDOWN:
                if e.key in (p.K_ESCAPE, p.K_RETURN, p.K_KP_ENTER):
                    closed = True
                elif on_digit is not None:
                    d = _digit_key(e.key)
                    if d is not None:
                        on_digit(d)            # e.g. show/clear plan arrows on the board
            elif e.type == p.MOUSEBUTTONDOWN and e.button == 1:
                if act_btn and act_btn.collidepoint(e.pos):
                    try:
                        action()
                    except Exception as ex:
                        print(f"popup action failed: {ex}")
                    closed = True
                elif btn.collidepoint(e.pos):
                    closed = True


def edit_text_multiline(title: str, initial: str = "") -> Optional[str]:
    """Modal MULTI-LINE text editor (e.g. a PGN move comment). Enter inserts a
    newline; Ctrl+Enter or the Save button commits; Esc or Cancel aborts. Returns
    the edited text, or None if cancelled. Editing is append/backspace at the end
    (no mid-text cursor) -- enough for notes."""
    screen = app.screen
    text = initial or ""
    margin, pad = 36, 12
    x, y = margin, margin
    w, h = app.W - 2 * margin, app.H - 2 * margin
    box = p.Rect(x, y, w, h)
    title_font = p.font.SysFont("Arial", 20, bold=True)
    body_font = p.font.SysFont("Arial", 18)
    title_h = title_font.get_height() + 2 * pad
    btn_h, btn_w, gap = 34, 130, 14
    by = y + h - btn_h - pad
    save_btn = p.Rect(x + (w - 2 * btn_w - gap) // 2, by, btn_w, btn_h)
    cancel_btn = p.Rect(save_btn.right + gap, by, btn_w, btn_h)
    hint = "Enter: new line  -  Ctrl+Enter: save  -  Ctrl+V: paste  -  Esc: cancel"
    p.key.set_repeat(400, 40)   # hold-to-repeat (backspace, typing) while the editor is open
    result: list = [None]
    running = True
    while running:
        app.clock.tick(60)
        mouse = p.mouse.get_pos()
        p.draw.rect(screen, (28, 30, 38), box)
        p.draw.rect(screen, (200, 200, 210), box, 2)
        p.draw.rect(screen, (40, 60, 90), (x, y, w, title_h))
        ts = title_font.render(f"{title}    ({hint})", True, p.Color("white"))
        screen.blit(ts, (x + pad, y + (title_h - ts.get_height()) // 2))

        prev = screen.get_clip()
        screen.set_clip(p.Rect(x, y + title_h, w, h - title_h - btn_h - 2 * pad))
        ty = y + title_h + pad
        for ln in _wrap_text(text + "█", body_font, w - 2 * pad):   # block caret at the end
            surf = body_font.render(ln, True, p.Color("white"))
            screen.blit(surf, (x + pad, ty))
            ty += surf.get_height() + 4
        screen.set_clip(prev)

        for btn, label, col in ((save_btn, "Save", (50, 90, 65)), (cancel_btn, "Cancel", (60, 70, 95))):
            hover = btn.collidepoint(mouse)
            p.draw.rect(screen, tuple(min(255, c + 30) for c in col) if hover else col, btn)
            p.draw.rect(screen, (200, 200, 210), btn, 1)
            ls = body_font.render(label, True, p.Color("white"))
            screen.blit(ls, ls.get_rect(center=btn.center))
        p.display.update(box)

        for e in p.event.get():
            if e.type == p.QUIT:
                p.quit()
                sys.exit()
            elif e.type == p.KEYDOWN:
                ctrl = e.mod & p.KMOD_CTRL
                if e.key == p.K_ESCAPE:
                    result[0] = None
                    running = False
                elif e.key in (p.K_RETURN, p.K_KP_ENTER):
                    if ctrl:
                        result[0] = text
                        running = False
                    else:
                        text += "\n"
                elif ctrl and e.key == p.K_v:                  # paste (append clipboard)
                    try:
                        text = (text + (pyperclip.paste() or ""))[:2000]
                    except Exception:
                        pass
                elif ctrl and e.key == p.K_c:                  # copy the whole text
                    try:
                        pyperclip.copy(text)
                    except Exception:
                        pass
                elif e.key == p.K_BACKSPACE:
                    if ctrl:                                   # delete the last word
                        stripped = text.rstrip()
                        cut = max(stripped.rfind(" "), stripped.rfind("\n"))
                        text = stripped[:cut + 1] if cut != -1 else ""
                    else:
                        text = text[:-1]
                elif e.unicode and e.unicode.isprintable() and len(text) < 2000:
                    text += e.unicode
            elif e.type == p.MOUSEBUTTONDOWN and e.button == 1:
                if save_btn.collidepoint(e.pos):
                    result[0] = text
                    running = False
                elif cancel_btn.collidepoint(e.pos):
                    result[0] = None
                    running = False
    p.key.set_repeat()   # restore the app default (no auto-repeat)
    return result[0]


def draw_progress_banner(text: str) -> None:
    """Top-of-board banner showing the line a long background analysis is
    currently querying (its current variation/subvariation), so the wait is
    informative. Self-contained: paints and flips only its own rectangle."""
    screen = app.screen
    font = app.myfont or BS.BOOKFONT
    if font is None:
        return
    pad = 8
    w = BS.BOARD_WIDTH
    label = "Analyzing   " + (text or "...")
    while font.size(label)[0] > w - 2 * pad and len(label) > 16:
        label = label[:-2]
    surf = font.render(label, True, p.Color("white"))
    rect = p.Rect(0, BS.BOARD_Y, w, surf.get_height() + 2 * pad)
    overlay = p.Surface(rect.size, p.SRCALPHA)
    overlay.fill((25, 25, 35, 220))
    screen.blit(overlay, rect.topleft)
    screen.blit(surf, (pad, BS.BOARD_Y + pad))
    p.display.update(rect)


def draw_message_banner(text: str) -> None:
    """A generic amber status banner across the top of the board (e.g. the
    transposition warnings from the session), WORD-WRAPPED to up to 2 lines so a
    long message isn't cut off. Paints/flips only its own rect."""
    if not text:
        return
    screen = app.screen
    font = app.myfont or BS.BOOKFONT
    if font is None:
        return
    pad = 8
    w = BS.BOARD_WIDTH
    lines = _wrap_text(text, font, w - 2 * pad)[:2]
    line_h = font.size("Ag")[1] + 2
    rect = p.Rect(0, BS.BOARD_Y, w, line_h * len(lines) + 2 * pad)
    overlay = p.Surface(rect.size, p.SRCALPHA)
    overlay.fill((150, 100, 20, 230))   # amber: a status/warning, distinct from the analysis banner
    screen.blit(overlay, rect.topleft)
    y = BS.BOARD_Y + pad
    for ln in lines:
        screen.blit(font.render(ln, True, p.Color("white")), (pad, y))
        y += line_h
    p.display.update(rect)


def toggle_book(gs) -> None:
    """Toggle the opening-book panel and redraw it."""
    BS.show_book = not BS.show_book
    BS.book.visible = BS.show_book
    BS.book.render(app.screen, BS.book_lines(gs))
    p.display.update(BS.book.rect)


def toggle_pgn(gs) -> None:
    """Toggle the move-list (PGN) panel and redraw it."""
    BS.show_pgn = not BS.show_pgn
    BS.pgn.visible = BS.show_pgn
    BS.pgn.render(app.screen, BS.pgn_lines(gs))
    p.display.update(BS.pgn.rect)


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
