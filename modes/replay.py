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

    

    # ll is a copy (not a deep copy) of data in the csv, not the same structure
    ll = analyzer.getRandomPositions(learningBase, positionParameters)

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
        header = ["White:"+pos.white, "Black:"+pos.black, "ECO:"+pos.eco, "Date:"+pos.gamedate.strftime('%d-%m-%Y')]
        # header.append("game number:"+ playParameters["gameid"])
        if pos.ok != pos.move:
            header.append("mistake was " + pos.move)



        moves = pos.moves.split()
        gs = GameState()
        gs.setHeader(header)
        #gs.setFen(pos["fen"])
        #BS.setWhiteUp(app.screen, not gs.whiteToMove())
        BS.setWhiteUp(app.screen, fen[1] == "b")
        BS.drawGameState(app.screen, gs, [], [], ())
        BS.update()
        solution = pos.ok
        BS.show_cpu = False

        currentMove = 0
        validMoves = gs.stdValidMoves()
        engineMove = 0
        mustSkip = False        # mustSkip determines the exit from the cycle
        humanCanPlay = True
        
       

        while running and not mustSkip:
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
                elif e.type == p.MOUSEBUTTONDOWN and not humanCanPlay:
                    mustSkip = True
                    break
                elif e.type == p.MOUSEBUTTONDOWN and not gameOver and humanCanPlay:
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
                

            
            if show_help:
                do_show_help()
                continue

            if not update:
                continue

            if moveMade and not mustSkip:
                moveMade = False
                lastMove = gs.moveLog[-1]
                if animate:
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

            BS.update()

    p.event.clear()
    app.main_menu.enable()
