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

def chooseNextMove(gs:GameState)->chess.Move:
    """
    Mostra un menu con le prossime mosse disponibili
    """
    next_moves = gs.getNextMoves()
    if not next_moves:
        return  None# Nessuna mossa disponibile

    if len(next_moves) == 1:
        # Se c'è solo una mossa, la restituisce direttamente
        return next_moves[0]

    menu_running = True
    surface = app.screen
    selected_move = None

    def make_move_wrapper(move_index: int):
        nonlocal menu_running,selected_move
        selected_node = gs.node.variations[move_index]
        selected_move = selected_node.move
        menu_running = False

    # Crea menu
    move_menu = pygame_menu.Menu("Choose Move", app.W, app.H, theme=pygame_menu.themes.THEME_DARK)

    for i, move in enumerate(next_moves):
        san = move.uci() 
        move_menu.add.button(san, make_move_wrapper, i)

    move_menu.add.button('Cancel', lambda: setattr(sys.modules[__name__], "menu_running", False))

    # Loop del menu
    while menu_running:
        events = p.event.get()
        for ev in events:
            if ev.type == p.QUIT:
                p.quit()
                sys.exit()

        surface.fill((0, 0, 0))
        move_menu.update(events)
        move_menu.draw(surface)
        p.display.flip()
    return selected_move


def chooseAnnotation(current_nags):
    """Menu dei glifi di annotazione (NAG) per l'ultima mossa.
    Ritorna il NAG scelto, 0 per rimuovere tutte le annotazioni, o None se
    annullato. I glifi gia' presenti sulla mossa sono marcati con '*'.
    """
    chosen = None
    menu_running = True

    def pick(nag):
        nonlocal chosen, menu_running
        chosen = nag
        menu_running = False

    theme = pygame_menu.themes.THEME_DARK.copy()
    sym_font = p.font.match_font("Segoe UI Symbol,Cambria Math,DejaVu Sans")
    if sym_font:
        theme.widget_font = sym_font  # font che contiene i glifi di annotazione
    menu = pygame_menu.Menu("Annotate last move", app.W, app.H, theme=theme)
    for nag, label in NAG_CHOICES:
        mark = "  *" if nag in current_nags else ""
        menu.add.button(label + mark, pick, nag)
    menu.add.button("(remove all)", pick, 0)
    menu.add.button("Cancel", pick, None)

    surface = app.screen
    while menu_running:
        events = p.event.get()
        for ev in events:
            if ev.type == p.QUIT:
                p.quit()
                sys.exit()
            if ev.type == p.KEYDOWN and ev.key == p.K_ESCAPE:
                chosen = None  # annulla come il pulsante Cancel
                menu_running = False
        surface.fill((0, 0, 0))
        menu.update(events)
        menu.draw(surface)
        p.display.flip()
    return chosen


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
        ToolbarAction("Quit",  "Quit to menu (Q)",                        _post_key(p.K_q)),
    ])

    help_text = [
            "Istruzioni:",
            "- left to take back a move",
            "- right to play next move",
            "- Q per uscire",
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
                    
                    if e.key == p.K_e:  # Engine on /off
                        glc.toggle_engine(gs)

                    if e.key == p.K_l and not whiteCPU and not blackCPU:
                        # Caricamento abilitato solo SENZA computer (modalita' analisi):
                        # la partita parte dalla prima mossa e si scorre in avanti con
                        # la freccia destra (chooseNextMove), esplorando le varianti.
                        # Contro il computer il caricamento e' disabilitato.
                        load_menu(gs)
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
