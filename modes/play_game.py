import sys
import random
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List, Dict

import chess
import chess.pgn
import pygame as p
import pygame_menu

from app_context import app
import game_loop_common as glc
import state
from state import playParameters, positionParameters, CIRCLE_COLOR
from GameState import Move, GameState, NAG_CHOICES
import UCIEngines
import plan_analysis
import guide_book
import BoardScreen as BS
from toolbar import IconToolbar, ToolbarAction
import analyzer
import BrainMaster
from BrainMaster import AnswerData, QuestionData, give_answers, ask_for_quiz, unlock_new_lesson
import Quiz
import pgngamelist
from LearningBase import LearningBase, LearnPosition, learningBases
from save_load import save_menu, load_menu
from modes.common import show_message, setAlfa
import notation
from modes.board_session import BoardSession, AnalysisPolicy
from modes.pygame_input import PygameInput

# Watch mode: set True to log every poll and save a crop per move (debug). Off by
# default -- the watch then runs quietly and a bit faster.
WATCH_DEBUG = True


def _confirm(prompt: str) -> bool:
    """Blocking Yes/No prompt drawn over the board. Returns True only on 'Y'."""
    app.main_background()
    BS.drawEndGameText(app.screen, None, prompt + "  (Y/N)", size=22)
    BS.update()
    while True:
        for e in p.event.get():
            if e.type == p.QUIT:
                glc.quit_app()              # guards unsaved PGN edits before exiting
            if e.type == p.KEYDOWN:
                if e.key == p.K_y:
                    return True
                if e.key in (p.K_n, p.K_ESCAPE):
                    return False
        app.clock.tick(30)


def playGame():
    app.main_menu.disable()
    app.main_menu.full_reset()
    playAGame()

