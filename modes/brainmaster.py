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
from modes.board_session import BoardSession, ModePolicy
import UCIEngines
import BoardScreen as BS
from toolbar import Toolbar, ToolbarAction
import analyzer
from config import config
import BrainMaster
from BrainMaster import AnswerData, QuestionData, give_answers, ask_for_quiz, unlock_new_lesson
import Quiz
import pgngamelist
from LearningBase import LearningBase, LearnPosition, learningBases
from save_load import save_menu, load_menu
from modes.common import show_message, setAlfa


# Study a set of positions of a course, suggested by the BrainMaster module, until they are all solved
def playBrainMasterBase():
    if state.id_course is None :
        text = "Please select a Course first"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2)
        return
    playBrainMaster(state.id_course)
    return


@dataclass
class MistakenPosition:   
    pass
    

@dataclass
class LearnPositionSimplified:
    fen: str
    ok: str
    moves: str
    eco: str
    gamedate: date
    id_question: str
    id_test:str
    id_lesson:str
    zobrist: int
    move:str
    @staticmethod
    def fromQuestionData(pos):
        movelist = pos["question"]
        moves = movelist.split() if movelist else []
        FEN = "X "
        if len(moves) % 2 == 0:
            FEN += "w "
        else:
            FEN += "b "

        return LearnPositionSimplified(
            fen=FEN,
            ok=pos["rightAnswer"],
            moves=pos["question"],
            move=pos["rightAnswer"],
            eco='none',
            id_lesson=pos["id_lesson"],
            id_test=pos["id_test"],
            gamedate=date.today(),
            id_question=pos["id_question"],
            zobrist=pos["id_question"]
        )

