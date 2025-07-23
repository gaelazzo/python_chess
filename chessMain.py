"""
Main driver file

"""
from ast import Dict
from collections.abc import Callable
import os.path
import random
from typing import Optional
from Board import Move,GameState
import pygame as p
import json
import BrainMaster
from LearningBase import LearningBase, LearnPosition, learningBases
import UCIEngines
import BoardScreen as BS
import analyzer
import analyzer as AN
import chess
import pygame_menu
import random
import pyperclip
import pygame_gui
from pygame_gui.windows.ui_file_dialog import UIFileDialog
import gamereader
from pygame_gui.elements.ui_button import UIButton
import sys
import UCIEngines
from dataclasses import dataclass
from BrainMaster import AnswerData, QuestionData, give_answers, ask_for_quiz, unlock_new_lesson
from typing import Optional, Union,List,Dict, Tuple, Iterator
from datetime import datetime, date
import os
import Quiz
import chess_com_download
from config import config, load_config, save_config


FPS = 60

manager = None
screen  = None
W = None
H = None

timeFactor = 500.0

def delay(unit: float) -> None:
    p.time.delay(int(unit * timeFactor))

def main_background() -> None:
    """
    Function used by menus, draw on background while menu is active.
    :return: None
    """
    global screen
    screen.fill(p.Color("white"))



playParameters = {
    "whiteCPU": False,
    "blackCPU": True,
    "elo": None,
    "elomax": True
}


positionParameters = {
    "eco": None,
    "color": "w",
    "filename": None,
    "base":"openings",
    "player":None,
    "movesToAnalyze":16,
    "blunderValue":80 ,
    "ponderTime": 0.5,
    "useBook": False,
    "filename": ""

}

num_moves_to_show = 4

def make_updater(key, cast_type, target_dict=None, validator=None, target_module=None):
    def updater(value):
        try:
            if cast_type == str:
                casted = value if value != "" else None
            else:
                casted = cast_type(value)

            if validator is not None and not validator(casted):
                return

            if target_dict is not None:
                target_dict[key] = casted
            else:
                mod = target_module or sys.modules[__name__]
                setattr(mod, key, casted)                
        except (ValueError, TypeError):
            pass
    return updater


def make_selector_updater(key, target_dict=None):
    def updater(value, _index):
        selected_value = value[0][1]
        if target_dict is not None:
            target_dict[key] = selected_value
        else:
            globals()[key] = selected_value
    return updater

def make_selector_updater_mapped(key, target_dict, value_map):
    def updater(selection, index):
        # Il valore del selector è nella forma: [(etichetta, valore_selettore)]
        selected_value = selection[0][1]
        mapped_value = value_map.get(selected_value)

        if target_dict is None:
            # Se target_dict è None, il "key" è una variabile globale da aggiornare direttamente
            globals()[key] = mapped_value
        else:
            target_dict[key] = mapped_value
    return updater


def make_bool_selector_updater(key, target_dict):
    return make_selector_updater_mapped(key, target_dict, {1: True, 0: False})


'''
 1 if skip playing initial moves, 0 if play all moves
'''
play_position = 1  

COLOR_MAP = {
    0: "w",
    1: "b",
    2: None
}
REVERSE_COLOR_MAP = {v: k for k, v in COLOR_MAP.items()}


def getCurrentColorIndex():
    if positionParameters["color"] == "w":
        return 0
    if positionParameters["color"] == "b":
        return 1
    return 2


def setPlayColor(color,index):
    myColor = color[0][0]
    if myColor == "Random":
        myColor = random.choice(["White", "Black"])
    playParameters["whiteCPU"] = myColor == "Black"
    playParameters["blackCPU"] = myColor == "White"

