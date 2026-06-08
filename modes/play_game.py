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
import BoardScreen as BS
from toolbar import Toolbar, ToolbarAction
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


def _confirm(prompt: str) -> bool:
    """Blocking Yes/No prompt drawn over the board. Returns True only on 'Y'."""
    app.main_background()
    BS.drawEndGameText(app.screen, None, prompt + "   [Y = yes / N = no]", size=22)
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
                  font_path: Optional[str] = None):
    """Side selector panel next to the board. Reused by
    `chooseNextMove` (variations) and `chooseAnnotation` (NAG).

    `items` is a list of `(label, value)` tuples. Returns the selected
    `value`, or `None` if the user cancels (Cancel button / Esc).

    Navigation: click / hover, **up/down arrow** to move, **Enter**
    to confirm, **Esc** to cancel. The board (to the left of the
    panel) is NOT redrawn -- it stays as drawn by the main loop
    before the call, so the user can still see it clearly.

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
        txt = font_cancel.render('Cancel', True, p.Color('white'))
        app.screen.blit(txt, txt.get_rect(center=cancel_rect.center))

        p.display.update(full_panel)

        for ev in p.event.get():
            if ev.type == p.QUIT:
                p.quit()
                sys.exit()
            elif ev.type == p.KEYDOWN:
                if ev.key == p.K_ESCAPE:
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
                picked = False
                for i, r in enumerate(item_rects):
                    if r.collidepoint(ev.pos):
                        result = items[i][1]
                        picked = True
                        break
                if not picked and cancel_rect.collidepoint(ev.pos):
                    result = None

    return result


def _show_db_stats(gs: "GameState") -> None:
    """Look up the current position in the reference DB (config.reference_db)
    and show a side panel with the statistics (see position_stats.py).

    Results POV: always from **White** (chess DB convention).
    """
    import os
    import position_stats
    from config import config as _cfg
    from modes.common import show_message

    db_path = (getattr(_cfg, 'reference_db', '') or '').strip()
    if not db_path or not os.path.exists(db_path):
        # font 20 instead of show_message default 32: the message is long and
        # would exceed BOARD_WIDTH, spilling off to the left.
        BS.drawEndGameText(app.screen, gs, "Set the reference DB in Tools -> Setup", size=20)
        BS.update()
        app.delay(2.5)
        return

    board = gs.node.board()

    # Index not in cache? Show an "Indexing..." screen while scanning.
    cached = db_path in position_stats._cache
    if not cached:
        def _progress(n_games):
            app.main_background()
            BS.drawEndGameText(app.screen, None,
                               f"Indexing {os.path.basename(db_path)}: {n_games} games", size=22)
            BS.update()
            p.event.pump()
        _progress(0)
        position_stats.get_index(db_path, progress=_progress)
        # Redraw game state because we overwrote it
        app.main_background()
        BS.drawGameState(app.screen, gs, [], [], ())
        BS.update()

    stats = position_stats.lookup_position(db_path, board)
    total = stats['total']
    if total == 0:
        BS.drawEndGameText(app.screen, gs,
                           f"Position never found in {os.path.basename(db_path)}",
                           size=20)
        BS.update()
        app.delay(2.5)
        return

    # Build the panel rows
    res = stats['results']
    w, d, lo = res.get(1, 0), res.get(0, 0), res.get(-1, 0)
    def _pct(n):
        return (n * 100 / total) if total else 0
    summary = f"W {w} ({_pct(w):.0f}%)  D {d} ({_pct(d):.0f}%)  L {lo} ({_pct(lo):.0f}%)"

    # Sort the following moves by descending frequency
    moves_sorted = sorted(stats['moves'].items(), key=lambda kv: kv[1]['count'], reverse=True)

    lines = []
    lines.append((f"Found {total} times", None))
    lines.append((summary, None))
    if moves_sorted:
        lines.append(("--- Continuations (W/D/L) ---", None))
    for uci, info in moves_sorted:
        try:
            san = board.san(chess.Move.from_uci(uci))
        except Exception:
            san = uci
        c = info['count']
        mw = info['results'].get(1, 0)
        md = info['results'].get(0, 0)
        ml = info['results'].get(-1, 0)
        lines.append((f"{san:>8}  {c:>3}  ({mw}/{md}/{ml})", uci))

    _show_info_panel(lines, title=f"DB: {os.path.basename(db_path)}",
                     row_h=24, font_size=14)


def _show_info_panel(lines, title: str, row_h: int = 24, font_size: int = 14):
    """Display-only side panel. `lines` is a list of (text, _payload).
    Close: Esc, click on Close, or click on any row."""
    PANEL_X = BS.BOARD_WIDTH
    PANEL_Y = BS.BOARD_Y
    PANEL_W = BS.SCREEN_WIDTH - BS.BOARD_WIDTH
    title_h = row_h
    close_h = row_h
    n = len(lines)
    PANEL_H = min(title_h + n * row_h + close_h, BS.BOARD_HEIGHT)

    title_rect = p.Rect(PANEL_X, PANEL_Y, PANEL_W, title_h)
    line_rects = [p.Rect(PANEL_X, PANEL_Y + title_h + i * row_h, PANEL_W, row_h)
                  for i in range(n)]
    close_rect = p.Rect(PANEL_X, PANEL_Y + title_h + n * row_h, PANEL_W, close_h)
    full_panel = p.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H)

    font_title = p.font.SysFont('Arial', max(12, font_size), bold=True)
    font_line = p.font.SysFont('Consolas,Courier New,Lucida Console', font_size)
    font_close = p.font.SysFont('Arial', font_size, bold=True)

    running = True
    while running:
        app.clock.tick(60)
        p.draw.rect(app.screen, p.Color('black'), full_panel)
        # Title
        p.draw.rect(app.screen, p.Color('steelblue'), title_rect)
        txt = font_title.render(title, True, p.Color('white'))
        app.screen.blit(txt, txt.get_rect(center=title_rect.center))
        # Rows
        for i, (text, _) in enumerate(lines):
            rect = line_rects[i]
            p.draw.rect(app.screen, p.Color(30, 30, 45), rect)
            p.draw.rect(app.screen, p.Color(20, 20, 20), rect, 1)
            try:
                txt = font_line.render(text, True, p.Color('white'))
            except Exception:
                txt = font_line.render(text.encode('ascii', 'replace').decode(),
                                       True, p.Color('white'))
            app.screen.blit(txt, (rect.x + 8, rect.centery - txt.get_height() // 2))
        # Close
        close_hover = close_rect.collidepoint(p.mouse.get_pos())
        p.draw.rect(app.screen, p.Color(80, 80, 80) if close_hover else p.Color(50, 50, 50), close_rect)
        p.draw.rect(app.screen, p.Color(20, 20, 20), close_rect, 1)
        txt = font_close.render('Close (Esc)', True, p.Color('white'))
        app.screen.blit(txt, txt.get_rect(center=close_rect.center))
        p.display.update(full_panel)

        for ev in p.event.get():
            if ev.type == p.QUIT:
                p.quit(); sys.exit()
            elif ev.type == p.KEYDOWN and ev.key in (p.K_ESCAPE, p.K_RETURN, p.K_KP_ENTER):
                running = False
            elif ev.type == p.MOUSEBUTTONDOWN and ev.button == 1:
                running = False


def chooseNextMove(gs:GameState)->chess.Move:
    """Side panel with the variations available from the current position.
    Shows the moves in SAN. Single-variant -> direct return without UI.
    """
    next_moves = gs.getNextMoves()
    if not next_moves:
        return None
    if len(next_moves) == 1:
        return next_moves[0]
    cur_board = gs.node.board()
    items = []
    for m in next_moves:
        try:
            label = cur_board.san(m)
        except Exception:
            label = m.uci()
        items.append((label, m))
    return _choose_panel(items, "Choose move", row_h=32, font_size=18)


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
    """Menu with a text field for the current move's comment.
    Returns the entered text, or None if cancelled."""
    result = [None]
    menu_running = True

    menu = pygame_menu.Menu("Move comment", app.W, app.H, theme=pygame_menu.themes.THEME_DARK)
    text_field = menu.add.text_input("> ", default=current_text or "", maxchar=200)

    def save():
        nonlocal menu_running
        result[0] = text_field.get_value()
        menu_running = False

    def cancel():
        nonlocal menu_running
        menu_running = False

    menu.add.button("Save", save)
    menu.add.button("Cancel", cancel)

    surface = app.screen
    while menu_running:
        events = p.event.get()
        for ev in events:
            if ev.type == p.QUIT:
                p.quit()
                sys.exit()
            if ev.type == p.KEYDOWN and ev.key == p.K_ESCAPE:
                result[0] = None  # cancel like the Cancel button
                menu_running = False
        surface.fill((0, 0, 0))
        menu.update(events)
        menu.draw(surface)
        p.display.flip()
    return result[0]


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
    analyze = True

    BS.show_pgn = False
    BS.show_book=False
    BS.show_cpu = False

    whiteCPU = playParameters["whiteCPU"]
    blackCPU = playParameters["blackCPU"]

    # Incremental migration to the decoupled controller (modes/board_session):
    # the Session SHARES this loop's GameState (gs), so commands routed through it
    # mutate the same object the loop already uses -- no double state. Migrated so
    # far: undo (Left) / truncate (Del) / delete-variation (Backspace).
    session = BoardSession(AnalysisPolicy(), gs=gs, white_cpu=whiteCPU, black_cpu=blackCPU)

    if whiteCPU and not blackCPU:
        BS.setWhiteUp(app.screen, True)

    BS.clearCPU(app.screen)

    # Toolbar at the top: each button posts the same corresponding keyboard
    # shortcut, so the KEYDOWN code handles everything and we don't duplicate
    # logic. The shortcuts keep working in parallel.
    def _post_key(key):
        return lambda: p.event.post(p.event.Event(p.KEYDOWN, key=key))
    _is_analysis = lambda: (not whiteCPU) and (not blackCPU)
    toolbar = Toolbar([
        ToolbarAction("Undo",  "Undo (Left arrow)",                       _post_key(p.K_LEFT)),
        ToolbarAction("Next",  "Next move (Right arrow)",                 _post_key(p.K_RIGHT)),
        ToolbarAction("Save",  "Save game (S)",                           _post_key(p.K_s)),
        ToolbarAction("Anal",  "Analyze mode toggle (A)",                 _post_key(p.K_a), active=lambda: analyze),
        ToolbarAction("Flip",  "Flip board (F)",                          _post_key(p.K_f)),
        ToolbarAction("Reset", "Reset game (R)",                          _post_key(p.K_r)),
        ToolbarAction("Eng",   "Engine on/off (E)",                       _post_key(p.K_e), active=UCIEngines.is_analysing),
        ToolbarAction("Book",  "Toggle opening book (B)",                 _post_key(p.K_b), active=lambda: BS.show_book),
        ToolbarAction("Moves", "Toggle PGN move list (D)",                _post_key(p.K_d), active=lambda: BS.show_pgn),
        ToolbarAction("C-FEN", "Copy FEN to clipboard (C)",               _post_key(p.K_c)),
        ToolbarAction("C-PGN", "Copy PGN to clipboard (G)",               _post_key(p.K_g)),
        ToolbarAction("Load",  "Load game (L) -- analysis only",          _post_key(p.K_l), enabled=_is_analysis),
        ToolbarAction("Annot", "Annotate last move (N) -- analysis only", _post_key(p.K_n), enabled=_is_analysis),
        ToolbarAction("Cmnt",  "Comment last move (T) -- analysis only",  _post_key(p.K_t), enabled=_is_analysis),
        ToolbarAction("Notat", "Notation panel (V) -- analysis only",     _post_key(p.K_v), enabled=_is_analysis),
        ToolbarAction("Setup", "Edit position (U) -- analysis only",      _post_key(p.K_u), enabled=_is_analysis),
        ToolbarAction("AddTac", "Save current pos + last move as tactic (K) -- analysis only",
                      _post_key(p.K_k), enabled=_is_analysis),
        ToolbarAction("DB",    "Position stats from reference DB (Y) -- analysis only",
                      _post_key(p.K_y), enabled=_is_analysis),
        ToolbarAction("Quit",  "Quit to menu (Q)",                        _post_key(p.K_q)),
    ])

    help_text = [
            "Instructions:",
            "- left to take back a move",
            "- right to play next move",
            "- Q to quit",
            "- C Copy FEN to clipboard",
            "- G Copy PGN to clipboard ", 
            "- S Save game ",
            "- A Analyze mode",
            "- F Flip board",
            "- R reset"
            "- E Engine ON/OFF",
            "- B show/hide book",
            "- D show/hide moves"
        ]
    if not whiteCPU and not blackCPU:
        # "Load game" appears only without a computer (analysis mode)
        # available only without a computer (analysis mode)
        help_text.insert(7, "- L Load game ")
        help_text.insert(8, "- N Annotate move (! ? !? ...)")
        help_text.insert(9, "- T Comment move (text)")
        help_text.insert(10, "- V Notation panel (variations)")
        help_text.append("- Del: truncate moves after current")
        help_text.append("- Backspace: delete the whole variation you are in")
    show_help = False
    def do_show_help():
        glc.draw_help_overlay(help_text, height=400)


    while running:
        time_delta = app.clock.tick(60) / 1000.0   # pace + dt for the toolbar/manager
        UCIEngines.poll()  # drains the engine info (no-op if analysis off)
        update = False
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
                if toolbar.process_event(e):
                    update = True
                    continue
                update = True
                if e.type == p.QUIT:
                    running = False
                elif  e.type == p.MOUSEBUTTONDOWN and e.button == 3:
                        # Show help when the right button is pressed
                        show_help = True
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Hide help when the right button is released
                        show_help = False

                elif e.type == p.MOUSEBUTTONDOWN  and e.button == 1 and not gameOver:
                    if toolbar.pointer_in_toolbar(e.pos):
                        continue                 # click on the toolbar, not on the board
                    #tak
                    row,col = BS.getRowColFromLocation(p.mouse.get_pos())
                    update = True
                    if sqSelected == (row, col) or col >= 8 or row>=8:  # user clicked same square or in move log
                        sqSelected = ()
                        playerClicks = [] # reset the sequence of selections
                    else:
                        sqSelected = (row, col) # new current selected square
                        playerClicks.append(sqSelected)

                    if len(playerClicks) == 2:
                        # do the move if two squares have been selected and the move is valid
                        move = Move(playerClicks[0], playerClicks[1], gs)

                        if (move.pieceMoved[1] == "P") and (row == 0 or row == 7):
                            validPromotions = [m for m in validMoves if m.startRow == playerClicks[0][0] and
                                               m.startCol == playerClicks[0][1] and
                                               m.stopRow == playerClicks[1][0] and
                                               m.stopCol == playerClicks[1][1]
                                               ]

                            if len(validPromotions) > 0:
                                piece = BS.choosePromotion(app.screen, move.pieceMoved[0])
                                move = move.promoteToPiece(piece)

                        validMove:Optional[Move] = move if move in validMoves else None
                        if validMove is not None:
                            # the move is valid so make it on the board
                            gs.makeMove(validMove)
                            moveMade = True
                            animate = True      
                            validMoves = gs.stdValidMoves() #evaluate the new list of valid moves
                            sqSelected = ()
                            playerClicks = []
                        else:
                            # the move can't be made so resets the square select list to the last square
                            sqSelected = (row, col)
                            playerClicks = [sqSelected]

                    if len(playerClicks) == 1 and gs.colorAt(row, col) != gs.colorToMove():
                        # if the player want to move a piece that is of the opposite color, the square selection is rejected
                        sqSelected = ()
                        playerClicks = []

                elif e.type == p.KEYDOWN:
                    update = True
                    if e.key == p.K_LEFT:
                        session.do("undo")           # delegated to BoardSession
                        validMoves = gs.stdValidMoves()
                        moveMade = True
                        animate = False
                        gameOver = False

                    if e.key == p.K_RIGHT:
                        move = chooseNextMove(gs)
                        if move is not None:
                            gs.makeChessMove(move)
                            validMoves = gs.stdValidMoves()
                            moveMade = True
                            animate = False

                    if e.key == p.K_b:
                        glc.toggle_book(gs)

                    if e.key == p.K_d:
                        glc.toggle_pgn(gs)

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
                            # Analysis mode locks the orientation: don't re-flip.
                            if not analyze:
                                BS.setWhiteUp(app.screen, gs.node.board().turn == chess.BLACK)

                    if e.key == p.K_k and not whiteCPU and not blackCPU:
                        # Save current position + last move as a tactic
                        # in a learning base chosen by the user.
                        import add_to_base
                        add_to_base.addPositionToBaseMenu(gs)
                        app.main_background()
                        continue

                    if e.key == p.K_y and not whiteCPU and not blackCPU:
                        # Position statistics against the reference DB.
                        _show_db_stats(gs)
                        app.main_background()
                        continue

                    if e.key == p.K_a:
                        analyze = not analyze
                        # exit analysis -> immediately re-orient the board
                        # (otherwise the side would only change on the next move)
                        if not whiteCPU and not blackCPU and not analyze:
                            BS.setWhiteUp(app.screen, gs.node.board().turn== chess.BLACK)
                    
                  
                    if e.key == p.K_c:  # copy to clipboard
                        glc.copy_to_clipboard(gs.board().fen(), "Position copied to clipboard", gs)
                        
                   
                    if e.key== p.K_s: # save the game
                        save_menu(gs)
                        app.main_background()  # see the note on K_l

                    if e.key == p.K_e:  # Engine on /off
                        glc.toggle_engine(gs)

                    if e.key == p.K_l and not whiteCPU and not blackCPU:
                        # Loading enabled only WITHOUT a computer (analysis mode):
                        # the game starts from the first move and you scroll forward with
                        # the right arrow (chooseNextMove), exploring the variations.
                        # Against the computer, loading is disabled.
                        load_menu(gs)
                        # Clear the screen: pygame_menu draws full-screen, and
                        # on close the text (the "Load Game" title) remains under
                        # the panels if we don't refresh the background before the redraw.
                        app.main_background()
                        moveMade = False # a move was made
                        animate = False  # move must be showed
                        validMoves = gs.stdValidMoves() # recalculate valid moves
                        if not analyze:  # analysis mode locks the board orientation
                            BS.setWhiteUp(app.screen, gs.node.board().turn== chess.BLACK)
                        continue

                    if e.key == p.K_n and not whiteCPU and not blackCPU:
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
                        BS.clearCPU(app.screen)
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
                        BS.clearCPU(app.screen)
                        continue

                    if e.key == p.K_v and not whiteCPU and not blackCPU:
                        # Notation panel: whole game + variations + annotations
                        notation.show_notation(gs)
                        # the panel draws full-screen: clear before
                        # redrawing the board (including the CPU strip below)
                        app.main_background()
                        BS.clearCPU(app.screen)
                        moveMade = False
                        animate = False
                        validMoves = gs.stdValidMoves()
                        if not analyze:  # analysis mode locks the board orientation
                            BS.setWhiteUp(app.screen, gs.node.board().turn== chess.BLACK)
                        continue

                    if e.key == p.K_g:  # copy to clipboard
                        glc.copy_to_clipboard(gs.to_PgnString(), "Game copied to clipboard", gs)

                    if e.key == p.K_DELETE and not whiteCPU and not blackCPU:
                        # Truncate: delete the moves after the current position.
                        # No continuation here -> nothing to do (and DON'T clear the
                        # screen, otherwise it just flashes: the old "glitch").
                        if gs.node is not None and gs.node.variations:
                            if _confirm("Delete the moves after the current position?"):
                                session.do("truncate")   # delegated to BoardSession
                                validMoves = gs.stdValidMoves()
                            app.main_background()
                        continue

                    if e.key == p.K_BACKSPACE and not whiteCPU and not blackCPU:
                        # Delete the WHOLE variation the current move belongs to, back
                        # to where it branched off the parent line. No-op (no flash)
                        # when on the main line -- there is no variation to delete.
                        if gs.node is not None and gs.isInVariation():
                            if _confirm("Delete the whole variation you are in?"):
                                session.do("delete_line")    # delegated to BoardSession
                                validMoves = gs.stdValidMoves()
                                moveMade = True
                                animate = False
                            app.main_background()
                        continue

                    if e.key == p.K_f:
                        # Flip the board: do NOT set moveMade=True, otherwise
                        # the "if moveMade" block calls setWhiteUp which resets
                        # the orientation based on the turn and cancels the flip.
                        BS.flipBoard(app.screen)

                    if e.key == p.K_r:
                        gs = GameState()
                        session.gs = gs            # keep the controller on the new game
                        session.refresh()
                        sqSelected = ()
                        playerClicks = []
                        validMoves = gs.stdValidMoves() #evaluate the new list of valid moves
                        moveMade = False
                        animate = False
                            
                

        toolbar.update(time_delta)

        if show_help:
                do_show_help()
                continue

        if not update:
            # Idle frame: we redraw the toolbar anyway (for the on-hover
            # tooltip animations) and flip the display.
            toolbar.draw(app.screen)
            p.display.update()
            continue

        if moveMade:
            moveMade = False
            UCIEngines.update_board(
                gs.board(), glc.engine_callback)
            if animate:
                BS.animateMove(gs.moveLog[-1], app.screen, gs)
                animate = False
            if not whiteCPU and not blackCPU and not analyze:
                BS.setWhiteUp(app.screen, gs.node.board().turn== chess.BLACK)

        gameOver = gs.checkMate() or gs.staleMate()

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

        toolbar.draw(app.screen)
        BS.update()

    toolbar.kill()
    p.event.clear()
    UCIEngines.stop_analysis()
    app.main_menu.enable()
