import os
import re
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
from GameState import Move, GameState
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


# Euristica: nelle PGN di repertorio d'apertura il lato che si esercita ha le
# proprie mosse fisse (mainline) mentre l'opponente ha varianti. La PRIMA
# variante incontrata nel testo del file ci dice quale lato sta "ramificando":
#   (N... mossa  -> variante del NERO (l'opponente e' Nero) -> giochiamo Bianco
#   (N.  mossa   -> variante del BIANCO (opponente Bianco) -> giochiamo Nero
_FIRST_VARIATION_RE = re.compile(r'\(\s*(\d+)\s*(\.\.\.|\.)\s*[A-Za-z]')


def detect_user_color_from_pgn(pgn_path: str) -> Optional[str]:
    """Rileva il colore dell'utente leggendo il testo grezzo del PGN.
    Ritorna 'w', 'b' o None se non si trovano varianti."""
    try:
        with open(pgn_path, encoding='utf-8', errors='replace') as f:
            text = f.read()
    except OSError:
        return None
    m = _FIRST_VARIATION_RE.search(text)
    if not m:
        return None
    # group(2) == '...' -> variante del Nero -> utente gioca Bianco
    return 'w' if m.group(2) == '...' else 'b'


# "Study openings": you must always play the best move while the computer replies
# with one of the lines stored in the PGN (typically an opening repertoire).
def playOpening():
    filename = positionParameters.get("filename")
    if filename is None:
        return

    # Auto-rileva il colore dell'utente dal contenuto del PGN. Fallback a Bianco
    # se il file non contiene varianti (es. una sola linea, niente da dedurre).
    pgn_path = os.path.join(pgngamelist.PGN_FOLDER, filename + ".pgn")
    detected = detect_user_color_from_pgn(pgn_path)
    human_color = detected or "w"

    app.main_menu.disable()
    app.main_menu.full_reset()
    if detected is None:
        # informativa: nessuna variante trovata, parto da Bianco di default
        app.main_background()
        BS.drawEndGameText(app.screen, None,
                           f"Colore non rilevabile dal PGN -- gioco Bianco di default", size=18)
        BS.update()
        app.delay(2)
    playOpeningLine(filename, human_color)
    return

