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


def _confirm(prompt: str) -> bool:
    """Blocking Yes/No prompt drawn over the board. Returns True only on 'Y'."""
    app.main_background()
    BS.drawEndGameText(app.screen, None, prompt + "  (Y/N)", size=22)
    BS.update()
    while True:
        for e in p.event.get():
            if e.type == p.QUIT:
                p.quit()
                sys.exit()
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
                p.quit()
                sys.exit()
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
                p.quit()
                sys.exit()
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

    # Window caption / context label: tell analysis apart from play-vs-computer.
    BS.set_context_label("Analysis / Human Play" if (not whiteCPU and not blackCPU)
                         else "Play vs computer")

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
        ToolbarAction("Variations", "Notation panel (V) -- analysis only", _post_key(p.K_v), enabled=_is_analysis, icon="variations"),
        ToolbarAction("Engine",     "Engine on/off (E)",               _post_key(p.K_e), active=UCIEngines.is_analysing, icon="engine"),
        ToolbarAction("Flip",       "Flip board (F)",                  _post_key(p.K_f), icon="flip"),
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
        None,                                                                            # separator before the exit button
        ToolbarAction("Menu",      "Back to menu (Q)",                                   _post_key(p.K_q), icon="home"),
    ], y=0, height=BS.TOOLBAR_HEIGHT, x0=_edit_x0,
       width=BS.SCREEN_WIDTH - _edit_x0, align="right")
    # Bottom bar: navigation + the move-level actions, separated by a gap (`None`).
    # The move ops are analysis only.
    nav_toolbar = IconToolbar([
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
    show_help = False
    def do_show_help():
        glc.draw_help_overlay(help_text, height=470)


    while running:
        time_delta = app.clock.tick(60) / 1000.0   # pace + dt for the toolbar/manager
        UCIEngines.poll()  # drains the engine info (no-op if analysis off)
        update = False
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
            engine_move:Optional[chess.Move] = UCIEngines.bestMove(gs.board(), elo=elo)  #validMoves is not used at the moment
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
                        #quit
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
                        save_menu(gs)
                        app.main_background()  # see the note on K_l

                    if e.key == p.K_e:  # Engine on /off
                        BS.show_cpu = True
                        UCIEngines.engine_on_off(gs.board(), _draw_engine)

                    if e.key == p.K_o and not whiteCPU and not blackCPU:
                        # Open/load a game. Enabled only WITHOUT a computer (analysis mode):
                        # the game starts from the first move and you scroll forward with
                        # the right arrow (Next / variation picker), exploring the variations.
                        # Against the computer, loading is disabled.
                        load_menu(gs)
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
                        moveMade = False
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
                        moveMade = False
                        animate = False
                        validMoves = gs.stdValidMoves()
                        session.reorient()
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
    BS.set_context_label(None)
    p.event.clear()
    UCIEngines.stop_analysis()
    app.main_menu.enable()