def make_file_selector(
    key: str,
    fileNameTranformer: Optional[Callable[[str], str]] ,
    labels: List,
    initial_folder: str = ".",
    file_type: str = ".json",
    window_title: str = "Select file",
    callback: Optional[Callable] = None,
    prefix: str = "",
):
    def choose_file():
        global manager, screen, W, H, clock
        background = p.Surface((W, H))
        background.fill(p.Color('#000000'))

        file_selection = UIFileDialog(
            rect=p.Rect(0, 0, W, H),
            manager=manager,
            allow_existing_files_only=True,
            window_title=window_title,
            initial_file_path=initial_folder,
            allowed_suffixes=[file_type],
            allow_picking_directories=False
        )
        
        while True:
            time_delta = clock.tick(60) / 1000.0

            for event in p.event.get():
                if event.type == p.QUIT:
                    quit()
                if event.type == p.WINDOWCLOSE or event.type == pygame_gui.UI_WINDOW_CLOSE:
                    return

                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    if event.ui_element == file_selection.ok_button:
                        selected = file_selection.current_file_path
                        file_name_with_ext  = os.path.basename(selected)
                        file_name, file_extension = os.path.splitext(file_name_with_ext) # <-- NUOVO

                        if prefix and not file_name.startswith(prefix):
                             # Il file non è valido: mostriamo un messaggio e non usciamo
                            # print(f"Errore: Il file '{file_name}' non inizia con 'base_'. Seleziona un file valido.")
                            # Potresti anche visualizzare un messaggio popup all'utente
                            # ad esempio con pygame_gui.windows.UIMessageWindow
                            pygame_gui.windows.UIMessageWindow(
                                html_message=f"The selected file is not valid:<br><b>{file_name}</b><br>it must start with {prefix}.",
                                window_title="Invalid file selection",
                                manager=manager,
                                rect=p.Rect(W // 4, H // 4, W // 2, H // 2) # Posizione e dimensione del popup
                            )     
                            continue


                        file_name = fileNameTranformer(file_name) if fileNameTranformer else file_name
                        positionParameters[key] = file_name

                        for label in labels:
                            if label:
                                label.set_title(selected)

                        if callback:
                            callback(selected)

                        return
                    elif event.ui_element == file_selection.cancel_button:
                        return

                manager.process_events(event)

            manager.update(time_delta)
            screen.blit(background, (0, 0))
            manager.draw_ui(screen)
            p.display.update()

    return choose_file






def show_message(gs:GameState, text:str):
    global screen
    BS.drawEndGameText(screen, gs, text)
    


CIRCLE_COLOR = (15, 50, 180, 90)




def setEloMax(value):
    playParameters["elomax"] = value

def setPlayElo(value):
    playParameters["elo"] = int(value)

def humanPlay():
    playParameters["whiteCPU"]=False
    playParameters["blackCPU"] = False
    playGame()




WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
myfont:p.Font

def setPositionEco(current_text, **kwargs):
    global openingParameters
    if current_text == "":
        positionParameters["eco"] = None
    else:
        positionParameters["eco"] = current_text.upper()

def setPlayer(current_text, **kwargs):
    global openingParameters
    if current_text == "":
        positionParameters["player"] = None
    else:
        positionParameters["player"] = current_text


def playGame():
    global main_menu
    main_menu.disable()
    main_menu.full_reset()
    playAGame()


def playAGame():
    global screen
    gs:Optional[GameState] = GameState()
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
    whiteCPU = playParameters["whiteCPU"]
    blackCPU = playParameters["blackCPU"]

    if whiteCPU and not blackCPU:
        BS.setWhiteUp(screen, True)

    help_text = [
            "Istruzioni:",
            "- Z o freccia sinistra per ritirare la mossa",
            "- Q per uscire",
            "- C copia la posizione FEN nella clipboard",
            "- S valuta la posizione ",
            "- F flip board",
            "- R reset"
        ]
    show_help = False

    while running:

        if not gameOver and \
                ((gs.whiteToMove() and whiteCPU) or (blackCPU and not gs.whiteToMove())):
            engine_move:Optional[chess.Move] = UCIEngines.bestMove(gs, validMoves, elo=elo)  #validMoves is not used at the moment
            if engine_move is not None:
                move:Optional[Move] = Move.fromChessMove(engine_move, gs)
                gs.makeMove(move)
                moveMade = True # a move was made
                animate = True  # move must be showed
                validMoves = gs.stdValidMoves() # recalculate valid moves

        else:
            for e in p.event.get():
                if e.type == p.QUIT:
                    running = False
                elif  e.type == p.MOUSEBUTTONDOWN and e.button == 3:
                        # Mostra aiuto quando il tasto destro è premuto
                        show_help = True            
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Nasconde aiuto quando il tasto destro è rilasciato
                        show_help = False
                elif e.type == p.MOUSEBUTTONDOWN  and e.button == 1 and not gameOver:
                    #tak
                    row,col = BS.getRowColFromLocation(p.mouse.get_pos())

                    if sqSelected == (row, col) or col >= 8:  # user clicked same square or in move log
                        sqSelected = ()
                        playerClicks = [] # reset the sequence of selections
                    else:
                        sqSelected = (row, col) # new current selected square
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
                                piece = BS.choosePromotion(screen, move.pieceMoved[0])
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
                    if e.key == p.K_z or e.key == p.K_LEFT:
                        gs.undoMove()
                        validMoves = gs.stdValidMoves()
                        moveMade = True
                        animate = False
                        gameOver = False

                    if e.key == p.K_q:
                        #quit
                        running = False

                    if e.key == p.K_c:  # copy to clipboard
                        pyperclip.copy(BS.board.fen())
                        text = "Position copied to clipboard"
                        show_message(gs, text)
                        delay(2)
                        running = False

                    if e.key == p.K_s:  # evaluate score
                        gs.setEvaluation(analyzer.evaluatePosition(gs.board, 5))

                    if e.key == p.K_f:
                        BS.flipBoard(screen)
                        moveMade = True
                        animate = False

                    if e.key == p.K_r:
                        gs = GameState()
                        sqSelected = ()
                        playerClicks = []
                        validMoves = gs.stdValidMoves() #evaluate the new list of valid moves
                        gameOver = False
                        moveMade = False
                        animate = False

        if show_help:
                    p.draw.rect(screen, GRAY, (50, 50, 600, 300))
                    p.draw.rect(screen, BLACK, (50, 50, 600, 300), 2)

                    for i, line in enumerate(help_text):
                        text = myfont.render(line, True, BLACK)                        
                        screen.blit(text, (60, 60 + i * 30))
                    p.display.flip()
                    continue
                    
        if moveMade:
            moveMade = False
            if animate:
                BS.animateMove(gs.moveLog[-1], screen, gs)
                animate = False
            if not whiteCPU and not blackCPU:
                BS.flipBoard(screen)

        gameOver = gs.checkMate() or gs.staleMate()

        if gameOver:
            BS.drawGameState(screen, gs, [], [], ())
            if gs.checkMate():
                text = "Black wins by CheckMate" if gs.colorToMove() == "w" else "White wins by CheckMate"
                # textsurface = myfont.render('Checkmate', False, p.Color("red"))
            else:
                text = "Stalemate"
            show_message(gs, text)            
            delay(2 )
            running = False
            # textsurface = myfont.render('Stalemate', False, p.Color("red"))
            # screen.blit(textsurface, (200, 100))

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

            BS.drawGameState(screen, gs, toHighlightCirclesColor= toHighlightCircle,
                             toHighlightSquareColor=toHighlightSquares,
                             sqSelected=sqSelected)

        BS.update()

    main_menu.enable()


def setAlfa(color, alfa):
    return [color[0],color[1],color[2], alfa]



def replayBase():
    global main_menu
    main_menu.disable()
    main_menu.full_reset()
    replayBadPositions(learningBases[positionParameters["base"]])
    return

def playBrainMasterBase():
    playBrainMaster(positionParameters["base"])
    return


@dataclass
class MistakenPosition:   
    pass
    


def playBrainMasterSet(learningBase:LearningBase, questions: List[QuestionData])->Dict[str, AnswerData] :
    '''
    Ask a set of positions until each one is solved. A position is solved when it is correctly answered 3 times
     in a row after a mistake, or correctly answered the first time.
    '''
    global  screen
    positions  = learningBase.positions
    ll:List[LearnPosition]= []
    result: Dict[str, AnswerData] = {}
    
    
    # ll is a copy (not a deep copy) of data in the LearningBase
    for q in questions:
        ll.append(positions[int(q.id_question)])

    running = True
    sqSelected = ()
    playerClicks = []
    moveMade = False
    animate = False
    gameOver = False
    errorsMade = {}  # tells how many mistakes for every position minus good answers
    
    
    
    if len(ll)==0:
        text = "No positions found"
        show_message(gs, text)
        delay(2 )

    help_text = [
            "Istruzioni:",
            "- Q per uscire",
            "- C copia la posizione FEN nella clipboard",
            "- G copia le mosse come PGN nella clipboard", 
            "- S valuta la posizione ",
            "- R reset",
            "- + vedi altre mosse",
            "- H mostra la soluzione"  
        ]
    show_help = False

    start_stamp = None

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
        header = ["White:"+pos.white, "Black:"+pos.black, "ECO:"+pos.eco, "Date:"+pos.gamedate.strftime('%d-%m-%Y')]
        if pos.ok != pos.move:
            header.append("mistake was " + pos.move)



        moves = pos.moves.split()
        gs = GameState()
        gs.setHeader(header)
        #gs.setFen(pos["fen"])
        #BS.setWhiteUp(screen, not gs.whiteToMove())
        BS.setWhiteUp(screen, fen[1] == "b")
        BS.drawGameState(screen, gs, [], [], ())
        BS.update()
        solution = pos.ok

        currentMove = 0
        validMoves = gs.stdValidMoves()
        engineMove = 0
        mustSkip = False        # mustSkip determines the exit from the cycle
        humanCanPlay = True

        last_stamp= datetime.now()

        while running and not mustSkip:
            updateStats = False
            
            if play_position:
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

            if engineMove > 0:
                # make a move choosen by the engine
                chessmove:Optional[chess.Move] = UCIEngines.bestMove(gs, validMoves, time=1.0)
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
                if e.type == p.QUIT:
                    running = False            
                elif  e.type == p.MOUSEBUTTONDOWN and e.button == 3:
                        # Mostra aiuto quando il tasto destro è premuto
                        show_help = True            
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Nasconde aiuto quando il tasto destro è rilasciato
                        show_help = False
                elif e.type == p.MOUSEBUTTONDOWN and not humanCanPlay:
                    mustSkip = True
                    break
                elif e.type == p.MOUSEBUTTONDOWN and not gameOver and humanCanPlay:
                    row, col = BS.getRowColFromLocation(p.mouse.get_pos())

                    if sqSelected == (row, col) or col >= 8:  # user clicked same square or in move log
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
                                piece = BS.choosePromotion(screen, move.pieceMoved[0])
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
                    if e.key == p.K_LESS and (e.mod & p.KMOD_SHIFT):
                        BS.setFactor( BS.getFactor()*1.2)

                    if e.key == p.K_LESS and ((e.mod & p.KMOD_SHIFT) == 0):
                        BS.setFactor( BS.getFactor() / 1.2)

                    if e.key == p.K_c:
                        # copy position to clibboard
                        pyperclip.copy(gs.board.fen())
                        text = "Position copied to clipboard"
                        show_message(gs, text)
                        delay(2)

                    if e.key == p.K_g:
                        # copy position to clibboard
                        pyperclip.copy(pos.to_PgnString())
                        text = "Game copied to clipboard"
                        show_message(gs, text)
                        delay(2)

                    if e.key == p.K_s:  # evaluate score
                        gs.setEvaluation(analyzer.evaluatePosition(gs.board, 5))

                    if e.key == p.K_KP_PLUS and not humanCanPlay:
                        engineMove += 2

                    if e.key == p.K_q:
                        running = False

                    if e.key == p.K_n and not updateStats:
                        mustSkip = True
                        break

                    if e.key == p.K_h and not isNewPosition:  # Mostra la soluzione ma non se sta ancora risolvendo
                        if solution:
                            show_message(gs, f"Solution: {solution}")                            
                            delay(2 )

            
            if show_help:   
                    p.draw.rect(screen, GRAY, (50, 50, 600, 300))
                    p.draw.rect(screen, BLACK, (50, 50, 600, 300), 2)

                    for i, line in enumerate(help_text):
                        text = myfont.render(line, True, BLACK)                        
                        screen.blit(text, (60, 60 + i * 30))
                    p.display.flip()
                    continue

            if moveMade and not mustSkip:
                moveMade = False
                lastMove = gs.moveLog[-1]
                stop_stamp = datetime.now()

                if animate:
                    BS.animateMove(lastMove, screen, gs)

                    p.time.delay(100)
                    animate = False
                
                if updateStats:
                    updateStats=False
                    if AN.updateInfoStats(gs.board, learningBase):
                        msg = "Right"                                                
                        if isNewPosition: # 
                            delay(1 )
                            curr_data.timeElapsed = (stop_stamp-last_stamp).total_seconds()
                            curr_data.result = 1
                            

                        if not isNewPosition:
                            curr_data.notesTime += (stop_stamp-last_stamp).total_seconds()
                            
                            errorsMade[curr_zobrist] -= 1
                            if errorsMade[curr_zobrist] <= 0:
                                BS.drawGameState(screen, gs, toHighlightCirclesColor=[],
                                 toHighlightSquareColor=[],
                                 sqSelected=sqSelected)
                                msg  =  "Position solved"
                            else:
                                ll.append(pos)

                        show_message(gs, msg)
                        delay(1 )

                        engineMove = num_moves_to_show
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
                        zobrist:int = chess.polyglot.zobrist_hash(gs.board)
                        position = learningBase.positions[zobrist]
                        show_message(gs, "Right move is "+position.ok)
                        delay(3 )
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

                BS.drawGameState(screen, gs, toHighlightCirclesColor=toHighlightCircle,
                                 toHighlightSquareColor=toHighlightSquares,
                                 sqSelected=sqSelected)

            BS.update()
    p.event.clear()
    main_menu.enable()
    return result


def playBrainMaster(learningBaseName:str):
    learningBase = learningBases[learningBaseName]
    global screen

    #eventually unlocks new lessons
    main_background() 
    BS.drawEndGameText(screen,None, "Checking lessons to unlock",size=20)
    BS.update()

    res = unlock_new_lesson(learningBaseName)
    if res:
        main_background() 
        BS.drawEndGameText(screen, None,f"New lesson unlocked:{res}",size=20)
        BS.update()
        delay(2 )

    main_background() 
    BS.drawEndGameText(screen, None,"Acquiring test",size=20)
    BS.update()
    suggestion = ask_for_quiz(learningBaseName, BrainMaster.id_student)
    
    main_background() 
    if suggestion is None:
        main_background() 
        BS.drawEndGameText(screen, None,"Errore accedendo al servizio Brainmaster",size=20)
        BS.update()
        delay(2 )
        return
    action = suggestion["action"] if "action" in suggestion else None
    if action is None:
        main_background() 
        BS.drawEndGameText(screen, None,"No suggestion available",size=20)
        BS.update()
        delay(2 )
        return
    for q in suggestion["questions"]:
        # print id_question, id_test, id_lesson for each question (with labels)
        print(
            f"Question: {q['id_question']}, Test: {q['id_test']}, Lesson: {q['id_lesson']}")
        
         

    questions:List[QuestionData] = [QuestionData.from_dict(q) for q in suggestion["questions"]]
    results = playBrainMasterSet(learningBase, questions)
    count = sum(1 for item in results.values() if item.result == 1)
    total = len(results)
    msg = f"Number of correct answers: {count} over {total}"
    main_background() 
    BS.drawEndGameText(screen, None, msg,size=20)
    BS.update()

    give_answers(learningBaseName, action, list(results.values()))

   
def replayBadPositions(learningBase:LearningBase):
    '''
    Teaches maxErrorsToConsider = 10 positions at a time taken from a LearningBase. A Position is assumed to be learnt when
      it is solved correctly 3 times in a row after a mistake, or correctly answered the first time.
    '''

    global  screen
    

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
    maxErrorsToConsider = 10
    if len(ll)==0:
        text = "No positions found"
        main_background()
        BS.drawEndGameText(screen, None, text)
        BS.update()
        delay(2 )

    help_text = [
            "Istruzioni:",
            "- Q per uscire",
            "- C copia la posizione FEN nella clipboard",
            "- G copia la partita nella clipboard",
            "- S valuta la posizione ",
            "- F flip board",
            "- R reset",
            "- + vedi altre mosse",
            "- H mostra la soluzione"  
        ]
    show_help = False

    
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
        if pos.ok != pos.move:
            header.append("mistake was " + pos.move)



        moves = pos.moves.split()
        gs = GameState()
        gs.setHeader(header)
        #gs.setFen(pos["fen"])
        #BS.setWhiteUp(screen, not gs.whiteToMove())
        BS.setWhiteUp(screen, fen[1] == "b")
        BS.drawGameState(screen, gs, [], [], ())
        BS.update()
        solution = pos.ok

        currentMove = 0
        validMoves = gs.stdValidMoves()
        engineMove = 0
        mustSkip = False        # mustSkip determines the exit from the cycle
        humanCanPlay = True

       

        while running and not mustSkip:
            updateStats = False

            if play_position:
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

            if engineMove > 0:
                # make a move choosen by the engine
                chessmove:Optional[chess.Move] = UCIEngines.bestMove(gs, validMoves, time=1.0)
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
                if e.type == p.QUIT:
                    running = False            
                elif  e.type == p.MOUSEBUTTONDOWN and e.button == 3:
                        # Mostra aiuto quando il tasto destro è premuto
                        show_help = True            
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Nasconde aiuto quando il tasto destro è rilasciato
                        show_help = False
                elif e.type == p.MOUSEBUTTONDOWN and not humanCanPlay:
                    mustSkip = True
                    break
                elif e.type == p.MOUSEBUTTONDOWN and not gameOver and humanCanPlay:
                    row, col = BS.getRowColFromLocation(p.mouse.get_pos())

                    if sqSelected == (row, col) or col >= 8:  # user clicked same square or in move log
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
                                piece = BS.choosePromotion(screen, move.pieceMoved[0])
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
                        pyperclip.copy(gs.board.fen())
                        text = "Position copied to clipboard"
                        show_message(gs, text)
                        delay(2 )

                    if e.key == p.K_g:
                        # copy position to clibboard
                        pyperclip.copy(pos.to_PgnString())
                        text = "Game copied to clipboard"
                        show_message(gs, text)
                        delay(2)

                    if e.key == p.K_LESS and (e.mod & p.KMOD_SHIFT):
                        BS.setFactor( BS.getFactor()*1.2)

                    if e.key == p.K_LESS and ((e.mod & p.KMOD_SHIFT) == 0):
                        BS.setFactor( BS.getFactor() / 1.2)

                    if e.key == p.K_s:  # evaluate score
                        gs.setEvaluation(analyzer.evaluatePosition(gs.board, 5))

                    if e.key == p.K_q:
                        running = False

                    if e.key == p.K_KP_PLUS and not humanCanPlay:
                        engineMove += 2

                    if e.key == p.K_n and not humanCanPlay:
                        mustSkip = True
                        break

                    if e.key == p.K_h and not updateStats:  # Mostra la soluzione
                        if solution:
                            show_message(gs, f"Solution: {solution}")
                            delay(2)

            
            if show_help:   
                    p.draw.rect(screen, GRAY, (50, 50, 600, 300))
                    p.draw.rect(screen, BLACK, (50, 50, 600, 300), 2)

                    for i, line in enumerate(help_text):
                        text = myfont.render(line, True, BLACK)                        
                        screen.blit(text, (60, 60 + i * 30))
                    p.display.flip()
                    continue

            if moveMade and not mustSkip:
                moveMade = False
                lastMove = gs.moveLog[-1]
                if animate:
                    BS.animateMove(lastMove, screen, gs)

                    delay(0.1)
                    animate = False

                if updateStats:
                    if AN.updateInfoStats(gs.board, learningBase):
                        msg = "Right"

                        if not isNewPosition:
                            # print(f"currentElement is {currentElement}, len of numberOfErrors is {len(numberOfErrors)}")
                            numberOfErrors[currentElement] -= 1
                            if numberOfErrors[currentElement] == 0 or pos.skip == "S":
                                del numberOfErrors[currentElement]
                                del errorsMade[currentElement]
                                msg = "Position solved"

                        show_message(gs,msg)
                        delay(1 )

                        engineMove = num_moves_to_show
                        humanCanPlay = False
                    else:
                        show_message(gs,"Not the right move")
                        delay(1 )
                        gs.undoMove()
                        validMoves = gs.stdValidMoves()
                        if isNewPosition:
                            # print(f"wrong move, appending new error position")
                            currentElement = len(errorsMade)
                            errorsMade.append(pos)
                            numberOfErrors.append(3)
                            isNewPosition = False

                        else:
                            # print(f"wrong move, setting n.of error = 3")
                            numberOfErrors[currentElement] = 3

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

                BS.drawGameState(screen, gs, toHighlightCirclesColor=toHighlightCircle,
                                 toHighlightSquareColor=toHighlightSquares,
                                 sqSelected=sqSelected)

            BS.update()

    p.event.clear()
    main_menu.enable()

def playModels():
    global main_menu

    if positionParameters["filename"] is None:
        return

    main_menu.disable()
    main_menu.full_reset()
    playModelFiles( positionParameters["filename"],  positionParameters["color"])
    return

def playModelFiles(filename, humanColor):
    '''
        Play a random game from a file, and the player must always play the best move, while the computer plays one of the
          available lines stored in the game.
    '''

    global screen, play_position

    gr = gamereader.PgnGameList(filename)

    running = True
    sqSelected = ()
    playerClicks = []
    moveMade = False
    animate = False


    if gr.isEmpty():
        text = "No positions found"
        main_background()
        BS.drawEndGameText(screen, None, text)
        BS.update()
        delay(2 )
        main_menu.enable()
        return

    while running:
        gr.chooseRandomGame()
        gs = gr.gs
        gs.setHeader([filename.stem])

        if play_position:
            # skip all stored moves until a leaf node is reached
            moreMoves = True
            move = None
            while moreMoves:
                playerTurn = gs.colorToMove() == humanColor    

                if playerTurn:
                    moreMoves = gr.doNextMainMove()
                    if random.randint(1, 3) == 1:
                        break
                else:
                    move = gr.makeNextMove()
                    moreMoves = move is not None
            # takes back last move
            gr.undoMove()
            

                
        

        BS.setWhiteUp(screen, humanColor == "b")
        BS.drawGameState(screen, gs, [], [], ())
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
            nextMove = gr.getNextMainMove()
            if nextMove is None or stopCondition:  # game is over anyway
                text = "Solved"
                main_background()
                BS.drawEndGameText(screen, gs, text)
                BS.update()
                delay(2 )
                gameOver = True
                break

            if nextMove is not None and not humanCanPlay:
                    move = gr.makeNextMove()
                    moveMade = True
                    animate = True
                    validMoves = gs.stdValidMoves()


            for e in p.event.get():
                if e.type == p.QUIT:
                    running = False
                elif e.type == p.MOUSEBUTTONDOWN and gameOver:
                    mustSkip = True
                    break
                elif e.type == p.MOUSEBUTTONDOWN and not gameOver and humanCanPlay:

                    row, col = BS.getRowColFromLocation(p.mouse.get_pos())

                    if sqSelected == (row, col) or col >= 8:  # user clicked same square or in move log
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
                                piece = BS.choosePromotion(screen, move.pieceMoved[0])
                                move = move.promoteToPiece(piece)

                        # print(move.getChessNotation())
                        validMove = next((m for m in validMoves if move == m), None)
                        if validMove is not None:
                            if gr.checkNextMove(validMove.move):
                                errors = 0
                                gr.doNextMainMove()
                                moveMade = True
                                animate = True
                                validMoves = gs.stdValidMoves()
                                if play_position:
                                    stopCondition=True
                            else:
                                errors += 1
                                msg = "Not the right move"
                                if errors >= 3:
                                    rightMove = Move.fromChessMove(gr.getNextMainMove(), gs)
                                    msg = f"hint:{rightMove.uci[:2]}"
                                show_message(gs,msg)
                                delay(1)
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
                        pyperclip.copy(gs.board.fen())                        
                        text = "Position copied to clipboard"
                        show_message(gs,text)
                        delay(2 )
                    
                    if e.key == p.K_g:
                        # copy position to clibboard
                        pyperclip.copy(pos.to_PgnString())
                        text = "Game copied to clipboard"
                        show_message(gs, text)
                        delay(2)

                    if e.key == p.K_s:  # evaluate score
                        gs.setEvaluation(analyzer.evaluatePosition(gs.board, 5))

                    if e.key == p.K_q:
                        running = False

                    if e.key == p.K_n and not humanCanPlay:
                        mustSkip = True
                        break

                    if e.key == p.K_f:
                        whiteUp = not whiteUp
                        moveMade = True
                        animate = False


            if moveMade and not mustSkip:
                moveMade = False
                lastMove = gs.moveLog[-1] if len(gs.moveLog) > 0 else None
                if animate and lastMove:
                    BS.animateMove(lastMove, screen, gs)
                    delay(0.1)
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

                BS.drawGameState(screen, gs, toHighlightCirclesColor=toHighlightCircle,
                                 toHighlightSquareColor=toHighlightSquares,
                                 sqSelected=sqSelected)

            BS.update()

    p.event.clear()
    main_menu.enable()


main_running = True
current_base_label = None
current_filename_label = None
current_base_label2 = None
current_base_label3 = None 
current_filename_label3 = None
current_filename_label4= None
current_ChessComFile_label = None


def update_base_display():
    global current_base_label, current_base_label2,current_base_label3
    value = positionParameters.get("base", "Nessuna selezionata")
    current_base_label.set_title(value)
    current_base_label2.set_title(value)
    current_base_label3.set_title(value)

   


def update_filename_display():
    global current_filename_label, current_filename_label3, current_filename_label4, current_ChessComFile_label
    value = positionParameters.get("filename", "Nessuna selezionata")
    current_filename_label.set_title(value)
    current_filename_label3.set_title(value)
    current_filename_label4.set_title(value)
    current_ChessComFile_label.set_title(value)


def quit_program():
    print ("quit program called\n")
    global main_running
    main_running = False 


def createLearningBase():    
    global positionParameters
    # Verifica che filename non sia vuoto
    filename = positionParameters.get("filename", "").strip()
    if not filename:
        raise ValueError("Il campo 'filename' in positionParameters è vuoto.")


    learningBase = LearningBase(movesToAnalyze=positionParameters.get("movesToAnalyze",16),
                                                               blunderValue=positionParameters.get("blunderValue", 80),
                               ponderTime=positionParameters.get("ponderTime", 0.5),
                                useBook=positionParameters.get("useBook", False))

    learningBase.setFileName(filename)
    learningBases[filename] = learningBase
    learningBase.save()

    main_background()
    BS.drawEndGameText(screen, None, f"learning base created")
    BS.update()
    delay(2 )
    return


def updateLearningBase():
    pgnFileName = positionParameters.get("filename", None)
    learningBaseName = positionParameters.get("base", None)
    player = positionParameters.get("player", None)
    if pgnFileName is None :
        text = "Please select a PGN file"
        main_background()
        BS.drawEndGameText(screen, None, text)
        BS.update()
        delay(2 )
        return

    if learningBaseName is None:
        text = "Please select a base file"
        main_background()
        BS.drawEndGameText(screen, None, text)
        BS.update()
        delay(2 )
        return

    if player is None or player == "":
        text = "Please enter a player name"
        main_background()
        BS.drawEndGameText(screen, None, text)
        BS.update()
        delay(2 )
        return

    learningBase = learningBases.get(learningBaseName, None)
    
    analyzer.analyzePgn(pgnFileName, player, learningBase)
    text = f"Learning base {learningBaseName} updated with {pgnFileName}"
    main_background()
    BS.drawEndGameText(screen, None, text)
    BS.update()

def unrollPGN():
    pgnFileName = positionParameters.get("filename", None)
    if pgnFileName is None :
        text = "Please select a PGN file"
        main_background()
        BS.drawEndGameText(screen, None, text)
        BS.update()
        delay(2 )
        return

    basename = os.path.splitext(os.path.basename(pgnFileName))[0]    
    learningBase = LearningBase(0,0,0,False)
    learningBase.setFileName(basename)
    learningBases[basename] = learningBase
    analyzer.unrollPgn(pgnFileName, learningBase, positionParameters.get("color", "w")=="w")
        
    main_background()
    BS.drawEndGameText(screen, None, "Unroll done")
    BS.update()
    delay(2)
    return

def readChessComGames(): 
    '''
    Reads a file with Chess.com games and creates a LearningBase from it.
    The file must be in the format of a Chess.com export, with each game separated by a blank line.
    '''
    pgnFileName = positionParameters.get("filename", None)
    if pgnFileName is None :
        text = "Please select a PGN file"
        main_background()
        BS.drawEndGameText(screen, None, text)
        BS.update()
        delay(2 )
        return
    
    chess_com_download.load(positionParameters.get("player", None), pgnFileName, positionParameters.get("color",None))
        
    main_background()
    BS.drawEndGameText(screen, None, "Games downloaded")
    BS.update()
    delay(2)


def registerBrainMaster():
    '''
    Registers a new BrainMaster base, which is a LearningBase with a specific name.
    The name is taken from the positionParameters["base"] variable.
    '''
    global screen, current_base_label2
    learningBaseName = positionParameters.get("base", None)
    if learningBaseName is None or learningBaseName == "":
        text = "Please select a base file"
        main_background()
        BS.drawEndGameText(screen, None, text)
        BS.update()
        delay(2 )
        return

    if not learningBaseName in learningBases:
        text = f"BrainMaster base {learningBaseName} does not exist"
        main_background()
        BS.drawEndGameText(screen, None, text)
        BS.update()
        delay(2 )
        return

    BrainMaster.add_to_BrainMaster(learningBaseName)
    text = f"BrainMaster base {learningBaseName} registered"
    main_background()
    BS.drawEndGameText(screen, None, text)
    BS.update()



def mainMenu(width,height, test: bool = False) -> None:
    global clock
    global main_menu
    global screen
    global FPS
    global manager
    global main_running
    global num_moves_to_show
    global current_base_label, current_base_label2,current_filename_label, current_base_label3, current_filename_label3, current_filename_label4
    global current_ChessComFile_label

    clock = p.time.Clock()

    playParameters["elomax"] = False
    surface = screen
    default_color_index = REVERSE_COLOR_MAP.get(positionParameters["color"], 0)
    setColorIndex = lambda val, idx: positionParameters.__setitem__("color", COLOR_MAP[int(val[0][1])])

    value_map = {1: True, 0: False}
    reverse_value_map = {v: k for k, v in value_map.items()}
    setUseBook = lambda val, idx: positionParameters.__setitem__("useBook", COLOR_MAP[val[0][1]])

    playComputerMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Choose play params',
        width=width
    )    
    playComputerMenu.add.selector('You play', [("White", 0), ("Black", 1), ("Random", 2)], onchange=setPlayColor)
    playComputerMenu.add.range_slider('ELO', range_values=(1350, 2850), onchange=setPlayElo, default=2000, increment=50)
    playComputerMenu.add.toggle_switch("ELO MAX", state_text=("Off", "On"), state_values=(False, True), 
                                       onchange=make_updater("elomax",bool,playParameters))
    playComputerMenu.add.range_slider('Num Moves to Show', range_values=(0, 10), increment = 1,  
                                      onchange=make_updater("num_moves_to_show",int), 
                default=num_moves_to_show)  # Aggiungi questa riga

    playComputerMenu.add.button('Play', playGame)
    

    playDataSetMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Base Options',
        width=width
    )    
    playDataSetMenu.add.text_input('ECO (optional)', default=positionParameters["eco"] or "", onchange=setPositionEco)
    playDataSetMenu.add.selector('You play', [("White", 0), ("Black", 1), ("Any", 2)], default=default_color_index,
                                onchange=setColorIndex)
    labels = []
    chooseBaseFile = make_file_selector(
        "base", lambda x : x.replace("base_", "") , labels,"data",".json", "Choose base file",None,"base_")
    playDataSetMenu.add.button('Choose base file', chooseBaseFile)
    default_value = str(positionParameters.get("base", "Nessuna selezionata"))
    label = playDataSetMenu.add.button(default_value,chooseBaseFile,font_size=20, background_color=None,selection_effect=pygame_menu.widgets.NoneSelection())
    labels.append(label)
    playDataSetMenu.add.selector('Skip initial moves', [("Yes", 1), ("No", 0)], default=play_position, onchange=make_selector_updater("play_position"))
    playDataSetMenu.add.range_slider('Num Moves to Show', range_values=(0, 10), increment=1, onchange=make_updater("num_moves_to_show",int), 
                                     value_format=lambda x: str(round(x, 0)),
                default=num_moves_to_show)  # Aggiungi questa riga

    playDataSetMenu.add.button('Play', replayBase)
    

    ExerciseModelsMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Choose model games',
        width=width
    )
    
    ExerciseModelsMenu.add.selector('You play', [("White", 0), ("Black", 1)],
                      default=default_color_index if default_color_index<2 else 0, onchange=setColorIndex)
    ExerciseModelsMenu.add.range_slider('Num Moves to Show', range_values=(0, 10), increment=1,value_format=lambda x: str(round(x, 0)),
                                       onchange=make_updater("num_moves_to_show",int), 
                default=num_moves_to_show)  # Aggiungi questa riga
    labels = []
    chooseModelFile = make_file_selector("filename", None , labels, "pgn", ".pgn", "Choose PGN file", None)
    ExerciseModelsMenu.add.button('Choose PGN file', chooseModelFile)
    default_value = str(positionParameters.get("filename", "Nessuna selezionata"))
    label = ExerciseModelsMenu.add.button(default_value,chooseModelFile,font_size=20, background_color=None,selection_effect=pygame_menu.widgets.NoneSelection())    
    labels.append(label)
    ExerciseModelsMenu.add.selector('Skip initial moves', [("Yes", 1), ("No", 0)], default=play_position, onchange=make_selector_updater("play_position"))
    ExerciseModelsMenu.add.button('Play', playModels)

    BrainMasterMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Choose base',
        width=width
    )    
    labels = []
    chooseBaseFile = make_file_selector(
         "base", lambda x : x.replace("base_", "") , labels,"data",".json", "Choose base file",None, "base_")
    BrainMasterMenu.add.button('Choose base file', chooseBaseFile)
    default_value = str(positionParameters.get("base", "Nessuna selezionata"))
    
    label = BrainMasterMenu.add.button(default_value,chooseBaseFile,font_size=20, background_color=None,selection_effect=pygame_menu.widgets.NoneSelection())    
    labels.append(label)
    BrainMasterMenu.add.range_slider('Num Moves to Show', range_values=(0, 10),  onchange=make_updater("num_moves_to_show",int), value_format=lambda x: str(round(x, 0)),
                default=num_moves_to_show, increment=1)  # Aggiungi questa riga
    BrainMasterMenu.add.selector('Skip initial moves', [("Yes", 1), ("No", 0)], default=play_position, onchange=make_selector_updater("play_position"))
    # Disabilita il text_input in modo che l'utente non possa modificarlo
    BrainMasterMenu.add.button('Create course', registerBrainMaster)
    BrainMasterMenu.add.button('Play', playBrainMasterBase)
    


    updateLearningBaseMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Update learning base',
        width=width
    )  
    labels = []
    updateLearningBaseMenu.add.text_input('player:', default=positionParameters["player"] or "", onchange=make_updater("player",str,positionParameters))
    chooseModelFile = make_file_selector("filename", None , labels, "pgn", ".pgn", "Choose PGN file", None)
    updateLearningBaseMenu.add.button('Choose PGN file', chooseModelFile)
    default_value = str(positionParameters.get("filename", "Nessuna selezionata"))
    label = updateLearningBaseMenu.add.button(default_value,chooseModelFile,font_size=20, background_color=None,selection_effect=pygame_menu.widgets.NoneSelection())        
    labels.append(label)
    labels = []
    chooseBaseFile = make_file_selector("base", lambda x : x.replace("base_", "") , labels,"data",".json", "Choose base file",None, "base_")
    updateLearningBaseMenu.add.button('Choose base file', chooseBaseFile)
    # Aggiungi un text_input che sarà usato per visualizzare la base corrente
    # Inizializza il suo valore con la base corrente o un messaggio predefinito
    default_value = str(positionParameters.get("base", "Nessuna selezionata"))
    label = updateLearningBaseMenu.add.button(default_value,chooseBaseFile,font_size=20, background_color=None,selection_effect=pygame_menu.widgets.NoneSelection())           
    labels.append(label)
    updateLearningBaseMenu.add.button('Update Learning Base', updateLearningBase)
    
    
    createBaseMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='download chess.com games',
        width=width
    )  
    createBaseMenu.add.text_input('movesToAnalyze:', default=positionParameters["movesToAnalyze"] or "", 
                                    onchange=make_updater("movesToAnalyze",int,positionParameters))
    createBaseMenu.add.text_input('blunderValue:', default=positionParameters["blunderValue"] or "", 
                                  onchange=make_updater("blunderValue",int,positionParameters))
    createBaseMenu.add.text_input('ponderTime:', default=positionParameters["ponderTime"] or "", 
                                    onchange=make_updater("ponderTime",float,positionParameters))
    createBaseMenu.add.selector('useBook', [("Yes", 1), ("No", 0)], default= reverse_value_map[ positionParameters["useBook"] ], 
                                onchange=make_bool_selector_updater("useBook", positionParameters))
    createBaseMenu.add.text_input('filename:', default=positionParameters["filename"] or "",
                                 onchange=make_updater("filename",str,positionParameters))    
    createBaseMenu.add.button('Create learning base', createLearningBase)

    

    unrollPGNMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Unroll model PGN',
        width=width
    )  
    labels = []
    chooseModelFile = make_file_selector("filename", None , labels, "pgn", ".pgn", "Choose PGN file", None)
    unrollPGNMenu.add.button('Choose PGN file', chooseModelFile)
    default_value = str(positionParameters.get("filename", "Nessuna selezionata"))
    label =  unrollPGNMenu.add.button(default_value,chooseModelFile,font_size=20, background_color=None,selection_effect=pygame_menu.widgets.NoneSelection())           
    labels.append(label)
    unrollPGNMenu.add.selector('You play', [("White", "0"), ("Black", "1")], 
                               default=default_color_index if default_color_index<2 else 0, onchange=setColorIndex)                      
    unrollPGNMenu.add.button('Unroll', unrollPGN)
    
    chessComMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='download chess.com games',
        width=width
    )  
    chooseNewPgn = make_file_selector("filename", None , labels, "pgn/newfile.pgn", ".pgn", "Select PGN file to create", None)
    chessComMenu.add.button('PGN file to create', chooseNewPgn)
    default_value = str(positionParameters.get("filename", "Nessuna selezionata"))
    current_ChessComFile_label = chessComMenu.add.button(default_value,chooseNewPgn,font_size=20, background_color=None,selection_effect=pygame_menu.widgets.NoneSelection())               
    chessComMenu.add.text_input('player:', default=positionParameters["player"] or "", onchange=make_updater("player",str,positionParameters))
    chessComMenu.add.selector('Player color', [("White", 0), ("Black", 1), ("Any", 2)], default=default_color_index , onchange=setColorIndex)
    
    chessComMenu.add.button('Download games', readChessComGames)

   
    def combine_onchange(first_fn, second_fn):
        def combined(*args, **kwargs):
            first_fn(*args, **kwargs)
            second_fn()
        return combined
    
    configureGame = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Choose base',
        width=width
    )    
    configureGame.add.text_input('base_url:', default=config.base_url or "", 
                                            onchange=combine_onchange(make_updater("base_url",str,config), save_config))
    configureGame.add.text_input('id studente:', default=config.id_student or "",
                                        onchange=combine_onchange(make_updater("id_student",str,config), save_config))

    def restart_engine():
        save_config()
        UCIEngines.engine_close()
        UCIEngines.engine_open()

    configureGame.add.text_input('engine:', default=config.engine or "",
                                        onchange=combine_onchange(make_updater("engine",str,config), restart_engine))

    toolsMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Tools',
        width=width
    )  
    toolsMenu.add.button('Download Chess.com games', chessComMenu)
    toolsMenu.add.button("Create learning base", createBaseMenu)
    toolsMenu.add.button('Update learning base', updateLearningBaseMenu)
    toolsMenu.add.button('Unroll PGN file', unrollPGNMenu)
    toolsMenu.add.button('Config', configureGame)


    main_menu = pygame_menu.Menu('Chess Python', width, height,
                                 theme=pygame_menu.themes.THEME_BLUE)
    main_menu.add.button('Play against computer', playComputerMenu)
    main_menu.add.button('Play between humans', humanPlay)
    main_menu.add.button('Play a dataset', playDataSetMenu)
    main_menu.add.button('BrainMaster lessons', BrainMasterMenu)
    main_menu.add.button('Exercise by models', ExerciseModelsMenu)
    main_menu.add.button('Tools', toolsMenu)
    main_menu.add.button('Quit', quit_program) # pygame_menu.events.EXIT

    main_menu.disable()
    main_menu.full_reset()
    main_menu.enable()

    

    while main_running:
        # Tick
        clock.tick(FPS)

        # Paint background
        main_background()
        
        events = p.event.get()
        # for event in events:
        #     if event.type == p.QUIT:
        #         main_running = False  # Esce dal loop principale


        # Main menu
        if main_menu.is_enabled():
            main_menu.update(events)   # Gestisce gli eventi del menu
            main_menu.draw(surface)    # Disegna il menu sulla finestra
            #main_menu.mainloop(surface, main_background, disable_loop=test, fps_limit=FPS)
        else:
            main_running = False  # Chiude il programma se il menu sparisce

        # Flip surface
        p.display.flip()

        # At first loop returns
        if test:
            break
    
    


def runMain():
    global myfont
    p.init()
    
    myfont = p.font.SysFont('Comic Sans MS', 20)
    global screen
    global W
    global H
    global manager

    UCIEngines.engine_open()
    try:
        W, H = BS.init()

        screen = p.display.set_mode((W, H))
        screen.fill(p.Color("white"))

        p.display.set_caption('Chess trainer')
        Icon = p.image.load('pic-chess.png')
        p.display.set_icon(Icon)


        manager = pygame_gui.UIManager((W, H))

        mainMenu(W, H)

        p.display.quit()
        p.quit()    
        
    finally:
        UCIEngines.engine_close()

    sys.exit()



if __name__ == "__main__":
    runMain()