def playOpeningLine(filename, humanColor):
    '''
        Play one line from the PGN: the trainee must always play the best move,
        while the computer answers with one of the lines stored in the game
        (typically an opening repertoire).
    '''


    gamelist = pgngamelist.PgnGameList(filename)

    running = True
    sqSelected = ()
    playerClicks = []
    moveMade = False
    animate = False
    BS.show_pgn = False
    BS.show_book=False
    BS.show_cpu = False
    BS.clearCPU(app.screen)
    
    help_text = [
            "Istruzioni:",
            "- left to take back a move",
            "- right to play next move",
            "- Q per uscire",
            "- C Copy FEN to clipboard",
            "- G Copy PGN to clipboard ", 
            "- E Engine ON/OFF",
            "- B show/hide book", 
            "- D show/hide moves"                        
        ]
    show_help = False
    def do_show_help():
        glc.draw_help_overlay(help_text, height=400)

    if gamelist.isEmpty():
        text = "No positions found"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2 )
        app.main_menu.enable()
        return

    color_label = {"w": "Bianco", "b": "Nero"}.get(humanColor, "?")
    BS.set_context_label(f"Apertura: {filename} ({color_label})")

    # Toolbar (fase 2): stesso pattern degli altri mode.
    def _post_key(key, mod=0):
        return lambda: p.event.post(p.event.Event(p.KEYDOWN, key=key, mod=mod))
    # NB: Undo NON e' esposto come pulsante in Study openings: il mode e' un
    # esercizio "trova-la-mossa-giusta", non free play, e gs.undoMove()
    # interagisce in modo non intuitivo con la sequenza (stopCondition / auto-
    # moves dell'avversario), facendo "saltare" passi della soluzione. La
    # scorciatoia tastiera Z/Left resta disponibile per uso volontario.
    toolbar = Toolbar([
        ToolbarAction("Flip",  "Flip board (F)",                          _post_key(p.K_f)),
        ToolbarAction("Eval",  "Evaluate position (S)",                   _post_key(p.K_s)),
        ToolbarAction("Eng",   "Engine on/off (E)",                       _post_key(p.K_e)),
        ToolbarAction("Book",  "Toggle opening book (B)",                 _post_key(p.K_b)),
        ToolbarAction("Moves", "Toggle PGN move list (D)",                _post_key(p.K_d)),
        ToolbarAction("C-FEN", "Copy FEN to clipboard (C)",               _post_key(p.K_c)),
        ToolbarAction("C-PGN", "Copy PGN to clipboard (G)",               _post_key(p.K_g)),
        ToolbarAction("Next",  "Next game (N) -- after a correct line",   _post_key(p.K_n),
                      enabled=lambda: not humanCanPlay),
        ToolbarAction("Quit",  "Quit to menu (Q)",                        _post_key(p.K_q)),
    ])

    while running:
        gs = GameState()
        game = gamelist.chooseRandomGame()
        gs.setPgn(game)      

        if state.play_position:
            # Lead-in Skip: scegli uniformemente la profondita' di partenza tra
            # tutti i turni utente della linea. Pre-scan della mainline a partire
            # da gs.node per contare N turni utente, poi target = randint(1, N).
            # Camminiamo la linea (mainline per l'utente, variante random per il
            # computer) e ci fermiamo al target-esimo turno utente. La vecchia
            # versione (1/3 di break ad ogni turno utente) dava una distribuzione
            # geometrica che privilegiava fortemente le prime mosse del repertorio.
            cur_turn_is_white = gs.node.board().turn
            n_player_turns = 0
            node = gs.node
            while True:
                nxt = node.next()
                if nxt is None:
                    break
                turn_color = 'w' if cur_turn_is_white else 'b'
                if turn_color == humanColor:
                    n_player_turns += 1
                cur_turn_is_white = not cur_turn_is_white
                node = nxt
            target_idx = random.randint(1, n_player_turns) if n_player_turns > 0 else 0

            seen = 0
            moreMoves = True
            while moreMoves:
                playerTurn = gs.colorToMove() == humanColor
                if playerTurn:
                    advanced = gs.doNextMainMove()
                    if advanced:
                        seen += 1
                        if seen >= target_idx:
                            break
                    moreMoves = advanced
                else:
                    move = gs.makeNextMove()
                    moreMoves = move is not None
            # undo dell'ultima mossa: arriva l'utente che deve rigiocarla
            gs.undoMove()
        

        BS.setWhiteUp(app.screen, humanColor == "b")
        BS.drawGameState(app.screen, gs, [], [], ())
        BS.update()

        currentMove = 0
        validMoves = gs.stdValidMoves()
        engineMove = 0
        mustSkip = False
        terminated = False
        gameOver = False
        errors = 0
        stopCondition = False
        while running and not mustSkip:
            time_delta = app.clock.tick(60) / 1000.0   # pace + dt per la toolbar
            humanCanPlay = gs.colorToMove() == humanColor
            checkMove = False
            nextMove = gs.getNextMainMove()
            update= False
            if nextMove is None or stopCondition:  # game is over anyway
                text = "Ok"
                app.main_background()
                BS.drawEndGameText(app.screen, gs, text)
                BS.update()
                app.delay(2 )
                gameOver = True
                break

            if nextMove is not None and not humanCanPlay:
                    move = gs.makeNextMove()
                    moveMade = True
                    animate = True
                    validMoves = gs.stdValidMoves()
                    update = True


            for e in p.event.get():
                app.manager.process_events(e)
                if toolbar.process_event(e):
                    update = True
                    continue
                update = True
                if e.type == p.QUIT:
                    running = False
                elif e.type == p.MOUSEBUTTONDOWN and gameOver and not toolbar.pointer_in_toolbar(e.pos):
                    mustSkip = True
                    break
                elif  e.type == p.MOUSEBUTTONDOWN and e.button == 3:
                        # Mostra aiuto quando il tasto destro è premuto
                        show_help = True
                        # play_position = 1
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Nasconde aiuto quando il tasto destro è rilasciato
                        show_help = False
                elif e.type == p.MOUSEBUTTONDOWN and not gameOver and humanCanPlay and not toolbar.pointer_in_toolbar(e.pos):

                    row, col = BS.getRowColFromLocation(p.mouse.get_pos())

                    if sqSelected == (row, col) or col >= 8 or row>=8: # user clicked same square or in move log
                        sqSelected = ()
                        playerClicks = []
                    else:
                        sqSelected = (row, col)
                        playerClicks.append(sqSelected)

                    if len(playerClicks) == 2:
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

                        # print(move.getChessNotation())
                        validMove = next((m for m in validMoves if move == m), None)
                        if validMove is not None:
                            if gs.checkNextMove(validMove.move):
                                errors = 0
                                gs.doNextMainMove()
                                moveMade = True
                                animate = True
                                validMoves = gs.stdValidMoves()
                                if state.play_position:
                                    stopCondition=True
                            else:
                                errors += 1
                                msg = "Not the right move"
                                if errors >= 3:
                                    rightMove = Move.fromChessMove(gs.getNextMainMove(), gs)
                                    msg = f"hint:{rightMove.uci[:2]}"
                                show_message(gs,msg)
                                app.delay(1)
                            sqSelected = ()
                            playerClicks = []
                        else:
                            sqSelected = (row, col)
                            playerClicks = [sqSelected]

                    if len(playerClicks) == 1 and gs.colorAt(row, col) != gs.colorToMove():
                        sqSelected = ()
                        playerClicks = []

                elif e.type == p.KEYDOWN:
                    if e.key == p.K_z or e.key == p.K_LEFT:
                        gs.undoMove()
                        validMoves = gs.stdValidMoves()
                        moveMade = True
                        animate = False
                        gameOver = False

                    if e.key == p.K_LESS and (e.mod & p.KMOD_SHIFT):
                        BS.setFactor( BS.getFactor()*1.2)

                    if e.key == p.K_LESS and ((e.mod & p.KMOD_SHIFT) == 0):
                        BS.setFactor( BS.getFactor() / 1.2)

                    if e.key == p.K_c:
                        # copy position to clibboard
                        glc.copy_to_clipboard(gs.node.board().fen(), "Position copied to clipboard", gs)
                    
                    if e.key == p.K_g:
                        # copy position to clibboard
                        glc.copy_to_clipboard(gs.to_PgnString(), "Game copied to clipboard", gs)

                    if e.key == p.K_s:  # evaluate score
                        gs.setEvaluation(analyzer.evaluatePosition(gs.node.board(), 5))

                    if e.key == p.K_q:
                        running = False

                    if e.key == p.K_n and not humanCanPlay:
                        mustSkip = True
                        break
                    if e.key == p.K_b:
                        glc.toggle_book(gs)

                    if e.key == p.K_d:
                        glc.toggle_pgn(gs)

                    if e.key == p.K_e:  # Engine on /off
                        glc.toggle_engine(gs)

                    if e.key == p.K_f:
                        # Bugfix: prima questa branca scriveva "whiteUp = not whiteUp"
                        # ma whiteUp non era una locale -> UnboundLocalError al runtime.
                        # Ora usa BS.flipBoard come gli altri mode.
                        BS.flipBoard(app.screen)
                        animate = False
               
            toolbar.update(time_delta)

            if not update:
                # Frame idle: ridisegniamo la toolbar (per i tooltip) e flippiamo.
                toolbar.draw(app.screen)
                p.display.update()
                continue

            if show_help:
                do_show_help()
                continue

            if moveMade and not mustSkip:
                moveMade = False
                lastMove = gs.moveLog[-1] if len(gs.moveLog) > 0 else None
                if animate and lastMove:
                    BS.animateMove(lastMove, app.screen, gs)
                    app.delay(0.1)
                    animate = False

            if humanCanPlay and not moveMade:
                toHighlightSquares = []
                toHighlightCircle = []
                if len(playerClicks) == 1:
                    mm = [m for m in validMoves if m.startRow == sqSelected[0] and m.startCol == sqSelected[1]]
                    toHighlightCircle = [(m.stopRow, m.stopCol, CIRCLE_COLOR) for m in mm]

                if len(playerClicks) == 0 and len(gs.moveLog) > 0:
                    lastMove = gs.moveLog[-1]
                    toHighlightSquares = [(lastMove.stopRow, lastMove.stopCol, setAlfa(p.Color("yellow"), 150)),
                                          (lastMove.startRow, lastMove.startCol, setAlfa(p.Color("yellow"), 150))]

                BS.drawGameState(app.screen, gs, toHighlightCirclesColor=toHighlightCircle,
                                 toHighlightSquareColor=toHighlightSquares,
                                 sqSelected=sqSelected)

            toolbar.draw(app.screen)
            BS.update()

    toolbar.kill()
    BS.set_context_label(None)
    p.event.clear()
    UCIEngines.stop_analysis()
    app.main_menu.enable()