# play a set of positions suggested by the BrainMaster module, until they are all solved
def playBrainMasterSet(questions: List[QuestionData])->Dict[str, AnswerData] :
    '''
    Ask a set of positions until each one is solved. A position is solved when it is correctly answered 3 times
     in a row after a mistake, or correctly answered the first time.
    '''
    ll:List[LearnPositionSimplified]= []
    result: Dict[str, AnswerData] = {}

    BS.set_context_label(f"BrainMaster: {state.id_course or '?'}")

    # ll is a copy (not a deep copy) of data in the LearningBase
    for q in questions:
        ll.append(LearnPositionSimplified.fromQuestionData(q))

    running = True
    sqSelected = ()
    playerClicks = []
    moveMade = False
    animate = False
    gameOver = False
    errorsMade = {}  # tells how many mistakes for every position minus good answers
    
    if len(ll)==0:
        text = "No positions found"
        BS.drawEndGameText(app.screen, None, text)
        app.delay(2 )

    help_text = [
            "Instructions:",
            "- Q to quit",
            "- C Copy FEN to clipboard",
            "- G Copy PGN to clipboard", 
            "- + show more moves",
            "- H show the solution" ,
            "- E Engine ON/OFF",
            "- B show/hide book", 
            "- D show/hide moves"
        ]
    show_help = False

    start_stamp = None
    # show_cpu must follow the engine's real state, otherwise if the analysis
    # was left active the CPU panel stays empty while the engine is running.
    BS.show_cpu = UCIEngines.is_analysing()
    BS.clearCPU(app.screen)

    # Toolbar (phase 2): same pattern as the other modes.
    def _post_key(key, mod=0):
        return lambda: p.event.post(p.event.Event(p.KEYDOWN, key=key, mod=mod))
    toolbar = Toolbar([
        ToolbarAction("Sol",   "Show solution (H) -- before you answer",  _post_key(p.K_h),
                      enabled=lambda: not isNewPosition),
        ToolbarAction("+Mov",  "Show more continuation moves (+) -- after correct answer",
                                                                          _post_key(p.K_KP_PLUS),
                      enabled=lambda: not humanCanPlay),
        ToolbarAction("Next",  "Next question (N) -- after you answer",   _post_key(p.K_n),
                      enabled=lambda: not updateStats),
        ToolbarAction("Eng",   "Engine on/off (E)",                       _post_key(p.K_e)),
        ToolbarAction("Book",  "Toggle opening book (B)",                 _post_key(p.K_b)),
        ToolbarAction("Moves", "Toggle PGN move list (D)",                _post_key(p.K_d)),
        ToolbarAction("C-FEN", "Copy FEN to clipboard (C)",               _post_key(p.K_c)),
        ToolbarAction("C-PGN", "Copy PGN to clipboard (G)",               _post_key(p.K_g)),
        ToolbarAction("Quit",  "Quit to menu (Q)",                        _post_key(p.K_q)),
    ])

    def do_show_help():
        glc.draw_help_overlay(help_text, height=300)

    while (len(ll) > 0) and running:
        
        pos = ll.pop(0)
        curr_zobrist= str(pos.zobrist)

        isNewPosition = False

        curr_data = None

        if curr_zobrist in result:
            curr_data = result[curr_zobrist]
        else:
            curr_data =  AnswerData(datetime.now(), curr_zobrist, 1, 0,0)
            result[curr_zobrist]=curr_data       
            isNewPosition = True
            errorsMade[curr_zobrist] = 0

        fen = pos.fen.split()
        header = ["id_lesson:"+pos.id_lesson, "id_test:"+pos.id_test]
        
        if pos.ok != pos.move:
            header.append("mistake was " + pos.move)

        moves = pos.moves.split()
        gs = GameState()
        gs.setHeader(header)

        # Free-play board core (same as play_game/replay): the base ModePolicy is
        # inert (no judging, no auto-flip) -- this mode owns the rules in the loop.
        # The session SHARES this gs, so clicks mutate the same object.
        session = BoardSession(ModePolicy(), gs=gs)
        #gs.setFen(pos["fen"])
        #BS.setWhiteUp(app.screen, not gs.whiteToMove())
        BS.setWhiteUp(app.screen, fen[1] == "b")
        BS.drawGameState(app.screen, gs, [], [], ())
        BS.update()
        solution = pos.ok

        currentMove = 0
        validMoves = gs.stdValidMoves()
        engineMove = 0
        mustSkip = False        # mustSkip determines the exit from the cycle
        humanCanPlay = True

        last_stamp= datetime.now()

        while running and not mustSkip:
            time_delta = app.clock.tick(60) / 1000.0   # pace + dt for the toolbar
            UCIEngines.poll()  # drain the engine info (no-op if analysis off)
            updateStats = False
            update = False

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
                    update=True

            if currentMove < len(moves):
                ucimove = moves[currentMove]
                currentMove += 1
                chessMove:Optional[chess.Move] = chess.Move.from_uci(ucimove)
                move:Optional[Move] = Move.fromChessMove(chessMove, gs)
                # print(f"made a move from list:{move.getChessNotation()}")
                gs.makeMove(move)
                last_stamp= datetime.now()               
                moveMade = True
                animate = True
                validMoves = gs.stdValidMoves()
                update=True

            if engineMove > 0:
                update=True
                # make a move choosen by the engine
                chessmove:Optional[chess.Move] = UCIEngines.bestMove(gs.board(),  time=1.0)
                move:Optional[Move] = Move.fromChessMove(chessmove, gs)
                if move is None:
                    engineMove = 0
                    moveMade = False
                    validMoves = []
                    mustSkip= True
                else:
                    gs.makeMove(move)
                    last_stamp= datetime.now()
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
                        # Show help when the right button is pressed
                        show_help = True
                        #play_position = 1
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Hide help when the right button is released
                        show_help = False
                elif e.type == p.MOUSEBUTTONDOWN and e.button == 1 and not humanCanPlay and not toolbar.pointer_in_toolbar(e.pos):
                    # Only a left click skips: the mouse wheel (button 4/5) does NOT.
                    mustSkip = True
                    update=True
                    break
                elif e.type == p.MOUSEBUTTONDOWN and not gameOver and humanCanPlay and not toolbar.pointer_in_toolbar(e.pos):
                    update=True
                    row, col = BS.getRowColFromLocation(p.mouse.get_pos())
                    # Click -> move delegated to the BoardSession (free play, like
                    # replay): same selection + promotion handling from the tested
                    # core. The selection is mirrored back for the renderer; this
                    # mode's own judging (updateStats) then runs on the move made.
                    moved = session.click(row, col,
                                          ask_promotion=lambda color: BS.choosePromotion(app.screen, color))
                    sqSelected = session.selected if session.selected is not None else ()
                    playerClicks = [session.selected] if session.selected is not None else []
                    validMoves = session.validMoves
                    if moved is not None:
                        moveMade = True
                        animate = True
                        updateStats = True

                elif e.type == p.KEYDOWN:
                    update=True
                    if e.key == p.K_LESS and (e.mod & p.KMOD_SHIFT):
                        BS.setFactor( BS.getFactor()*1.2)

                    if e.key == p.K_LESS and ((e.mod & p.KMOD_SHIFT) == 0):
                        BS.setFactor( BS.getFactor() / 1.2)

                    if e.key == p.K_c:
                        # copy position to clibboard
                        glc.copy_to_clipboard(gs.node.board().fen(), "Position copied to clipboard", gs)

                    if e.key == p.K_g:
                        # copy position to clibboard
                        glc.copy_to_clipboard(pos.to_PgnString(), "Game copied to clipboard", gs)

                    if e.key == p.K_e:  # Engine on /off
                        glc.toggle_engine(gs)

                    if e.key == p.K_KP_PLUS and not humanCanPlay:
                        engineMove += 2
                    
                    if e.key == p.K_b:
                        glc.toggle_book(gs)

                    if e.key == p.K_d:
                        glc.toggle_pgn(gs)

                    if e.key == p.K_q:
                        running = False

                    if e.key == p.K_n and not updateStats:
                        mustSkip = True
                        break

                    if e.key == p.K_h and not isNewPosition:  # Show the solution but not if it is still being solved
                        if solution:
                            show_message(gs, f"Solution: {solution}")                            
                            app.delay(2 )

            
            toolbar.update(time_delta)

            if show_help:
                do_show_help()
                continue

            if not update:
                # Idle frame: redraw the toolbar (for the tooltips) and flip.
                toolbar.draw(app.screen)
                p.display.update()
                continue
            if moveMade and not mustSkip:
                moveMade = False
                # If the analysis is active, attach the new position (no-op if off).
                UCIEngines.update_board(gs.board(), glc.engine_callback)
                lastMove = gs.moveLog[-1]
                stop_stamp = datetime.now()

                if animate:
                    BS.animateMove(lastMove, app.screen, gs)

                    p.time.delay(100)
                    animate = False
                
                if updateStats:
                    updateStats=False

                    if lastMove.move.uci()==pos.ok:
                        msg = "Right"                                                
                        if isNewPosition: # 
                            app.delay(1 )
                            curr_data.timeElapsed = (stop_stamp-last_stamp).total_seconds()
                            curr_data.result = 1
                            

                        if not isNewPosition:
                            curr_data.notesTime += (stop_stamp-last_stamp).total_seconds()
                            
                            errorsMade[curr_zobrist] -= 1
                            if errorsMade[curr_zobrist] <= 0:
                                BS.drawGameState(app.screen, gs, toHighlightCirclesColor=[],
                                 toHighlightSquareColor=[],
                                 sqSelected=sqSelected)
                                msg  =  "Position solved"
                            else:
                                ll.append(pos)

                        show_message(gs, msg)
                        app.delay(1 )

                        engineMove = state.num_moves_to_show
                        humanCanPlay = False
                    else:                        
                        errorsMade[curr_zobrist]=3
                        curr_data.result -= 1  # 1-> 0, 0->-1  ...
                        # print(f"{curr_zobrist} errored {curr_data.result}")
                        if isNewPosition:  
                            curr_data.timeElapsed = (stop_stamp-last_stamp).total_seconds()                            
                        else:
                            curr_data.notesTime += (stop_stamp-last_stamp).total_seconds()
                        gs.undoMove()
                        show_message(gs, "Right move is "+pos.ok)
                        app.delay(3 )
                        validMoves = gs.stdValidMoves()
                        isNewPosition = False
                        

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
    UCIEngines.stop_analysis()
    app.main_menu.enable()
    return result

