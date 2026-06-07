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


def playGame():
    app.main_menu.disable()
    app.main_menu.full_reset()
    playAGame()

def _choose_panel(items, title: str, row_h: int = 32, font_size: int = 18,
                  font_path: Optional[str] = None):
    """Pannello selettore laterale alla scacchiera. Riutilizzato da
    `chooseNextMove` (varianti) e `chooseAnnotation` (NAG).

    `items` e' una lista di tuple `(label, value)`. Ritorna il `value`
    selezionato, oppure `None` se l'utente annulla (Cancel button / Esc).

    Navigazione: click / hover, **freccia su/giu'** per spostarsi, **Enter**
    per confermare, **Esc** per annullare. La scacchiera (a sinistra del
    pannello) NON viene ridipinta -- resta quella disegnata dal main loop
    prima della chiamata, cosi' l'utente la vede in chiaro.

    `font_path` permette di specificare un font con copertura Unicode (es.
    per i glifi NAG: 'Segoe UI Symbol').
    """
    if not items:
        return None

    PANEL_X = BS.BOARD_WIDTH
    PANEL_Y = BS.BOARD_Y
    PANEL_W = BS.SCREEN_WIDTH - BS.BOARD_WIDTH  # copre move log + book/pgn
    title_h = row_h
    cancel_h = row_h
    n = len(items)
    PANEL_H = title_h + n * row_h + cancel_h
    # Se sfora l'altezza dello schermo cap-piamo: in pratica chooseAnnotation
    # con row_h=24 sta dentro 512, ma per sicurezza.
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
        # Solo se il mouse si muove davvero, l'hover prende il sopravvento sul
        # selected_index della tastiera (cosi' ↓↓↓ Enter funziona senza che il
        # cursore "rubi" la selezione).
        if hovered_idx is not None and mouse_pos != last_mouse_pos:
            selected_index = hovered_idx
        last_mouse_pos = mouse_pos
        cancel_hover = cancel_rect.collidepoint(mouse_pos)

        # Sfondo + titolo
        p.draw.rect(app.screen, p.Color('black'), full_panel)
        p.draw.rect(app.screen, p.Color('steelblue'), title_rect)
        txt = font_title.render(title, True, p.Color('white'))
        app.screen.blit(txt, txt.get_rect(center=title_rect.center))

        # Voci
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
                    # Right arrow accettato come Enter: e' il tasto usato per
                    # "vai alla prossima mossa" e quindi naturale per
                    # confermare la variante / l'annotazione scelta.
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
    """Cerca la posizione corrente nel DB di riferimento (config.reference_db)
    e mostra un pannello laterale con le statistiche (vedi position_stats.py).

    POV dei risultati: dal **Bianco** sempre (convenzione DB scacchistico).
    """
    import os
    import position_stats
    from config import config as _cfg
    from modes.common import show_message

    db_path = (getattr(_cfg, 'reference_db', '') or '').strip()
    if not db_path or not os.path.exists(db_path):
        # font 20 invece di show_message default 32: il messaggio e' lungo e
        # supererebbe BOARD_WIDTH, finendo fuori a sinistra.
        BS.drawEndGameText(app.screen, gs, "Imposta il DB di riferimento in Tools -> Setup", size=20)
        BS.update()
        app.delay(2.5)
        return

    board = gs.node.board()

    # Indice non in cache? Mostra una schermata "Indicizzo..." mentre si scansiona.
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
        # Ridisegna game state perche' lo abbiamo sovrascritto
        app.main_background()
        BS.drawGameState(app.screen, gs, [], [], ())
        BS.update()

    stats = position_stats.lookup_position(db_path, board)
    total = stats['total']
    if total == 0:
        BS.drawEndGameText(app.screen, gs,
                           f"Posizione mai trovata in {os.path.basename(db_path)}",
                           size=20)
        BS.update()
        app.delay(2.5)
        return

    # Costruisci le righe del pannello
    res = stats['results']
    w, d, lo = res.get(1, 0), res.get(0, 0), res.get(-1, 0)
    def _pct(n):
        return (n * 100 / total) if total else 0
    summary = f"W {w} ({_pct(w):.0f}%)  D {d} ({_pct(d):.0f}%)  L {lo} ({_pct(lo):.0f}%)"

    # Ordina le mosse successive per frequenza decrescente
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
    """Pannello laterale display-only. `lines` e' una lista di (text, _payload).
    Chiusura: Esc, click su Close, o click su una riga qualsiasi."""
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
        # Titolo
        p.draw.rect(app.screen, p.Color('steelblue'), title_rect)
        txt = font_title.render(title, True, p.Color('white'))
        app.screen.blit(txt, txt.get_rect(center=title_rect.center))
        # Righe
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
    """Pannello laterale con le varianti disponibili dalla posizione corrente.
    Mostra le mosse in SAN. Single-variant -> ritorno diretto senza UI.
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
    """Pannello laterale con i glifi NAG di annotazione per l'ultima mossa.
    Ritorna il NAG scelto, 0 per rimuovere tutte le annotazioni, o None se
    annullato. I glifi gia' presenti sulla mossa sono marcati con '*'.

    Layout compatto (row_h=24, font 16) per stare dentro l'altezza della
    scacchiera anche con 16 NAG + "remove all"; usa un font Unicode (Segoe
    UI Symbol / DejaVu Sans) per rendere correttamente i simboli ⩲ ± ∓ ∞.
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
    """Menu con campo di testo per il commento della mossa corrente.
    Ritorna il testo inserito, o None se annullato."""
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
                result[0] = None  # annulla come il pulsante Cancel
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
    analyze = False

    BS.show_pgn = False
    BS.show_book=False
    BS.show_cpu = False

    whiteCPU = playParameters["whiteCPU"]
    blackCPU = playParameters["blackCPU"]

    if whiteCPU and not blackCPU:
        BS.setWhiteUp(app.screen, True)

    BS.clearCPU(app.screen)

    # Toolbar in alto: ogni pulsante posta la stessa scorciatoia da tastiera
    # corrispondente, cosi' il codice dei KEYDOWN gestisce tutto e non duplichiamo
    # logica. Le scorciatoie restano funzionanti in parallelo.
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
        # "Load game" compare solo senza computer (modalita' analisi)
        # disponibili solo senza computer (modalita' analisi)
        help_text.insert(7, "- L Load game ")
        help_text.insert(8, "- N Annotate move (! ? !? ...)")
        help_text.insert(9, "- T Comment move (text)")
        help_text.insert(10, "- V Notation panel (variations)")
    show_help = False
    def do_show_help():
        glc.draw_help_overlay(help_text, height=400)


    while running:
        time_delta = app.clock.tick(60) / 1000.0   # pace + dt per la toolbar/manager
        UCIEngines.poll()  # drena gli info engine (no-op se analisi off)
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
                        # Mostra aiuto quando il tasto destro è premuto
                        show_help = True
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Nasconde aiuto quando il tasto destro è rilasciato
                        show_help = False

                elif e.type == p.MOUSEBUTTONDOWN  and e.button == 1 and not gameOver:
                    if toolbar.pointer_in_toolbar(e.pos):
                        continue                 # click sulla toolbar, non sulla board
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
                        gs.undoMove()
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
                        # Setup posizione (modal sub-mode). Solo in analisi.
                        import position_setup
                        applied = position_setup.run(gs)
                        # Ripulisci lo schermo: il setup disegna la palette nella
                        # striscia CPU, all'uscita resta a video finche' qualcuno
                        # non ridipinge sopra. drawGameState ridisegna solo
                        # board+movelog+book+pgn, non la striscia CPU.
                        app.main_background()
                        if applied:
                            # Posizione cambiata: refresh validMoves e force redraw.
                            validMoves = gs.stdValidMoves()
                            moveMade = True
                            animate = False
                            # La toolbar e' stata "scoperta" dal modal -- ridisegna.
                            BS.setWhiteUp(app.screen, gs.node.board().turn == chess.BLACK)

                    if e.key == p.K_k and not whiteCPU and not blackCPU:
                        # Salva posizione corrente + ultima mossa come tattica
                        # in una learning base scelta dall'utente.
                        import add_to_base
                        add_to_base.addPositionToBaseMenu(gs)
                        app.main_background()
                        continue

                    if e.key == p.K_y and not whiteCPU and not blackCPU:
                        # Statistiche di posizione contro il DB di riferimento.
                        _show_db_stats(gs)
                        app.main_background()
                        continue

                    if e.key == p.K_a:
                        analyze = not analyze
                        # esci dall'analisi -> ri-orienta subito la scacchiera
                        # (altrimenti il lato cambierebbe solo alla mossa dopo)
                        if not whiteCPU and not blackCPU and not analyze:
                            BS.setWhiteUp(app.screen, gs.node.board().turn== chess.BLACK)
                    
                  
                    if e.key == p.K_c:  # copy to clipboard
                        glc.copy_to_clipboard(gs.board().fen(), "Position copied to clipboard", gs)
                        
                   
                    if e.key== p.K_s: # save the game
                        save_menu(gs)
                        app.main_background()  # vedi note sul K_l

                    if e.key == p.K_e:  # Engine on /off
                        glc.toggle_engine(gs)

                    if e.key == p.K_l and not whiteCPU and not blackCPU:
                        # Caricamento abilitato solo SENZA computer (modalita' analisi):
                        # la partita parte dalla prima mossa e si scorre in avanti con
                        # la freccia destra (chooseNextMove), esplorando le varianti.
                        # Contro il computer il caricamento e' disabilitato.
                        load_menu(gs)
                        # Pulisci lo schermo: pygame_menu disegna a tutto schermo, e
                        # alla chiusura le scritte (titolo "Load Game") restano sotto
                        # i pannelli se non rinfreschiamo lo sfondo prima del redraw.
                        app.main_background()
                        moveMade = False # a move was made
                        animate = False  # move must be showed
                        validMoves = gs.stdValidMoves() # recalculate valid moves
                        BS.setWhiteUp(app.screen, gs.node.board().turn== chess.BLACK)
                        continue

                    if e.key == p.K_n and not whiteCPU and not blackCPU:
                        # Annota l'ultima mossa (solo in analisi, senza computer)
                        if len(gs.moveLog) > 0:
                            nag = chooseAnnotation(gs.node.nags)
                            if nag == 0:
                                gs.clearMoveNags()
                            elif nag is not None:
                                gs.setMoveNag(nag)
                        # il menu disegna a tutto schermo: ripulisco prima di
                        # ridisegnare la scacchiera (incluso lo strip CPU sotto)
                        app.main_background()
                        BS.clearCPU(app.screen)
                        continue

                    if e.key == p.K_t and not whiteCPU and not blackCPU:
                        # Commento testuale sull'ultima mossa (solo in analisi)
                        if len(gs.moveLog) > 0:
                            text = editComment(gs.getMoveComment())
                            if text is not None:
                                gs.setMoveComment(text)
                        # il menu disegna a tutto schermo: ripulisco prima di
                        # ridisegnare la scacchiera (incluso lo strip CPU sotto)
                        app.main_background()
                        BS.clearCPU(app.screen)
                        continue

                    if e.key == p.K_v and not whiteCPU and not blackCPU:
                        # Pannello notazione: intera partita + varianti + annotazioni
                        notation.show_notation(gs)
                        # il pannello disegna a tutto schermo: ripulisco prima di
                        # ridisegnare la scacchiera (incluso lo strip CPU sotto)
                        app.main_background()
                        BS.clearCPU(app.screen)
                        moveMade = False
                        animate = False
                        validMoves = gs.stdValidMoves()
                        BS.setWhiteUp(app.screen, gs.node.board().turn== chess.BLACK)
                        continue

                    if e.key == p.K_g:  # copy to clipboard
                        glc.copy_to_clipboard(gs.to_PgnString(), "Game copied to clipboard", gs)

                    if e.key == p.K_f:
                        # Flip della scacchiera: NON impostare moveMade=True, altrimenti
                        # il blocco "if moveMade" chiama setWhiteUp che reimposta
                        # l'orientamento in base al turno e annulla la flip.
                        BS.flipBoard(app.screen)

                    if e.key == p.K_r:
                        gs = GameState()
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
            # Frame idle: ridisegniamo comunque la toolbar (per le animazioni
            # del tooltip on-hover) e flippiamo il display.
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
            # Mostra il risultato ma NON chiudere la maschera: l'utente resta
            # sulla posizione finale e chiude quando vuole (Q), cosi' puo'
            # ancora salvare (S), tornare indietro (freccia sx) o resettare (R).
            # gameOver viene ricalcolato a ogni giro, quindi undo/reset
            # riprendono la partita; la mossa col mouse e' gia' bloccata.
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
