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
from config import config
from GameState import Move, GameState
import UCIEngines
import BoardScreen as BS
from toolbar import Toolbar, ToolbarAction
import analyzer
import analyzer as AN
import BrainMaster
from BrainMaster import AnswerData, QuestionData, give_answers, ask_for_quiz, unlock_new_lesson
import Quiz
import pgngamelist
from LearningBase import LearningBase, LearnPosition, learningBases
from save_load import save_menu, load_menu
from modes.common import show_message, setAlfa


# "Solve positions": wrapper that launches the review on the selected base.
def solvePositions():
    app.main_menu.disable()
    app.main_menu.full_reset()
    solvePositionsFromBase(learningBases[positionParameters["base"]])
    return


# "Solve positions" engine: one move per position, taken from a LearningBase.
def solvePositionsFromBase(learningBase:LearningBase):
    '''
    Reviews positions from a LearningBase as a dynamic session of at most
    config.maxErrorsToConsider active positions. A position enters when seen and
    leaves either immediately (correct on the first try) or after
    config.correctsToLearn consecutive correct answers following a mistake. Both
    are program-wide settings (Setup menu, persisted in config.json).
    '''

    BS.set_context_label(f"Allenando: {learningBase.filename or '?'}")

    # Stato pulito per il toggle E: se un mode precedente (es. endgames) aveva
    # lasciato l'analisi attiva, il primo E qui finirebbe nel ramo "stop"
    # (mostrando "engine stopped") invece di avviarla -- da fuori sembra "il
    # motore non si avvia".
    UCIEngines.stop_analysis()

    # Filter locale: ECO da positionParameters (se l'utente lo ha digitato nel
    # menu), color=None sempre. Il colore-al-tratto e' gia' implicito nella base
    # (rimosso dal menu come selettore separato), e positionParameters["color"]
    # potrebbe essere stato settato da altri menu (Download chess.com/lichess)
    # senza che l'utente intenda filtrare la pratica.
    filter_ = {"eco": positionParameters.get("eco"), "color": None}
    # ll is a copy (not a deep copy) of data in the csv, not the same structure
    ll = analyzer.getPositions(learningBase, filter_, order=state.practice_order)

    running = True
    sqSelected = ()
    playerClicks = []
    moveMade = False
    animate = False
    gameOver = False
    errorsMade= [] # tells how many mistakes for every position
    numberOfErrors = []
    maxErrorsToConsider = config.maxErrorsToConsider
    if len(ll)==0:
        text = "No positions found"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2 )

    help_text = [
            "Istruzioni:",
            "- Q per uscire",
            "- C copia la posizione FEN nella clipboard",
            "- G copia la partita nella clipboard",
            "- + vedi altre mosse",
            "- H mostra la soluzione" ,
            "- E Engine ON/OFF",
            "- B show/hide book", 
            "- D show/hide moves"
        ]
    show_help = False
    BS.clearCPU(app.screen)

    # Toolbar (fase 2): stesso pattern di play_game -- ogni pulsante posta
    # la stessa scorciatoia da tastiera, cosi' il codice di gestione resta
    # singolo. Alcuni pulsanti hanno predicato `enabled` che legge le variabili
    # di stato dell'inner loop (humanCanPlay, updateStats).
    # NOTA: humanCanPlay/updateStats sono locali e riassegnati durante il loop;
    # le lambda li risolvono al call time, quindi vedono sempre il valore corrente.
    def _post_key(key, mod=0):
        return lambda: p.event.post(p.event.Event(p.KEYDOWN, key=key, mod=mod))
    toolbar = Toolbar([
        ToolbarAction("Sol",   "Show solution (H)",                       _post_key(p.K_h),
                      enabled=lambda: not updateStats),
        ToolbarAction("+Mov",  "Show more continuation moves (+) -- after a correct answer",
                                                                          _post_key(p.K_KP_PLUS),
                      enabled=lambda: not humanCanPlay),
        ToolbarAction("Next",  "Next position (N) -- after a correct answer",
                                                                          _post_key(p.K_n),
                      enabled=lambda: not humanCanPlay),
        ToolbarAction("Eng",   "Engine on/off (E)",                       _post_key(p.K_e)),
        ToolbarAction("Book",  "Toggle opening book (B)",                 _post_key(p.K_b)),
        ToolbarAction("Moves", "Toggle PGN move list (D)",                _post_key(p.K_d)),
        ToolbarAction("C-FEN", "Copy FEN to clipboard (C)",               _post_key(p.K_c)),
        ToolbarAction("C-PGN", "Copy PGN to clipboard (G)",               _post_key(p.K_g)),
        ToolbarAction("Quit",  "Quit to menu (Q)",                        _post_key(p.K_q)),
    ])

    def do_show_help():
        glc.draw_help_overlay(help_text, height=300)


    while (len(ll) > 0 or len(errorsMade) > 0) and running:
        #extract a position to play, either from the errorsMade or from the learningBase.
        # to do that, we choose a random number between 0 and maxErrorsToConsider-1, then, if this position is filled
        #  in the errorsMade list, we play that. Otherwise we take another random position from the learning base.
        # index of current error being examined or None if it is still not present in errorsMade
        
        currentElement = random.randint(0, maxErrorsToConsider-1)  # take a random position in the range 0-maxErrorsToConsider-1

        if currentElement >= len(errorsMade) and len(ll)>0:
            pos = ll.pop()  # positions examined are less than the the desired index, we take the position from the learning base 
            isNewPosition = True
        else:
            if currentElement >= len(errorsMade): # learning base has been exhausted, so we go on with errorsMade
                currentElement = len(errorsMade)-1  
            pos = errorsMade[currentElement]
            isNewPosition = False

        # print(f"currentElement is {currentElement}, len(errorsMade) = {len(errorsMade)}, "
        #       f"len(numberOfErrors) is {len(numberOfErrors)}")
        # print(errorsMade)
        fen = pos.fen.split()
        # Header tollerante: i campi opzionali (eco/data) e i player "?" sono
        # comuni nelle PGN di finali / studi -- skip se assenti.
        header = []
        for label, value in (("White", pos.white), ("Black", pos.black), ("ECO", pos.eco)):
            if value and value != "?":
                header.append(f"{label}:{value}")
        if pos.gamedate is not None:
            header.append(f"Date:{pos.gamedate.strftime('%d-%m-%Y')}")
        if pos.ok != pos.move:
            header.append("mistake was " + pos.move)



        # Setup della posizione. La posizione finale e' SEMPRE `pos.fen`
        # (canonica nella learning base). Quel che cambia e' il percorso:
        #
        # - Se `pos.moves` e' ricostruibile dalla scacchiera iniziale standard
        #   (caso tipico: tattica/aperture salvate da PGN normali), si usa il
        #   replay delle mosse -> `gs` mantiene la cronologia completa: il
        #   Lead-in "Replay" funziona, il pannello Notation (V) mostra il
        #   path d'arrivo, undo (Z/<-) torna indietro tra le mosse storiche.
        #
        # - Se invece le mosse non sono applicabili dallo start standard
        #   (caso tipico: finali da PGN con header `[FEN]` custom, posizioni
        #   Chess960 / studi), si fa setup diretto da `pos.fen`. Si perde la
        #   cronologia (Lead-in Replay non ha nulla da mostrare) ma la
        #   posizione e' corretta.
        moves = pos.moves.split() if pos.moves else []
        try:
            _probe = chess.Board()
            for _u in moves:
                _m = chess.Move.from_uci(_u)
                if not _probe.is_pseudo_legal(_m):
                    raise ValueError(f"non pseudo-legale: {_u}")
                _probe.push(_m)
            # Sanity finale: dopo aver applicato tutte le mosse, devo essere
            # esattamente in pos.fen (altrimenti la base ha incoerenze).
            _replayable = (_probe.fen().split()[0] == pos.fen.split()[0]
                           and _probe.turn == chess.Board(pos.fen).turn)
        except (chess.IllegalMoveError, chess.InvalidMoveError, AssertionError, ValueError):
            _replayable = False

        gs = GameState()
        if not _replayable:
            _seed = chess.pgn.Game()
            _seed.headers["FEN"] = pos.fen
            _seed.headers["SetUp"] = "1"
            gs.setPgn(_seed)
            moves = []  # gia' alla posizione, niente da rigiocare
        gs.setHeader(header)
        #gs.setFen(pos["fen"])
        #BS.setWhiteUp(app.screen, not gs.whiteToMove())
        BS.setWhiteUp(app.screen, fen[1] == "b")
        BS.drawGameState(app.screen, gs, [], [], ())
        BS.update()
        solution = pos.ok
        # show_cpu deve riflettere lo stato reale dell'engine: se update_board()
        # ha tenuto attiva l'analisi durante la continuazione della posizione
        # precedente, "stopper" e' ancora set ma `show_cpu=False` silenzierebbe
        # drawCpu, dando l'illusione che il motore non scriva piu'. Per la nuova
        # posizione mostriamo le info se e solo se l'analisi e' davvero in corso.
        BS.show_cpu = UCIEngines.is_analysing()

        currentMove = 0
        validMoves = gs.stdValidMoves()
        engineMove = 0
        mustSkip = False        # mustSkip determines the exit from the cycle
        humanCanPlay = True
        # Reset di stato per la nuova posizione: moveMade/animate sono locali alla
        # funzione ma persistono fra una posizione e l'altra. Se nella posizione
        # precedente l'utente ha cliccato per saltare proprio nel frame in cui
        # l'engine aveva appena giocato (moveMade=True + mustSkip=True), il
        # blocco di pulizia a riga 369 non fira e moveMade resta True. Alla
        # nuova posizione gs.moveLog e' vuoto -> moveLog[-1] esplode.
        moveMade = False
        animate = False
        
       

        while running and not mustSkip:
            time_delta = app.clock.tick(60) / 1000.0   # pace + dt per la toolbar
            UCIEngines.poll()  # drena gli info engine (no-op se analisi off)
            update  = False
            updateStats = False

            if state.play_position:
                while currentMove < len(moves):
                    ucimove = moves[currentMove]
                    currentMove += 1
                    chessMove:Optional[chess.Move] = chess.Move.from_uci(ucimove)
                    move:Optional[Move] = Move.fromChessMove(chessMove, gs)
                    # print(f"made a move from list:{move.getChessNotation()}")
                    gs.makeMove(move)
                    moveMade = True
                    animate = False
                    validMoves = gs.stdValidMoves()
                    update = True


            
            if currentMove < len(moves):
                ucimove = moves[currentMove]
                currentMove += 1
                chessMove:Optional[chess.Move] = chess.Move.from_uci(ucimove)
                move:Optional[Move] = Move.fromChessMove(chessMove, gs)
                # print(f"made a move from list:{move.getChessNotation()}")
                gs.makeMove(move)
                moveMade = True
                animate = True
                validMoves = gs.stdValidMoves()
                update = True

            if engineMove > 0:
                update = True
                # make a move choosen by the engine
                chessmove:Optional[chess.Move] = UCIEngines.bestMove(gs.board(),  time=1.0)
                move:Optional[Move] = Move.fromChessMove(chessmove, gs)
                if move is None:
                    moveMade = False
                    validMoves=[]
                    mustSkip=True
                else:
                    gs.makeMove(move)
                    moveMade = True
                    animate = True
                    validMoves = gs.stdValidMoves()
                    engineMove = engineMove-1

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
                        # play_position = 1
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Nasconde aiuto quando il tasto destro è rilasciato
                        show_help = False
                elif e.type == p.MOUSEBUTTONDOWN and e.button == 1 and not humanCanPlay and not toolbar.pointer_in_toolbar(e.pos):
                    # Solo click sinistro skippa al prossimo esercizio. Senza
                    # `button==1` la rotellina del mouse (button 4/5 in pygame)
                    # farebbe saltare di posizione mentre l'utente guarda la
                    # continuazione.
                    mustSkip = True
                    break
                elif e.type == p.MOUSEBUTTONDOWN and not gameOver and humanCanPlay and not toolbar.pointer_in_toolbar(e.pos):
                    row, col = BS.getRowColFromLocation(p.mouse.get_pos())

                    if sqSelected == (row, col) or col >= 8 or row>=8: # user clicked same square or in move log
                        sqSelected = ()
                        playerClicks = []
                    else:
                        sqSelected = (row, col)
                        playerClicks.append(sqSelected)

                    if len(playerClicks) == 2:
                        # do the move if two squares has been selected and the move is valid
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
                            updateStats = True
                        else:
                            sqSelected = (row, col)
                            playerClicks = [sqSelected]
                    if len(playerClicks) == 1 and gs.colorAt(row, col) != gs.colorToMove():
                        sqSelected = ()
                        playerClicks = []

                elif e.type == p.KEYDOWN:

                    if e.key == p.K_c:
                        # copy position to clibboard
                        glc.copy_to_clipboard(gs.node.board().fen(), "Position copied to clipboard", gs)

                    if e.key == p.K_g:
                        # copy position to clibboard
                        glc.copy_to_clipboard(pos.to_PgnString(), "Game copied to clipboard", gs)

                    if e.key == p.K_LESS and (e.mod & p.KMOD_SHIFT):
                        BS.setFactor( BS.getFactor()*1.2)

                    if e.key == p.K_LESS and ((e.mod & p.KMOD_SHIFT) == 0):
                        BS.setFactor( BS.getFactor() / 1.2)

                    if e.key == p.K_e:  # Engine on /off
                        glc.toggle_engine(gs)

                    if e.key == p.K_q:
                        running = False

                    if e.key == p.K_b:
                        glc.toggle_book(gs)

                    if e.key == p.K_d:
                        glc.toggle_pgn(gs)

                    if e.key == p.K_KP_PLUS and not humanCanPlay:
                        engineMove += 2

                    if e.key == p.K_n and not humanCanPlay:
                        mustSkip = True
                        break

                    if e.key == p.K_h and not updateStats:  # Mostra la soluzione
                        if solution:
                            show_message(gs, f"Solution: {solution}")
                            app.delay(2)
                

            
            toolbar.update(time_delta)

            if show_help:
                do_show_help()
                continue

            if not update:
                # Frame idle: ridisegniamo la toolbar (per i tooltip on-hover) e flippiamo.
                toolbar.draw(app.screen)
                p.display.update()
                continue

            if moveMade and not mustSkip:
                moveMade = False
                # Se l'analisi e' attiva, aggancia la nuova posizione (no-op se off).
                UCIEngines.update_board(gs.board(), glc.engine_callback)
                # Guard difensivo: in teoria se moveMade era True ci dovrebbe
                # essere stata una makeMove e moveLog non sarebbe vuoto, ma e'
                # capitato in passato (vedi reset di moveMade sopra). Saltiamo
                # l'animazione invece di crashare.
                lastMove = gs.moveLog[-1] if gs.moveLog else None
                if animate and lastMove is not None:
                    BS.animateMove(lastMove, app.screen, gs)
                    app.delay(0.1)
                    animate = False

                if updateStats:
                    if AN.updateInfoStats(gs.node.board(), learningBase):
                        msg = "Right"

                        if not isNewPosition:
                            # print(f"currentElement is {currentElement}, len of numberOfErrors is {len(numberOfErrors)}")
                            numberOfErrors[currentElement] -= 1
                            if numberOfErrors[currentElement] == 0 or pos.skip == "S":
                                del numberOfErrors[currentElement]
                                del errorsMade[currentElement]
                                msg = "Position solved"

                        show_message(gs,msg)
                        app.delay(1 )

                        engineMove = state.num_moves_to_show
                        humanCanPlay = False
                    else:
                        show_message(gs,"Not the right move")
                        app.delay(1 )
                        gs.undoMove()
                        validMoves = gs.stdValidMoves()
                        if isNewPosition:
                            # print(f"wrong move, appending new error position")
                            currentElement = len(errorsMade)
                            errorsMade.append(pos)
                            numberOfErrors.append(config.correctsToLearn)
                            isNewPosition = False

                        else:
                            # print(f"wrong move, setting n.of error = correctsToLearn")
                            numberOfErrors[currentElement] = config.correctsToLearn

            # Highlight squares when needed
            if currentMove >= len(moves) and engineMove == 0:
                toHighlightSquares = []
                toHighlightCircle = []

                if len(playerClicks) == 1:
                    # if a square has been selected, highlith possible piece targets
                    mm = [m for m in validMoves if m.startRow == sqSelected[0] and m.startCol == sqSelected[1]]
                    toHighlightCircle = [(m.stopRow, m.stopCol, CIRCLE_COLOR) for m in mm]

                if len(playerClicks) == 0 and len(gs.moveLog) > 0:
                    # at the the start of a move, previous move is hightlighted
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
    app.main_menu.enable()