# Study a course from the BrainMaster module, eventually unlocking new lessons and playing quizzes
def playBrainMaster(learningBaseName:str):

    # Clean state for the E toggle: if a previous mode had left
    # the analysis active, the first E here would end up in the "stop" branch
    # instead of starting it.
    UCIEngines.stop_analysis()

    # Lazy registration with the BrainMaster service: only now that the user is
    # actually entering BrainMaster (never at startup). The open list_courses
    # works without it, but the student endpoints below need credentials.
    if not BrainMaster.ensure_registered():
        app.main_background()
        msg = ("Set the BrainMaster service URL (base_url) in Tools -> Setup"
               if not config.base_url
               else "Could not register with the BrainMaster service")
        BS.drawEndGameText(app.screen, None, msg, size=20)
        BS.update()
        app.delay(2)
        return

    #eventually unlocks new lessons
    app.main_background()
    BS.drawEndGameText(app.screen,None, "Checking lessons to unlock",size=20)
    BS.update()

    res = unlock_new_lesson(learningBaseName)
    if res:
        app.main_background() 
        BS.drawEndGameText(app.screen, None,f"New lesson unlocked:{res}",size=20)
        BS.update()
        app.delay(2 )

    app.main_background() 
    BS.drawEndGameText(app.screen, None,"Acquiring test",size=20)
    BS.update()
    suggestion = ask_for_quiz(learningBaseName, config.id_student)
    
    app.main_background() 
    if suggestion is None:
        app.main_background() 
        BS.drawEndGameText(app.screen, None,"Error accessing the BrainMaster service",size=20)
        BS.update()
        app.delay(2 )
        return
    action = suggestion.get("action")
    if action is None:
        # No quiz right now: the server replied {"error": ...} (HTTP 200), e.g.
        # nothing left to review for this course. Show a clear message rather than
        # the generic "service error" handled above.
        app.main_background()
        BS.drawEndGameText(app.screen, None,
                           "No test to practice right now for this course", size=20)
        BS.update()
        app.delay(2 )
        return
    for q in suggestion["questions"]:
        # print id_question, id_test, id_lesson for each question (with labels)
        print(
            f"Question: {q['id_question']}, Test: {q['id_test']}, Lesson: {q['id_lesson']}")
        
         

    questions:List[dict] = [q for q in suggestion["questions"]]
    results = playBrainMasterSet(questions)
    count = sum(1 for item in results.values() if item.result == 1)
    total = len(results)
    msg = f"Number of correct answers: {count} over {total}"
    app.main_background() 
    BS.drawEndGameText(app.screen, None, msg,size=20)
    BS.update()

    give_answers(learningBaseName, action, list(results.values()))
