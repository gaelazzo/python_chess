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
import analyzer
import BrainMaster
from BrainMaster import AnswerData, QuestionData, give_answers, ask_for_quiz, unlock_new_lesson
import Quiz
import pgngamelist
from LearningBase import LearningBase, LearnPosition, learningBases
from save_load import save_menu, load_menu
from modes.common import show_message, setAlfa


# play a game from a pgn file, with the player playing the best move and the computer playing one of the lines stored in the game
def playModels():

    if positionParameters["filename"] is None:
        return

    app.main_menu.disable()
    app.main_menu.full_reset()
    playModelFiles( positionParameters["filename"],  positionParameters["color"])
    return

def playModelFiles(filename, humanColor):
    '''
        Play a random game from a file, and the player must always play the best move, while the computer plays one of the
          available lines stored in the game.
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
    

    while running:
        gs = GameState()
        game = gamelist.chooseRandomGame()
        gs.setPgn(game)      

        if state.play_position:
            # skip all stored moves until a leaf node is reached
            moreMoves = True
            move = None
            while moreMoves:
                playerTurn = gs.colorToMove() == humanColor    

                if playerTurn:
                    moreMoves = gs.doNextMainMove()
                    if random.randint(1, 3) == 1:
                        break
                else:
                    move = gs.makeNextMove()
                    moreMoves = move is not None
            # takes back last move
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
            humanCanPlay = gs.colorToMove() == humanColor
            checkMove = False
            nextMove = gs.getNextMainMove()
            update= False
            if nextMove is None or stopCondition:  # game is over anyway
                text = "Solved"
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
                update = True
                if e.type == p.QUIT:
                    running = False
                elif e.type == p.MOUSEBUTTONDOWN and gameOver:
                    mustSkip = True
                    break
                elif  e.type == p.MOUSEBUTTONDOWN and e.button == 3:
                        # Mostra aiuto quando il tasto destro è premuto
                        show_help = True         
                        # play_position = 1
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Nasconde aiuto quando il tasto destro è rilasciato
                        show_help = False                        
                elif e.type == p.MOUSEBUTTONDOWN and not gameOver and humanCanPlay:

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
                        whiteUp = not whiteUp
                        moveMade = True
                        animate = False
               
            if not update:
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

            BS.update()

    p.event.clear()
    UCIEngines.stop_analysis()
    app.main_menu.enable()