def _choose_panel(items, title: str, row_h: int = 32, font_size: int = 18,
                  font_path: Optional[str] = None, cancel_on_left: bool = False,
                  nav_toolbar=None):
    """Side selector panel next to the board. Reused by
    `_variation_picker` (variations) and `chooseAnnotation` (NAG).

    `items` is a list of `(label, value)` tuples. Returns the selected
    `value`, or `None` if the user cancels (Cancel button / Esc).

    Navigation: click / hover, **up/down arrow** to move, **Enter**
    to confirm, **Esc** to cancel. With `cancel_on_left=True` the **left
    arrow** also cancels: at a forward branch (variation picker) Left is the
    natural "I changed my mind about advancing" key, mirroring Right = confirm.
    The board (to the left of the panel) is NOT redrawn -- it stays as drawn by
    the main loop before the call, so the user can still see it clearly.

    `font_path` lets you specify a font with Unicode coverage (e.g.
    for the NAG glyphs: 'Segoe UI Symbol').
    """
    if not items:
        return None

    PANEL_X = BS.BOARD_WIDTH
    PANEL_Y = BS.BOARD_Y
    PANEL_W = BS.SCREEN_WIDTH - BS.BOARD_WIDTH  # covers move log + book/pgn
    title_h = row_h
    cancel_h = row_h
    n = len(items)
    PANEL_H = title_h + n * row_h + cancel_h
    # If it exceeds the screen height we cap it: in practice chooseAnnotation
    # with row_h=24 fits within 512, but just to be safe.
    PANEL_H = min(PANEL_H, BS.BOARD_HEIGHT)

    title_rect = p.Rect(PANEL_X, PANEL_Y, PANEL_W, title_h)
    item_rects = [p.Rect(PANEL_X, PANEL_Y + title_h + i * row_h, PANEL_W, row_h)
                  for i in range(n)]
    cancel_rect = p.Rect(PANEL_X, PANEL_Y + title_h + n * row_h, PANEL_W, cancel_h)
    full_panel = p.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H)

    font_title = p.font.SysFont('Arial', max(12, font_size - 4), bold=True)
    if font_path:
        font_item = p.font.Font(font_path, font_size)
    else:
        font_item = p.font.SysFont('Arial', font_size, bold=False)
    font_cancel = p.font.SysFont('Arial', font_size, bold=True)

    selected_index = 0
    SENTINEL = object()
    result = SENTINEL
    last_mouse_pos = (-1, -1)

    # While this modal runs the main loop (and its toolbar handling) is suspended,
    # but the bottom nav bar stays visible to the left of the panel. Let its
    # Next/Prev buttons drive the picker too: ▶ confirms the highlighted move
    # (like Right arrow), ◀ cancels (like Left arrow).
    next_rect = nav_toolbar.icon_rect("next") if nav_toolbar else None
    prev_rect = nav_toolbar.icon_rect("prev") if nav_toolbar else None

    while result is SENTINEL:
        app.clock.tick(60)

        mouse_pos = p.mouse.get_pos()
        hovered_idx = None
        for i, r in enumerate(item_rects):
            if r.collidepoint(mouse_pos):
                hovered_idx = i
                break
        # Only if the mouse actually moves does hover take precedence over the
        # keyboard's selected_index (so ↓↓↓ Enter works without the
        # cursor "stealing" the selection).
        if hovered_idx is not None and mouse_pos != last_mouse_pos:
            selected_index = hovered_idx
        last_mouse_pos = mouse_pos
        cancel_hover = cancel_rect.collidepoint(mouse_pos)

        # Background + title
        p.draw.rect(app.screen, p.Color('black'), full_panel)
        p.draw.rect(app.screen, p.Color('steelblue'), title_rect)
        txt = font_title.render(title, True, p.Color('white'))
        app.screen.blit(txt, txt.get_rect(center=title_rect.center))

        # Items
        for i, (label, _) in enumerate(items):
            rect = item_rects[i]
            bg = p.Color(80, 80, 120) if i == selected_index else p.Color(40, 40, 60)
            p.draw.rect(app.screen, bg, rect)
            p.draw.rect(app.screen, p.Color(20, 20, 20), rect, 1)
            try:
                txt = font_item.render(label, True, p.Color('white'))
            except Exception:
                txt = font_item.render(label.encode('ascii', 'replace').decode(), True, p.Color('white'))
            app.screen.blit(txt, (rect.x + 8, rect.centery - txt.get_height() // 2))

        # Cancel
        p.draw.rect(app.screen, p.Color(110, 30, 30) if cancel_hover else p.Color(60, 30, 30),
                    cancel_rect)
        p.draw.rect(app.screen, p.Color(20, 20, 20), cancel_rect, 1)
        cancel_label = 'Cancel (Esc / ←)' if cancel_on_left else 'Cancel'
        txt = font_cancel.render(cancel_label, True, p.Color('white'))
        app.screen.blit(txt, txt.get_rect(center=cancel_rect.center))

        p.display.update(full_panel)

        for ev in p.event.get():
            if ev.type == p.QUIT:
                glc.quit_app()              # guards unsaved PGN edits before exiting
            elif ev.type == p.KEYDOWN:
                if ev.key == p.K_ESCAPE or (cancel_on_left and ev.key == p.K_LEFT):
                    result = None
                elif ev.key == p.K_DOWN:
                    selected_index = (selected_index + 1) % n
                elif ev.key == p.K_UP:
                    selected_index = (selected_index - 1) % n
                elif ev.key == p.K_HOME:
                    selected_index = 0
                elif ev.key == p.K_END:
                    selected_index = n - 1
                elif ev.key in (p.K_RETURN, p.K_KP_ENTER, p.K_RIGHT):
                    # Right arrow accepted as Enter: it's the key used for
                    # "go to next move" and therefore natural for
                    # confirming the chosen variation / annotation.
                    result = items[selected_index][1]
            elif ev.type == p.MOUSEBUTTONDOWN and ev.button == 1:
                if next_rect is not None and next_rect.collidepoint(ev.pos):
                    result = items[selected_index][1]   # ▶ confirms the highlighted move
                elif prev_rect is not None and prev_rect.collidepoint(ev.pos):
                    result = None                        # ◀ cancels (go back)
                else:
                    picked = False
                    for i, r in enumerate(item_rects):
                        if r.collidepoint(ev.pos):
                            result = items[i][1]
                            picked = True
                            break
                    if not picked and cancel_rect.collidepoint(ev.pos):
                        result = None

    return result


def _db_stats_lines(gs) -> list:
    """Lines for the DB-stats side panel: stats of the current position in the
    reference DB. The index is already built once at startup (preloaded in
    runMain), so the per-position lookup is O(1) -- no extra caching needed."""
    import os
    import position_stats
    from config import config as _cfg
    board = gs.node.board()
    db_path = (getattr(_cfg, 'reference_db', '') or '').strip()
    if not db_path or not os.path.exists(db_path):
        return ["No reference DB", "set it in Tools > Setup"]
    if db_path not in position_stats._cache:
        return ["DB not indexed", "(restart to index it)"]
    stats = position_stats.lookup_position(db_path, board)
    total = stats['total']
    if total == 0:
        return ["Position not in DB"]
    res = stats['results']
    w, d, lo = res.get(1, 0), res.get(0, 0), res.get(-1, 0)
    pct = (lambda n: (n * 100 / total) if total else 0)
    # Monospace font in the panel -> space-padded columns line up into a table.
    lines = [f"Found {total}  (W POV)",
             f"W {pct(w):.0f}%  D {pct(d):.0f}%  L {pct(lo):.0f}%",
             "",
             f"{'move':<5}{'n':>5}  W/D/L"]
    moves_sorted = sorted(stats['moves'].items(), key=lambda kv: kv[1]['count'], reverse=True)
    for uci, info in moves_sorted[:8]:
        try:
            san = board.san(chess.Move.from_uci(uci))
        except Exception:
            san = uci
        c = info['count']
        mw = info['results'].get(1, 0)
        md = info['results'].get(0, 0)
        ml = info['results'].get(-1, 0)
        lines.append(f"{san:<5}{c:>5}  {mw}/{md}/{ml}")
    return lines


def _variation_picker(moves, board, nav_toolbar=None):
    """UI port for BoardSession.next_move: choose among several continuations
    (shown in SAN). Returns the chosen move, or None if cancelled. The single-
    and no-continuation cases are handled by the core, so this is only ever
    called when there really is a choice to make.

    `nav_toolbar`, when given, lets the bottom nav bar's ▶/◀ buttons confirm/cancel
    the choice too (it stays visible while this modal runs).
    """
    items = []
    for m in moves:
        try:
            label = board.san(m)
        except Exception:
            label = m.uci()
        items.append((label, m))
    # cancel_on_left: at a forward branch the left arrow cancels the advance,
    # mirroring right = confirm (Esc still works too).
    return _choose_panel(items, "Choose move", row_h=32, font_size=18,
                         cancel_on_left=True, nav_toolbar=nav_toolbar)


def chooseAnnotation(current_nags):
    """Side panel with the NAG annotation glyphs for the last move.
    Returns the chosen NAG, 0 to remove all annotations, or None if
    cancelled. The glyphs already present on the move are marked with '*'.

    Compact layout (row_h=24, font 16) to fit within the board's
    height even with 16 NAGs + "remove all"; uses a Unicode font (Segoe
    UI Symbol / DejaVu Sans) to render the symbols ⩲ ± ∓ ∞ correctly.
    """
    items = []
    for nag, label in NAG_CHOICES:
        mark = "  *" if nag in current_nags else ""
        items.append((label + mark, nag))
    items.append(("(remove all)", 0))
    sym_font = p.font.match_font("Segoe UI Symbol,Cambria Math,DejaVu Sans")
    return _choose_panel(items, "Annotate last move", row_h=24, font_size=16,
                         font_path=sym_font)


def editComment(current_text):
    """Edit the current move's MULTI-LINE comment (Enter = new line). Returns the
    entered text, or None if cancelled."""
    return glc.edit_text_multiline("Move comment", current_text or "")


def _split_items(s: str):
    return [x.strip() for x in s.split("/") if x.strip()]


def _plan_arrows_for(board, mover_sans, resp_sans, mover_color, resp_color):
    """SAN moves -> (from_sq, to_sq, color) arrows on `board`. Mover moves parse
    directly; opponent moves after a null move (to flip the turn). Moves that
    don't parse from this position (e.g. late recaptures) are skipped."""
    arrows, b = [], board.copy()
    for san in mover_sans:
        try:
            m = b.parse_san(san)
            arrows.append((m.from_square, m.to_square, mover_color))
        except Exception:
            pass
    try:
        b.push(chess.Move.null())
        for san in resp_sans:
            try:
                m = b.parse_san(san)
                arrows.append((m.from_square, m.to_square, resp_color))
            except Exception:
                pass
    except Exception:
        pass
    return arrows


def _mined_hint(mined) -> str:
    """One-line masters suggestion (from the cached analysis) for the editor:
    the strongest correlated plan (bundle) per side."""
    def top(side):
        side = side or {}
        bundles = side.get("bundles") or []
        if bundles:
            return bundles[0]["moves"]
        spots = side.get("spots") or []
        return ", ".join(s["move"] for s in spots[:3])
    w, b = top(mined.get("white")), top(mined.get("black"))
    parts = []
    if w:
        parts.append("W: " + w)
    if b:
        parts.append("B: " + b)
    return "Masters — " + "  |  ".join(parts) if parts else "Masters: (no data)"


def editOpeningIdeas(board):
    """Edit the IDEAS/PLANS dossier of the CURRENT pawn structure (authoring,
    analysis only). Keyed by the structure signature, so the same dossier is
    shared by every position / move order / opening reaching that structure."""
    import opening_ideas as OI
    d = OI.get_dossier(board)

    menu = pygame_menu.Menu("Opening ideas", app.W, app.H, theme=pygame_menu.themes.THEME_DARK)
    menu.add.label(OI.structure_label(board), font_size=16)
    mined = OI.get_mined(board)
    if mined:
        menu.add.label(_mined_hint(mined), font_size=14)   # masters suggestion (one-line glance)
    if d.get("notes"):                                     # full masters report (read-only, from G)
        menu.add.button("View masters report (G)",
                        lambda: glc.show_text_popup("Masters report", d["notes"]))
    fields = {
        "plans_white": menu.add.text_input("White plans (/): ", default=" / ".join(d.get("plans_white", [])), maxchar=220),
        "plans_black": menu.add.text_input("Black plans (/): ", default=" / ".join(d.get("plans_black", [])), maxchar=220),
    }
    running = [True]

    def save():
        # Only the plan lists are editable here; `notes` (the masters report, filled
        # by G) and any other stored fields are preserved untouched.
        keep = {k: v for k, v in d.items() if k not in ("plans_white", "plans_black")}
        keep.update({
            "plans_white": _split_items(fields["plans_white"].get_value()),
            "plans_black": _split_items(fields["plans_black"].get_value()),
        })
        OI.set_dossier(board, keep)
        running[0] = False

    menu.add.button("Save", save)
    menu.add.button("Cancel", lambda: running.__setitem__(0, False))

    surface = app.screen
    while running[0]:
        events = p.event.get()
        for ev in events:
            if ev.type == p.QUIT:
                glc.quit_app()              # guards unsaved PGN edits before exiting
            if ev.type == p.KEYDOWN and ev.key == p.K_ESCAPE:
                running[0] = False
        surface.fill((0, 0, 0))
        menu.update(events)
        menu.draw(surface)
        p.display.flip()


# Play a game against the engine or against another player, depending on the settings in playParameters
def playAGame():
    gs:Optional[GameState] = GameState()
    positionParameters["gameid"] = None

    validMoves = gs.stdValidMoves()
    elo = playParameters["elo"]
    if playParameters["elomax"]:
        elo = None

    running = True
    
    '''
     current selected square 
    '''
    sqSelected = ()     

    playerClicks = []
    moveMade = False
    animate = False
    gameOver = False
    # Default: start in analysis mode -> the board stays fixed (it does not flip
    # to the side to move on every move). This app isn't really a two-player
    # tool (no clock); press A to toggle the side-to-move flipping back on.
    # The lock now lives in the session's policy (AnalysisPolicy.locked, default
    # True); orientation (session.white_up) is the single source of truth.

    BS.show_pgn = False
    BS.show_book=False
    BS.show_cpu = False

    whiteCPU = playParameters["whiteCPU"]
    blackCPU = playParameters["blackCPU"]

    # Optional "play from my opening book": on the computer's turn it follows the
    # chosen repertoire (a random booked move, with an occasional engine deviation),
    # then the engine once off-book. Only loaded when playing vs the computer.
    guide_index = (guide_book.load_index_for(playParameters.get("guide_opening"))
                   if (whiteCPU or blackCPU) else {})

    # Window caption / context label: tell analysis apart from play-vs-computer.
    # Kept in a variable so the gap navigator (X) can temporarily show the gap in
    # the persistent top strip and Esc can restore it.
    _base_ctx_label = ("Analysis / Human Play" if (not whiteCPU and not blackCPU)
                       else "Play vs computer")
    BS.set_context_label(_base_ctx_label)

    # Play vs computer needs an engine: bail out with a clear message rather than
    # crashing later when the engine has to move (none configured).
    if (whiteCPU or blackCPU) and not UCIEngines.is_engine_ready():
        app.main_background()
        BS.drawEndGameText(app.screen, None,
                           "Configure an engine first: Tools > Setup > Choose engine",
                           size=20)
        BS.update()
        app.delay(3)
        BS.set_context_label(None)
        app.main_menu.enable()
        return

    # Incremental migration to the decoupled controller (modes/board_session):
    # the Session SHARES this loop's GameState (gs), so commands routed through it
    # mutate the same object the loop already uses -- no double state. Migrated so
    # far: undo (Left) / truncate (Del) / delete-variation (Backspace).
    session = BoardSession(AnalysisPolicy(), gs=gs, white_cpu=whiteCPU, black_cpu=blackCPU)
    session.guard_transpositions = (not whiteCPU) and (not blackCPU)   # block duplicate analysis (analysis only)
    # Guard accidental app-close while editing a PGN: register the current game
    # as an editable PGN (analysis only). begin/save/new reset the clean baseline;
    # end_pgn_edit() on exit stops the guard. See game_loop_common.quit_app().
    if not whiteCPU and not blackCPU:
        glc.begin_pgn_edit(lambda: gs.to_PgnString())

    # View layer: the SHARED side-panel singletons (BoardScreen owns one instance
    # per box -- same render/clear interface as every other mode). play_game keeps
    # show_book/show_pgn off so drawGameState only clears those boxes, then repaints
    # them here from the session view-model, over the cleared rectangles.
    book_panel = BS.book
    pgn_panel = BS.pgn
    dbstats_panel = BS.dbstats
    engine_panel = BS.engine

    # Input port: pygame events -> Commands -> session.apply(), the SAME path a
    # test drives with a ScriptedInput. The keymap holds only the plain game
    # commands; richer keys (Right=variation picker, Del/Backspace=confirm, the
    # modal/engine keys) stay in the bespoke handling below.
    game_input = PygameInput({p.K_LEFT: "undo", p.K_b: "book", p.K_m: "pgn",
                              p.K_y: "dbstats",
                              p.K_f: "flip", p.K_l: "analyze"})

    def _draw_engine(lines):
        """Engine callback: draw the analysis lines through the EnginePanel.

        Invoked from UCIEngines.poll() OUTSIDE the main render path, so it flips
        its own rectangle (the main loop's flip would otherwise lag a frame)."""
        engine_panel.visible = BS.show_cpu
        engine_panel.render(app.screen, lines)
        p.display.update(engine_panel.rect)

    if whiteCPU and not blackCPU:
        session.white_up = True                      # human plays Black -> White at the top
        BS.setWhiteUp(app.screen, session.white_up)  # initial orientation (draws once)

    BS.engine.clear(app.screen)

    # Two icon toolbars: the TOP row holds the in-game tools, the BOTTOM row
    # (under the board) holds move navigation. Each button posts the same keyboard
    # shortcut its action already uses, so the KEYDOWN code below does the work and
    # we never duplicate logic; the shortcuts keep working in parallel. Icons are
    # the colour PNGs in images/icons (see tools/generate_icons.py). Buttons not in
    # these rows (Reset R, Comment T, Setup U, Save-tactic K, ...) stay on the keyboard.
    def _post_key(key, mod=0):
        return lambda: p.event.post(p.event.Event(p.KEYDOWN, key=key, mod=mod))
    _is_analysis = lambda: (not whiteCPU) and (not blackCPU)
    # Transposition indicator: lit only when the current position has twins.
    # Recomputed (in the loop) only when the node changes -- the lambda just reads it.
    _twin_state = {"node": None, "twins": False}
    top_toolbar = IconToolbar([
        ToolbarAction("Open",       "Open / load game (O) -- analysis only", _post_key(p.K_o), enabled=_is_analysis, icon="open"),
        ToolbarAction("Save",       "Save game (S)",                   _post_key(p.K_s), icon="save"),
        ToolbarAction("CopyFEN",    "Copy FEN to clipboard (Shift+F)", _post_key(p.K_f, p.KMOD_SHIFT), icon="copyfen"),
        ToolbarAction("CopyPGN",    "Copy PGN to clipboard (Shift+P)", _post_key(p.K_p, p.KMOD_SHIFT), icon="copypgn"),
        ToolbarAction("Lock",       "Lock side / board orientation (L)", _post_key(p.K_l), active=lambda: session.policy.locked, icon="lock"),
        ToolbarAction("Openings",   "Toggle opening book (B)",         _post_key(p.K_b), active=lambda: session.show_book, icon="openings"),
        ToolbarAction("PGN",        "Toggle PGN moves panel (M)",      _post_key(p.K_m), active=lambda: session.show_pgn, icon="pgn"),
        ToolbarAction("Statistics", "Toggle Personal Stats (Y)",       _post_key(p.K_y), active=lambda: session.show_dbstats, icon="statistics"),
        ToolbarAction("Engine",     "Engine on/off (E)",               _post_key(p.K_e), active=UCIEngines.is_analysing, icon="engine"),
        ToolbarAction("Variations", "Notation panel (V) -- analysis only", _post_key(p.K_v), enabled=_is_analysis, icon="variations"),
        ToolbarAction("Plans",      "Analyze typical plans from masters (G) -- analysis only", _post_key(p.K_g), enabled=_is_analysis, icon="analyze"),
        ToolbarAction("Ideas",      "Edit opening ideas (I) -- analysis only",                 _post_key(p.K_i), enabled=_is_analysis, icon="ideas"),
        ToolbarAction("DB",         "Lichess database stats (D) -- analysis only",             _post_key(p.K_d), enabled=_is_analysis, icon="db"),
        ToolbarAction("Help",       "Show help (H)",                   _post_key(p.K_h), icon="help"),
    ], y=0, height=BS.TOOLBAR_HEIGHT)
    # Structure/edit group: a separate right-aligned cluster on the SAME top strip
    # (analysis only), kept apart from the slim main tools on the left.
    _edit_x0 = top_toolbar.content_right() + 16
    top_edit_toolbar = IconToolbar([
        ToolbarAction("EditPos",   "Edit position (U) -- analysis only",                _post_key(p.K_u),         enabled=_is_analysis, icon="editpos"),
        ToolbarAction("AddTactic", "Save position as tactic (K) -- analysis only",       _post_key(p.K_k),         enabled=_is_analysis, icon="addtac"),
        ToolbarAction("Truncate",  "Truncate moves after here (Del) -- analysis only",   _post_key(p.K_DELETE),    enabled=_is_analysis, icon="truncate"),
        ToolbarAction("DeleteVar", "Delete this variation (Backspace) -- analysis only", _post_key(p.K_BACKSPACE), enabled=_is_analysis, icon="delvar"),
        ToolbarAction("Gaps",      "Jump to the next repertoire gap (X) -- analysis only", _post_key(p.K_x),       enabled=_is_analysis, icon="gaps"),
        ToolbarAction("Watch",     "Follow a live board shown on screen (W) -- analysis only", _post_key(p.K_w),   enabled=_is_analysis, icon="watch"),
        None,                                                                            # separator before the exit button
        ToolbarAction("Menu",      "Back to menu (Q)",                                   _post_key(p.K_q), icon="home"),
    ], y=0, height=BS.TOOLBAR_HEIGHT, x0=_edit_x0,
       width=BS.SCREEN_WIDTH - _edit_x0, align="right")
    # Bottom bar: navigation + the move-level actions, separated by a gap (`None`).
    # The move ops are analysis only.
    nav_toolbar = IconToolbar([
        ToolbarAction("Flip",  "Flip board (F)",       _post_key(p.K_f),     icon="flip"),
        ToolbarAction("First", "First move (Home)",   _post_key(p.K_HOME),  icon="first"),
        ToolbarAction("Prev",  "Previous move (Left)", _post_key(p.K_LEFT),  icon="prev"),
        ToolbarAction("Next",  "Next move (Right)",    _post_key(p.K_RIGHT), icon="next"),
        ToolbarAction("Last",  "Last move (End)",      _post_key(p.K_END),   icon="last"),
        ToolbarAction("Twins", "Go to the next transposition / twin of this position (N)",
                      _post_key(p.K_n), enabled=lambda: _twin_state["twins"], icon="twins"),
        None,
        ToolbarAction("Annotate", "Annotate last move (A) -- analysis only", _post_key(p.K_a), enabled=_is_analysis, icon="annotate"),
        ToolbarAction("Comment",  "Comment last move (T) -- analysis only",  _post_key(p.K_t), enabled=_is_analysis, icon="comment"),
        ToolbarAction("Promote",  "Promote variation to main line (P) -- analysis only", _post_key(p.K_p), enabled=_is_analysis, icon="promote"),
    ], y=BS.NAV_Y, height=BS.NAV_HEIGHT, x0=BS.NAV_X, width=BS.NAV_WIDTH,
       align="center", tooltip_above=True)

    def _in_toolbars(pos):
        return (top_toolbar.pointer_in_toolbar(pos) or
                top_edit_toolbar.pointer_in_toolbar(pos) or
                nav_toolbar.pointer_in_toolbar(pos))

    help_text = [
            "Instructions:",
            "- left/right: previous / next move",
            "- Home/End: first / last move",
            "- Q to quit",
            "- Shift+F Copy FEN to clipboard",
            "- Shift+P Copy PGN to clipboard",
            "- S Save game ",
            "- L Lock side (board orientation)",
            "- F Flip board",
            "- R reset",
            "- E Engine ON/OFF",
            "- B show/hide book",
            "- M show/hide moves",
            "- C Coach: review current move",
        ]
    if not whiteCPU and not blackCPU:
        # These appear only without a computer (analysis mode)
        help_text.insert(7, "- O Open / load game ")
        help_text.insert(8, "- A Annotate move (! ? !? ...)")
        help_text.insert(9, "- T Comment move (multi-line: Enter=new line, Ctrl+Enter=save)")
        help_text.insert(10, "- V Notation panel (variations)")
        help_text.insert(11, "- P Promote variation to main line")
        help_text.append("- Del: truncate moves after current")
        help_text.append("- Backspace: delete the whole variation you are in")
        help_text.append("- I Edit opening ideas (plans for this structure)")
        help_text.append("- G Analyze plans (masters, background)")
        help_text.append("- D Lichess database stats (current position)")
        help_text.append("- Transpositions: N next twin / J original / Shift+J find FEN")
        help_text.append("- X Next repertoire gap (jumps the board there; Shift+X rescan, Esc close)")
        help_text.append("- W Watch a live board on screen: reuses the saved theme if it recognizes")
        help_text.append("    the board, else calibrates from the start (W again to stop)")
        help_text.append("- Shift+W Force a fresh calibration (use when the board theme changed)")
    show_help = False
    # Repertoire gap navigation (X): cached scan of the open tree + a preorder
    # index so X can jump to the gap after the current position. Recomputed on
    # Shift+X (after you edit lines). See repertoire_gaps.find_gaps_in_game.
    _gap_state = {"gaps": None, "order": {}}
    # Live-board watch (W): mirror a game shown elsewhere on screen. `session` is a
    # board_watch.WatchSession once running; `accum` throttles screen captures so
    # we grab a few times a second rather than every frame.
    _watch = {"session": None, "accum": 0.0, "hb": 0.0}
    def do_show_help():
        glc.draw_help_overlay(help_text, height=470)


    while running:
        time_delta = app.clock.tick(60) / 1000.0   # pace + dt for the toolbar/manager
        UCIEngines.poll()  # drains the engine info (no-op if analysis off)
        update = False

        # Live-board watch: a few times a second, grab the screen region and let
        # the watch turn any change into a legal move, which we play here so the
        # board/engine/book/PGN mirror the game shown elsewhere.
        if _watch["session"] is not None:
            _watch["accum"] += time_delta
            if WATCH_DEBUG:
                _watch["hb"] += time_delta
                if _watch["hb"] >= 5.0:        # heartbeat (debug): prove we're alive
                    _watch["hb"] = 0.0
                    print(f"[watch] monitoring... tracked={gs.board().board_fen()} "
                          f"last_seen={_watch['session'].last_seen}")
                    if _watch["session"].last_frame is not None:
                        try:
                            import os as _os
                            _wdir = _os.path.join("images", "watch")
                            _os.makedirs(_wdir, exist_ok=True)
                            _watch["session"].last_frame.save(_os.path.join(_wdir, "live.png"))
                        except Exception:
                            pass
            if _watch["accum"] >= 0.08:         # poll ~12x/s so fast moves aren't missed
                #                                 (affordable since mss region-grab cut
                #                                  the poll cost to ~55 ms)
                _watch["accum"] = 0.0
                try:
                    _watch_moves = _watch["session"].poll()
                    if _watch["session"].take_resync():
                        # The watch's board changed discontinuously: rebuild gs from
                        # it. Seed gs at the watch board's ROOT (which is the start for
                        # a normal game, but a mid-game position after a fell-behind
                        # JUMP) and replay its move_stack -- replaying jump-moves onto
                        # the standard start would be ILLEGAL and would corrupt the PGN
                        # tree (add_variation does not validate) -> a later board()
                        # replay crashes. Each move is legality-checked; on any problem
                        # the except below re-syncs the watch to gs's last good state.
                        _wboard = _watch["session"].board
                        gs = session.new_game()
                        _root = _wboard.root()
                        if _root.board_fen() != chess.Board().board_fen():
                            gs.setFen(_root.fen())
                        for _mv in _wboard.move_stack:
                            if not gs.board().is_legal(_mv):
                                raise ValueError(f"resync move {_mv} illegal in gs")
                            _wm = Move.fromChessMove(_mv, gs)
                            if _wm is None:
                                raise ValueError(f"resync move {_mv} not convertible")
                            gs.makeMove(_wm)
                        _gap_state["gaps"] = None
                        moveMade = True
                        animate = False
                        validMoves = gs.stdValidMoves()
                        update = True
                    else:
                        for _cmove in _watch_moves:
                            # gs must accept the move the watch inferred; if it can't
                            # (the two boards somehow diverged) resync gs<-watch
                            # instead of crashing the whole app.
                            _wmv = Move.fromChessMove(_cmove, gs)
                            if _wmv is None or not gs.board().is_legal(_cmove):
                                raise ValueError(f"move {_cmove} not applicable to gs")
                            gs.makeMove(_wmv)
                            moveMade = True
                            animate = False   # NO blocking animation: it stalls polling
                            validMoves = gs.stdValidMoves()
                            update = True
                except Exception as _wex:
                    print(f"[watch] poll/apply failed: {_wex}; resyncing")
                    try:
                        _watch["session"].reseed(gs.board())   # keep watch aligned to gs
                    except Exception:
                        pass

        _plan_res = plan_analysis.poll()   # masters analysis ready? (background)
        if _plan_res is not None:
            _kind, _text = _plan_res
            _on_digit = None
            if _kind == "done":
                BS.set_plan_arrows([])
                _vb = plan_analysis.analyzed_board()
                _mw = (_vb.turn == chess.WHITE) if _vb else True
                _mcol = BS.PLAN_ARROW_WHITE if _mw else BS.PLAN_ARROW_BLACK
                _rcol = BS.PLAN_ARROW_BLACK if _mw else BS.PLAN_ARROW_WHITE
                _varr = ({i: _plan_arrows_for(_vb, v["mover"], v["resp"], _mcol, _rcol)
                          for i, v in enumerate(plan_analysis.variants(), 1)} if _vb else {})

                def _on_digit(n, _va=_varr):
                    BS.set_plan_arrows(_va.get(n, []))   # 0 / unknown -> clear
                    BS.draw_board_only(app.screen, gs)
            if _kind == "done" and plan_analysis.dossier_saved():
                glc.show_text_popup("Masters plans",
                                    _text + "\n\n(saved to your ideas for this structure -- press I to edit)",
                                    on_digit=_on_digit)
            elif _kind == "done" and plan_analysis.dossier_pending():
                glc.show_text_popup("Masters plans", _text,
                                    action_label="Update my ideas from masters",
                                    action=plan_analysis.apply_dossier_update, on_digit=_on_digit)
            else:
                glc.show_text_popup("Masters plans" if _kind == "done" else "Plan analysis failed", _text)
            BS.set_plan_arrows([])     # clear the arrows once the popup closes
            app.main_background()
            BS.engine.clear(app.screen)
            update = True
        if not gameOver and \
                ((gs.whiteToMove() and whiteCPU) or (blackCPU and not gs.whiteToMove())):
            # Book first (if a repertoire is loaded), engine otherwise / on deviation.
            _book_uci = guide_book.book_move(guide_index, gs.board())
            engine_move:Optional[chess.Move] = (chess.Move.from_uci(_book_uci) if _book_uci is not None
                                                else UCIEngines.bestMove(gs.board(), elo=elo))  #validMoves is not used at the moment
            if engine_move is not None:
                move:Optional[Move] = Move.fromChessMove(engine_move, gs)
                gs.makeMove(move)
                moveMade = True # a move was made
                animate = True  # move must be showed
                validMoves = gs.stdValidMoves() # recalculate valid moves
                update=True

        else:
            for e in p.event.get():
                app.manager.process_events(e)
                glc.stop_speech_on_input(e)
                # Order matters: top_edit_toolbar (right cluster) is queried BEFORE
                # top_toolbar, because top_toolbar spans the whole strip and would
                # otherwise swallow clicks on the edit/menu buttons (its
                # pointer_in_toolbar fallback returns True for the whole top row).
                if (top_edit_toolbar.process_event(e) or top_toolbar.process_event(e)
                        or nav_toolbar.process_event(e)):
                    update = True
                    continue
                update = True

                # Input port: plain game commands, board clicks and window-close go
                # through the single apply() path -- exactly what a ScriptedInput
                # drives in a test. Promotion is a callback so the core stays headless;
                # the selection is mirrored back for the renderer. Everything else
                # falls through to the bespoke handling below.
                cmd = game_input.translate(e)
                if cmd is not None:
                    if cmd.kind == "quit":
                        # Window-close on the main analysis screen returns to the
                        # menu; guard unsaved edits before discarding the game.
                        if glc.confirm_unsaved("Unsaved changes to the PGN -- leave to menu anyway?  (Y / N)"):
                            running = False
                    elif cmd.kind == "click":
                        if not gameOver and not _in_toolbars(e.pos):
                            moved = session.apply(cmd,
                                ask_promotion=lambda color: BS.choosePromotion(app.screen, color))
                            sqSelected = session.selected if session.selected is not None else ()
                            playerClicks = [session.selected] if session.selected is not None else []
                            validMoves = session.validMoves
                            if moved is not None:
                                moveMade = True
                                animate = True
                    else:  # "do": undo / book / pgn / flip / analyze
                        session.apply(cmd)
                        if cmd.name == "undo":
                            validMoves = gs.stdValidMoves()
                            moveMade = True
                            animate = False
                            gameOver = False
                    continue                          # event consumed by the input port

                if e.type == p.MOUSEBUTTONDOWN and e.button == 3:
                        # Show help when the right button is pressed
                        show_help = True
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Hide help when the right button is released
                        show_help = False

                elif e.type == p.KEYDOWN:
                    update = True
                    session.message = None          # any key dismisses a lingering status banner
                    if e.key == p.K_RIGHT:
                        moved = session.next_move(
                            pick_variation=lambda mv, bd: _variation_picker(mv, bd, nav_toolbar=nav_toolbar))
                        if moved is not None:
                            validMoves = session.validMoves
                            moveMade = True
                            animate = False

                    if e.key == p.K_HOME:
                        # First move: jump to the start of the game (nav bar |<<).
                        gs.gotoFirstMove()
                        session.refresh()
                        validMoves = session.validMoves
                        sqSelected = ()
                        playerClicks = []
                        moveMade = True
                        animate = False
                        gameOver = False

                    if e.key == p.K_END:
                        # Last move: follow the MAIN line to its end (nav bar >>|).
                        gs.goToLastMove()
                        session.refresh()
                        validMoves = session.validMoves
                        sqSelected = ()
                        playerClicks = []
                        moveMade = True
                        animate = False
                        gameOver = False

                    if e.key == p.K_c:
                        # Coach: review the move that reached the CURRENT position
                        # (gs.node) and show the comment in a side popup.
                        import move_review
                        node = gs.node
                        if node is None or node.move is None or node.parent is None:
                            glc.show_text_popup("Coach",
                                "No move to review yet. Step forward to a move (Right arrow) first.")
                        elif not UCIEngines.is_engine_ready():
                            glc.show_text_popup("Coach",
                                "No engine configured -- Tools > Setup > Choose engine.")
                        else:
                            # The review runs its own synchronous engine.analyse;
                            # pause any live background analysis to avoid contention.
                            if UCIEngines.is_analysing():
                                UCIEngines.stop_analysis()
                            board_before = node.parent.board()
                            san = board_before.san(node.move)
                            comment = move_review.review_move(board_before, node.move, time=0.5)
                            glc.show_text_popup(f"Coach -- {san}", comment)
                        # Repaint the right panels over the popup area.
                        app.main_background()
                        BS.engine.clear(app.screen)
                        continue

                    if e.key == p.K_h:
                        # Toggle the help overlay (also shown while right mouse held).
                        show_help = not show_help

                    if e.key == p.K_q:
                        #quit (Q key or the Menu toolbar button) -> back to menu;
                        # guard unsaved edits before discarding the game.
                        if glc.confirm_unsaved("Unsaved changes to the PGN -- leave to menu anyway?  (Y / N)"):
                            running = False


                    if e.key == p.K_u and not whiteCPU and not blackCPU:
                        # Position setup (modal sub-mode). Analysis only.
                        import position_setup
                        applied = position_setup.run(gs)
                        # Clear the screen: setup draws the palette in the
                        # CPU strip, on exit it stays on screen until someone
                        # repaints over it. drawGameState only redraws
                        # board+movelog+book+pgn, not the CPU strip.
                        app.main_background()
                        if applied:
                            # Position changed: refresh validMoves and force redraw.
                            validMoves = gs.stdValidMoves()
                            moveMade = True
                            animate = False
                            # The toolbar was "uncovered" by the modal -- redraw.
                            # Re-apply the session's orientation rule (no-op when locked).
                            session.reorient()

                    if e.key == p.K_k and not whiteCPU and not blackCPU:
                        # Save current position + last move as a tactic
                        # in a learning base chosen by the user.
                        import add_to_base
                        add_to_base.addPositionToBaseMenu(gs)
                        app.main_background()
                        continue

                    if e.key == p.K_f and (e.mod & p.KMOD_SHIFT):  # Shift+F: copy FEN
                        glc.copy_to_clipboard(gs.board().fen(), "Position copied to clipboard", gs)
                        
                   
                    if e.key== p.K_s: # save the game
                        if save_menu(gs):
                            glc.mark_pgn_saved()   # saved -> current game is the new clean baseline
                        app.main_background()  # see the note on K_l

                    if e.key == p.K_e:  # Engine on /off
                        BS.show_cpu = True
                        UCIEngines.engine_on_off(gs.board(), _draw_engine)

                    if e.key == p.K_o and not whiteCPU and not blackCPU:
                        # Open/load a game. Enabled only WITHOUT a computer (analysis mode):
                        # the game starts from the first move and you scroll forward with
                        # the right arrow (Next / variation picker), exploring the variations.
                        # Against the computer, loading is disabled.
                        if load_menu(gs):
                            glc.mark_pgn_saved()    # loaded game is the new clean baseline
                        _gap_state["gaps"] = None   # new tree -> stale gap scan
                        # Clear the screen: pygame_menu draws full-screen, and
                        # on close the text (the "Load Game" title) remains under
                        # the panels if we don't refresh the background before the redraw.
                        app.main_background()
                        moveMade = False # a move was made
                        animate = False  # move must be showed
                        validMoves = gs.stdValidMoves() # recalculate valid moves
                        session.reorient()   # analysis mode keeps the board fixed
                        continue

                    if e.key == p.K_a and not whiteCPU and not blackCPU:
                        # Annotate the last move (analysis only, no computer)
                        if len(gs.moveLog) > 0:
                            nag = chooseAnnotation(gs.node.nags)
                            if nag == 0:
                                gs.clearMoveNags()
                            elif nag is not None:
                                gs.setMoveNag(nag)
                        # the menu draws full-screen: clear before
                        # redrawing the board (including the CPU strip below)
                        app.main_background()
                        BS.engine.clear(app.screen)
                        continue

                    if e.key == p.K_t and not whiteCPU and not blackCPU:
                        # Text comment on the last move (analysis only)
                        if len(gs.moveLog) > 0:
                            text = editComment(gs.getMoveComment())
                            if text is not None:
                                gs.setMoveComment(text)
                        # the menu draws full-screen: clear before
                        # redrawing the board (including the CPU strip below)
                        app.main_background()
                        BS.engine.clear(app.screen)
                        continue

                    if e.key == p.K_i and not whiteCPU and not blackCPU:
                        # Opening IDEAS: edit the plans/ideas dossier of the
                        # CURRENT pawn structure (authoring; analysis only).
                        editOpeningIdeas(gs.node.board())
                        app.main_background()
                        BS.engine.clear(app.screen)
                        continue

                    if e.key == p.K_g and not whiteCPU and not blackCPU:
                        # Analyze typical plans from the Lichess MASTERS explorer
                        # (background thread; the result pops up when ready).
                        if not plan_analysis.token_ready():
                            show_message(gs, "Set the Lichess token in Setup first")
                            app.delay(2)
                        elif plan_analysis.is_busy():
                            show_message(gs, "Already analyzing plans...")
                            app.delay(1)
                        else:
                            plan_analysis.start(gs.node.board())
                            show_message(gs, "Analyzing masters plans...")
                            app.delay(1)
                        continue

                    if e.key == p.K_d and not whiteCPU and not blackCPU:
                        # Lichess GAMES database: a straight stats query for the
                        # current position (all players, NOT masters; no plans).
                        import lichess_plans as LP
                        show_message(gs, "Querying Lichess database...")
                        try:
                            raw = LP.db_fetch(gs.node.board().fen())
                            BS.draw_board_only(app.screen, gs)   # wipe the "Querying..." text first
                            glc.show_text_popup("Lichess database", LP.format_db_stats(raw))
                        except Exception as ex:
                            BS.draw_board_only(app.screen, gs)
                            glc.show_text_popup("Lichess database -- query failed", str(ex))
                        app.main_background()
                        BS.engine.clear(app.screen)
                        continue

                    if e.key == p.K_j and not whiteCPU and not blackCPU:
                        # J: go to the ORIGINAL (first) occurrence of the current
                        # position (transpositions). Shift+J: search a FEN from the
                        # clipboard and jump to that position in this game.
                        if e.mod & p.KMOD_SHIFT:
                            try:
                                import pyperclip
                                fen = (pyperclip.paste() or "").strip()
                            except Exception:
                                fen = ""
                            target = gs.find_node_by_fen(fen) if fen else None
                            if target is not None:
                                gs.goToNode(target)
                                show_message(gs, "Jumped to the position from the FEN")
                            else:
                                show_message(gs, "FEN not found in this game (copy a FEN first)")
                        else:
                            canon = gs.canonical_node()
                            if canon is not None and canon is not gs.node:
                                gs.goToNode(canon)
                                show_message(gs, "Jumped to the original occurrence")
                            else:
                                show_message(gs, "No earlier occurrence of this position")
                        app.delay(1)
                        session.refresh()
                        app.main_background()
                        BS.engine.clear(app.screen)
                        # Position jumped (transposition / FEN search): re-point the
                        # live engine at it (moveMade drives update_board after the
                        # event loop), else it keeps reporting the eval we left.
                        moveMade = True
                        animate = False
                        validMoves = gs.stdValidMoves()
                        session.reorient()
                        continue

                    if e.key == p.K_n and not whiteCPU and not blackCPU:
                        # N (or the Twins button): cycle to the next occurrence of
                        # this position (transpositions / twins).
                        twin = gs.next_transposition()
                        if twin is not None:
                            gs.goToNode(twin)
                            show_message(gs, "Moved to a twin (transposition)")
                        else:
                            show_message(gs, "No other occurrence of this position")
                        app.delay(1)
                        session.refresh()
                        app.main_background()
                        BS.engine.clear(app.screen)
                        # Position jumped to a twin: re-point the live engine at it
                        # (moveMade drives update_board after the event loop), else
                        # it keeps reporting the eval of the position we left.
                        moveMade = True
                        animate = False
                        validMoves = gs.stdValidMoves()
                        session.reorient()
                        continue

                    if e.key == p.K_x and not whiteCPU and not blackCPU:
                        # X: jump to the next REPERTOIRE GAP -- a strong opponent
                        # reply seen in your own games that this repertoire has no
                        # answer to. Shift+X rescans (after you add lines). The
                        # board is moved onto the gap node so you can edit there.
                        import os as _os
                        from config import config as _cfg
                        _ref = (getattr(_cfg, "reference_db", "") or "").strip()
                        if not _ref or not _os.path.exists(_ref):
                            show_message(gs, "Set a reference DB (your games) in Setup first")
                            app.delay(2)
                            continue
                        if _gap_state["gaps"] is None or (e.mod & p.KMOD_SHIFT):
                            import repertoire_gaps as _RG
                            ucol = _RG.detect_user_color(gs.pgn)
                            if ucol is None:
                                ucol = True   # no variations to infer from -> assume White
                            show_message(gs, "Scanning for repertoire gaps...")
                            gaps, order, mok = _RG.find_gaps_in_game(
                                gs.pgn, _ref, user_color=ucol,
                                on_visit=lambda _f: p.event.pump())
                            _gap_state["gaps"] = gaps
                            _gap_state["order"] = order
                            if not gaps:
                                show_message(gs, "No strong gaps found in this repertoire." if mok
                                             else "Masters lookup unavailable (set Lichess token in Setup).")
                                app.delay(3)
                                continue
                        gaps = _gap_state["gaps"]
                        order = _gap_state["order"]
                        cur = order.get(id(gs.node), -1)
                        nxt = next((g for g in gaps if order.get(id(g.node), -1) > cur), gaps[0])
                        gs.goToNode(nxt.node)
                        top = nxt.report.gaps[0]
                        share = f"{int((top.masters_share or 0) * 100)}%"
                        path = " ".join(nxt.path_san) or "start"
                        extra = f" +{len(nxt.report.gaps) - 1} more" if len(nxt.report.gaps) > 1 else ""
                        # Persistent banner in the top strip (does NOT cover the board and
                        # does NOT auto-vanish): read it while you add the line, press X for
                        # the next gap, Esc to close.
                        BS.set_context_label(
                            f"GAP {gaps.index(nxt) + 1}/{len(gaps)} @ {path}: {top.san}  "
                            f"masters {share} ({top.games_count}x){extra}   -   X next, Esc close")
                        session.refresh()
                        app.main_background()
                        BS.engine.clear(app.screen)
                        # We jumped the board to the gap node: re-point the live
                        # engine at THIS position (moveMade drives update_board
                        # after the event loop), otherwise it keeps reporting the
                        # eval of the position we left -- a mismatch on screen.
                        moveMade = True
                        animate = False
                        validMoves = gs.stdValidMoves()
                        session.reorient()
                        continue

                    if e.key == p.K_w and not whiteCPU and not blackCPU:
                        # Watch: mirror a game shown elsewhere on screen. Toggle on
                        # -> grab the screen, locate the board, calibrate from this
                        # frame (which must be the INITIAL position) and follow every
                        # move into a fresh game. Toggle off -> stop.
                        if _watch["session"] is not None:
                            # Persist what the watch learned: the highlighted-square
                            # look accrues INTO the profile while following the game,
                            # so saving it back makes the next W reuse start richer
                            # (fewer misreads, faster lock-on). Same theme file.
                            try:
                                import board_vision as _bv
                                _pp = _watch.get("profpath")
                                if _pp:
                                    _bv.save_profile(_watch["session"].profile, _pp)
                                    print("[watch] profile updated (learned highlights saved)")
                            except Exception as _sex:
                                print(f"[watch] could not save profile: {_sex}")
                            _watch["session"] = None
                            print("[watch] STOPPED")
                            BS.set_context_label(_base_ctx_label)
                            show_message(gs, "Watch stopped")
                            app.delay(1)
                            app.main_background()
                            continue
                        # Plain W is SMART: first try to recognize the board with the
                        # saved profile (so you needn't remember Shift); if that reads
                        # a sane position, follow from there, otherwise calibrate a new
                        # profile from the START position. Shift+W forces a fresh
                        # calibration (use it when the board theme changed).
                        _force_new = bool(e.mod & p.KMOD_SHIFT)
                        # The watch needs numpy + Pillow (not required elsewhere at
                        # runtime); tell the user plainly instead of a generic failure.
                        try:
                            import board_vision as _bv, board_watch as _bw
                            from PIL import ImageGrab as _IG
                        except Exception as _iex:
                            print(f"watch: missing dependency: {_iex}")
                            show_message(gs, "Watch needs numpy + Pillow -- run:  pip install numpy Pillow")
                            app.delay(4)
                            continue
                        show_message(gs, "Watch: calibrating from the start position..." if _force_new
                                     else "Watch: reading the board on screen...")
                        BS.update()
                        app.delay(0.15)
                        _reuse = False
                        _prof = _seed = _wb = None
                        _fb_box = None                 # find_board result, computed at most once
                        try:
                            _shot = _IG.grab(all_screens=True)   # all monitors
                            # Black out OUR OWN window in the SEARCH image so find_board
                            # can't lock onto the app's own board (which would make the
                            # watch mirror itself). Uses the real window rect (Windows
                            # API) -- robust, unlike blanking which races the compositor.
                            _search = _shot
                            try:
                                import ctypes
                                from ctypes import wintypes
                                from PIL import ImageDraw as _ImageDraw
                                _hwnd = p.display.get_wm_info().get("window")
                                _u = ctypes.windll.user32
                                _vx = _u.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
                                _vy = _u.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
                                _rc = wintypes.RECT()
                                _u.GetWindowRect(_hwnd, ctypes.byref(_rc))
                                _search = _shot.copy()
                                _ImageDraw.Draw(_search).rectangle(
                                    [_rc.left - _vx, _rc.top - _vy,
                                     _rc.right - _vx, _rc.bottom - _vy], fill=(0, 0, 0))
                                if WATCH_DEBUG:
                                    print(f"[watch] excluding own window rect "
                                          f"({_rc.left},{_rc.top})-({_rc.right},{_rc.bottom})")
                            except Exception as _ex:
                                print(f"[watch] window-exclude failed ({_ex}); raw screenshot")
                            import os as _os
                            _profpath = _os.path.join("profiles", "watch_last.pkl")

                            # 1. Unless forced-new, TRY to reuse the saved profile at the
                            #    CURRENT position (any point in the game).
                            if not _force_new and _os.path.exists(_profpath):
                                try:
                                    _prof = _bv.load_profile(_profpath)
                                    # Fast path: if the board is still where it was last
                                    # time, read it there directly -- skips the ~6s scan.
                                    _hint = getattr(_prof, "last_region", None)
                                    if _hint:
                                        # Never trust the saved box blindly: the page may
                                        # have scrolled/zoomed a little since, and a
                                        # slightly-off grid reads the START fine (tall
                                        # back-rank pieces survive it) yet misreads
                                        # low-contrast pawns mid-game -- the watch then
                                        # stalls on move one. A cheap sharpness probe
                                        # (~0.2s) tells an intact box from a stale one;
                                        # only the stale case pays the ~2-3s re-pin.
                                        # Everything here works on _search (own window
                                        # blacked out): the re-pin SEARCHES for board-like
                                        # content around the box, and on the raw shot it
                                        # can lock onto the app's OWN board and mirror it.
                                        _hint = tuple(_hint)
                                        if _bv.framing_sharpness(_search, _hint, _prof) <= 1.15:
                                            if WATCH_DEBUG:
                                                print("[watch] saved region reads blurry -> re-pinning")
                                            _hint = _bv._refine_framing(_search, _hint, _prof)
                                        _bestq = 0.0
                                        for _cwb in (True, False):
                                            _cand = _bv.recognize_position(
                                                _search.crop(tuple(_hint)), _prof,
                                                white_bottom=_cwb, trim=False)
                                            _q = _bv._read_quality(_cand)
                                            if _q > _bestq:
                                                _bestq = _q
                                                _seed, (_l, _t, _r, _b), _wb = _cand, tuple(_hint), _cwb
                                    if _seed is None:
                                        _fb_box = _bv.find_board(_search)
                                        # _search here too: read_with_profile refines the
                                        # framing by SEARCHING around the box -- on the raw
                                        # shot that search can wander onto the app's own board.
                                        _seed, (_l, _t, _r, _b), _wb = _bv.read_with_profile(
                                            _search, _fb_box, _prof)
                                    if _seed is not None:
                                        _reuse = True
                                        if _wb is None:
                                            _wb = _prof.white_bottom
                                        if WATCH_DEBUG:
                                            from PIL import ImageDraw as _ID
                                            _wdir = _os.path.join("images", "watch")
                                            _os.makedirs(_wdir, exist_ok=True)
                                            _shot.save(_os.path.join(_wdir, "reuse_full.png"))
                                            _shot.crop((_l, _t, _r, _b)).save(_os.path.join(_wdir, "reuse.png"))
                                            print(f"[watch] reuse box ({_l},{_t})-({_r},{_b}) "
                                                  f"wb={_wb} seed={_seed.board_fen()}")
                                except Exception as _rex:
                                    print(f"[watch] reuse attempt failed ({_rex}); will calibrate")
                                    _seed = None

                            # 2. No reuse -> calibrate a NEW profile from the START position.
                            if not _reuse:
                                if _fb_box is None:
                                    _fb_box = _bv.find_board(_search)
                                _l, _t, _r, _b = _fb_box
                                # Snap to the exact start-position board: fixes size/
                                # offset and pulls the box off any player bar / clock.
                                # On _search (own window blacked): snap and refine both
                                # SEARCH around the box and must never wander onto the
                                # app's own board.
                                _l, _t, _r, _b = _bv.snap_to_startpos(_search, (_l, _t, _r, _b))
                                # Snap gets within ~half a square -- enough to classify
                                # occupancy, NOT to calibrate: a few px of size error
                                # ghosts every averaged template (this is what broke
                                # the watch on wood themes). Pin the grid to the pixel.
                                _l, _t, _r, _b = _bv.refine_start_grid(_search, (_l, _t, _r, _b))
                                _crop = _shot.crop((_l, _t, _r, _b))
                                if WATCH_DEBUG:      # save what we captured, for the eye
                                    from PIL import ImageDraw as _ID
                                    _wdir = _os.path.join("images", "watch")
                                    _os.makedirs(_wdir, exist_ok=True)
                                    _crop.save(_os.path.join(_wdir, "setup.png"))
                                    _boxed = _shot.copy()
                                    _ID.Draw(_boxed).rectangle([_l, _t, _r, _b],
                                                               outline=(255, 0, 0), width=5)
                                    _boxed.save(_os.path.join(_wdir, "screen.png"))
                                    print(f"[watch] found region ({_l},{_t})-({_r},{_b}) "
                                          f"{_r - _l}x{_b - _t}; captures in {_os.path.abspath(_wdir)}")
                                # trim=False everywhere: the box is already exact, and
                                # the watch reads frames untrimmed -- calibration must
                                # sample the very same grid.
                                _prof = _bv.calibrate_profile(_crop, trim=False)
                                _wb = _prof.white_bottom
                                _seed = _bv.recognize_board(_crop, _prof, white_bottom=_wb,
                                                            trim=False)
                        except Exception as _wex:
                            print(f"[watch] setup failed: {_wex}")
                            show_message(gs, "Watch setup failed (screen capture / board not found)")
                            app.delay(3)
                            app.main_background()
                            continue
                        if _reuse:
                            print(f"[watch] reusing saved profile; seeding at {_seed.fen()}")
                        else:
                            # We seed the tracker at the true start, so a couple of
                            # misreads at calibration are ok.
                            _match = sum(1 for _sq in chess.SQUARES
                                         if _seed.piece_at(_sq) == chess.Board().piece_at(_sq))
                            if WATCH_DEBUG:
                                print(f"[watch] recognized {_seed.board_fen()} "
                                      f"(matches start on {_match}/64, white_bottom={_wb})")
                            if _match < 58:
                                print("[watch] not the initial position -> not starting")
                                show_message(gs, "Aim at a board in the INITIAL position, then press W"
                                             if _force_new else
                                             "Couldn't read with the saved profile -- aim at the INITIAL position (W), or Shift+W to relearn")
                                app.delay(4)
                                app.main_background()
                                continue
                            try:                       # save so a later W can reuse it
                                _bv.save_profile(_prof, _profpath)
                                print("[watch] profile saved (W reuses it automatically from any position)")
                            except Exception as _pex:
                                print(f"[watch] could not save profile: {_pex}")
                            _seed = chess.Board()      # seed the tracker at the true start
                        gs = session.new_game()
                        if _reuse:
                            gs.setFen(_seed.fen())
                        glc.mark_pgn_saved()
                        _gap_state["gaps"] = None
                        _framesdir = None
                        if WATCH_DEBUG:          # fresh screenshots/ folder, one crop per move
                            _framesdir = "screenshots"
                            try:
                                import glob as _glob
                                _os.makedirs(_framesdir, exist_ok=True)
                                for _old in _glob.glob(_os.path.join(_framesdir, "*.png")):
                                    _os.remove(_old)
                            except Exception as _ex:
                                print(f"[watch] could not clear {_framesdir} ({_ex})")
                        _watch["session"] = _bw.WatchSession(
                            _prof, region=(_l, _t, _r, _b),
                            board=_seed, white_bottom=_wb,
                            reseed_after=10**9,   # never auto-reseed in-app (would desync gs)
                            max_depth=3,          # recover up to 3 plies of fast moves
                            log=(lambda m: print(f"[watch] {m}")) if WATCH_DEBUG else None,
                            frames_dir=_framesdir)
                        _prof.last_region = (_l, _t, _r, _b)   # remember where the board is (fast reuse)
                        _watch["profpath"] = _profpath   # save learned highlights here on stop
                        _watch["accum"] = 0.0
                        _watch["hb"] = 0.0
                        print("[watch] STARTED -- following the board. Press W to stop.")
                        BS.set_context_label("WATCHING a live board  -  W to stop")
                        session.refresh()               # gs may have been set to a FEN
                        validMoves = gs.stdValidMoves()
                        sqSelected = ()
                        playerClicks = []
                        app.main_background()
                        BS.engine.clear(app.screen)
                        moveMade = True
                        animate = False
                        session.reorient()
                        continue

                    if e.key == p.K_ESCAPE:
                        # Close the gap banner: restore the normal context label.
                        BS.set_context_label(_base_ctx_label)
                        continue

                    if e.key == p.K_v and not whiteCPU and not blackCPU:
                        # Notation panel: whole game + variations + annotations
                        notation.show_notation(gs)
                        # the panel draws full-screen: clear before
                        # redrawing the board (including the CPU strip below)
                        app.main_background()
                        BS.engine.clear(app.screen)
                        moveMade = False
                        animate = False
                        validMoves = gs.stdValidMoves()
                        session.reorient()   # analysis mode keeps the board fixed
                        continue

                    if e.key == p.K_p and (e.mod & p.KMOD_SHIFT):  # Shift+P: copy PGN
                        glc.copy_to_clipboard(gs.to_PgnString(), "Game copied to clipboard", gs)

                    if e.key == p.K_DELETE and not whiteCPU and not blackCPU:
                        # Truncate: delete the moves after the current position.
                        # No continuation here -> nothing to do (and DON'T clear the
                        # screen, otherwise it just flashes: the old "glitch").
                        if gs.node is not None and gs.node.variations:
                            if _confirm("Delete moves after here?"):
                                session.do("truncate")   # delegated to BoardSession
                                validMoves = gs.stdValidMoves()
                            app.main_background()
                        continue

                    if e.key == p.K_BACKSPACE and not whiteCPU and not blackCPU:
                        # Delete the WHOLE variation the current move belongs to, back
                        # to where it branched off the parent line. No-op (no flash)
                        # when on the main line -- there is no variation to delete.
                        if gs.node is not None and gs.isInVariation():
                            if _confirm("Delete this variation?"):
                                session.do("delete_line")    # delegated to BoardSession
                                validMoves = gs.stdValidMoves()
                                moveMade = True
                                animate = False
                            app.main_background()
                        continue

                    if e.key == p.K_p and not (e.mod & p.KMOD_SHIFT) and not whiteCPU and not blackCPU:
                        # Promote the current variation to the main line at its
                        # branch point (plain P; Shift+P is copy-PGN). Non-destructive --
                        # only reorders the
                        # variations, position unchanged -- so no confirmation and
                        # no re-analysis. Press again to keep promoting up a level
                        # when nested in a sub-variation. KEYDOWN already set
                        # update=True, so board + side panels redraw below.
                        if gs.node is not None and gs.isInVariation():
                            session.do("promote")
                            validMoves = gs.stdValidMoves()
                        continue

                    if e.key == p.K_r:
                        gs = session.new_game()    # fresh game, controller stays in sync
                        glc.mark_pgn_saved()       # empty new game is the clean baseline
                        _gap_state["gaps"] = None  # new tree -> stale gap scan
                        validMoves = session.validMoves
                        sqSelected = ()
                        playerClicks = []
                        moveMade = False
                        animate = False
                            
                

        top_toolbar.update(time_delta)
        top_edit_toolbar.update(time_delta)
        nav_toolbar.update(time_delta)

        if show_help:
                do_show_help()
                continue

        if not update:
            # Idle frame: we redraw the toolbars anyway (for the on-hover
            # highlight + tooltip) and flip the display.
            top_toolbar.draw(app.screen)
            top_edit_toolbar.draw(app.screen)
            nav_toolbar.draw(app.screen)
            p.display.update()
            if plan_analysis.is_busy():
                glc.draw_progress_banner(plan_analysis.progress())
            continue

        if moveMade:
            moveMade = False
            UCIEngines.update_board(
                gs.board(), _draw_engine)
            if animate:
                BS.animateMove(gs.moveLog[-1], app.screen, gs)
                animate = False
            session.reorient()   # re-apply orientation after the move (no-op when locked/CPU)

        # Transposition indicator: refresh only when the node changed (cheap).
        if gs.node is not _twin_state["node"]:
            _twin_state["node"] = gs.node
            _twin_state["twins"] = bool(gs.transpositions_of())

        gameOver = gs.checkMate() or gs.staleMate()

        # The renderer reads orientation from the session (single source of truth).
        BS.whiteUp = session.white_up

        if gameOver:
            BS.drawGameState(app.screen, gs, [], [], ())
            if gs.checkMate():
                text = "Black wins by CheckMate" if gs.colorToMove() == "w" else "White wins by CheckMate"
                # textsurface = app.myfont.render('Checkmate', False, p.Color("red"))
            else:
                text = "Stalemate"
            # Show the result but do NOT close the screen: the user stays
            # on the final position and closes when they want (Q), so they can
            # still save (S), go back (left arrow) or reset (R).
            # gameOver is recomputed every loop, so undo/reset
            # resume the game; mouse moves are already blocked.
            show_message(gs, text)

        else:
            # Highlight squares when needed
            toHighlightCircle = []
            toHighlightSquares = []
            if len(playerClicks) == 1:
                # if a square has been selected, highlith possible piece targets
                mm = [m for m in validMoves if m.startRow == sqSelected[0] and m.startCol == sqSelected[1]]
                toHighlightCircle = [(m.stopRow, m.stopCol,CIRCLE_COLOR) for m in mm]

            if len(playerClicks) == 0 and len(gs.moveLog) > 0:
                # at the the start of a move, previous move is hightlighted
                lastMove = gs.moveLog[-1]
                toHighlightSquares = [(lastMove.stopRow, lastMove.stopCol, setAlfa(p.Color("yellow"),150)),
                                 (lastMove.startRow,lastMove.startCol,setAlfa(p.Color("yellow"),150))]
            BS.drawGameState(app.screen, gs, toHighlightCirclesColor= toHighlightCircle,
                             toHighlightSquareColor=toHighlightSquares,
                             sqSelected=sqSelected)

        # Side panels (book / pgn): the view layer paints them from the session's
        # view-model, over the rectangles drawGameState just cleared. Visibility
        # is owned by the session; a hidden panel renders as a cleared box.
        vm = session.view_model()
        book_panel.visible = vm.panels["book"]
        book_panel.render(app.screen, vm.book)          # SAN list (session.book_view)
        pgn_panel.visible = vm.panels["pgn"]
        pgn_panel.render(app.screen,
                         BS.pgn_lines(gs) if vm.panels["pgn"] else [])
        dbstats_panel.visible = vm.panels["dbstats"]
        dbstats_panel.render(app.screen,
                             _db_stats_lines(gs) if vm.panels["dbstats"] else [])

        top_toolbar.draw(app.screen)
        top_edit_toolbar.draw(app.screen)
        nav_toolbar.draw(app.screen)
        if vm.message:                       # session status (e.g. transposition warnings)
            glc.draw_message_banner(vm.message)
        BS.update()
        if plan_analysis.is_busy():
            glc.draw_progress_banner(plan_analysis.progress())

    top_toolbar.kill()
    top_edit_toolbar.kill()
    nav_toolbar.kill()
    glc.end_pgn_edit()          # stop guarding: the game is no longer being edited
    BS.set_context_label(None)
    p.event.clear()
    UCIEngines.stop_analysis()
    app.main_menu.enable()
