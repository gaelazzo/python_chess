"""
Main driver file

"""
import random

import Board
import pygame as p
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

FPS = 60

manager = None
screen  = None
W = None
H = None

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
    "filename": None
}


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

def chooseModelFile():
    global manager
    global H
    global W
    background = p.Surface((W, H))
    background.fill(p.Color('#000000'))

    file_selection = UIFileDialog(rect=p.Rect(0, 0, W, H),
                                  manager=manager,
                                  allow_existing_files_only=True,
                                  window_title="Select PGN file",
                                  initial_file_path="pgn",
                                  allow_picking_directories=False)

    while 1:
        time_delta = clock.tick(60) / 1000.0

        for event in p.event.get():
            if event.type == p.QUIT:
                quit()

            if event.type == p.USEREVENT:
                if event.user_type == pygame_gui.UI_BUTTON_PRESSED:  # user_type
                #if event.type == p.MOUSEBUTTONDOWN:  # user_type

                    if event.ui_element == file_selection.ok_button:
                        positionParameters["filename"] = file_selection.current_file_path
                        pygame_menu.events.BACK
                        return

            manager.process_events(event)

        manager.update(time_delta)
        screen.blit(background, (0, 0))
        manager.draw_ui(screen)

        p.display.update()




CIRCLE_COLOR = (15, 50, 180, 90)




def setEloMax(value):
    playParameters["elomax"] = value

def setPlayElo(value):
    playParameters["elo"] = value

def humanPlay():
    playParameters["whiteCPU"]=False
    playParameters["blackCPU"] = False
    playGame()

def setPositionColor(color, index):
    myColor = color[0][0]
    if myColor == "Any":
        myColor = None
    if myColor == "White":
        myColor = "w"
    if myColor == "Black":
        myColor = "b"

    positionParameters["color"] = myColor



def setPositionEco(current_text, **kwargs):
    global openingParameters
    if current_text == "":
        positionParameters["eco"] = None
    else:
        positionParameters["eco"] = current_text.upper()

def playGame():
    global main_menu
    main_menu.disable()
    main_menu.full_reset()
    playAGame()


def playAGame():
    global screen
    gs = Board.GameState()
    validMoves = gs.stdValidMoves()
    elo = playParameters["elo"]
    if playParameters["elomax"]:
        elo = None

    running = True
    sqSelected = ()
    playerClicks = []
    moveMade = False
    animate = False
    gameOver = False
    whiteCPU = playParameters["whiteCPU"]
    blackCPU = playParameters["blackCPU"]

    myfont = p.font.SysFont('Comic Sans MS', 20)

    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    GRAY = (200, 200, 200)

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
            move = UCIEngines.bestMove(gs, validMoves, elo=elo)
            if move is not None:
                if not hasattr(move, "move"):
                    move = Board.Move.fromChessMove(move, gs)
                gs.makeMove(move)
                moveMade = True
                animate = True
                validMoves = gs.stdValidMoves()

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
                    row,col = BS.getRowColFromLocation(p.mouse.get_pos())

                    if sqSelected == (row, col) or col >= 8:  # user clicked same square or in move log
                        sqSelected = ()
                        playerClicks = []
                    else:
                        sqSelected = (row, col)
                        playerClicks.append(sqSelected)

                    if len(playerClicks) == 2:
                        move = Board.Move(playerClicks[0], playerClicks[1], gs)

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
                            gs.makeMove(validMove)
                            moveMade = True
                            animate = True
                            validMoves = gs.stdValidMoves()
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

                    if e.key == p.K_q:
                        #quit
                        running = False

                    if e.key == p.K_c:  # copy to clipboard
                        pyperclip.copy(BS.board.fen())
                        text = "Position copied to clipboard"
                        BS.drawEndGameText(screen, text)
                        p.time.delay(2 * 1000)
                        running = False

                    if e.key == p.K_s:  # evaluate score
                        gs.setEvaluation(analyzer.evaluatePosition(gs.board, 5))

                    if e.key == p.K_f:
                        BS.flipBoard()
                        moveMade = True
                        animate = False

                    if e.key == p.K_r:
                        gs = Board.GameState()
                        sqSelected = ()
                        playerClicks = []
                        validMoves = gs.stdValidMoves()
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
            if animate:
                BS.animateMove(gs.moveLog[-1], screen, gs)
                animate = False
            moveMade = False
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
            BS.drawEndGameText(screen, text)
            p.time.delay(2 * 1000)
            running = False
            # textsurface = myfont.render('Stalemate', False, p.Color("red"))
            # screen.blit(textsurface, (200, 100))

        else:
            toHighlightCircle = []
            toHighlightSquares = []
            if len(playerClicks) == 1:
                mm = [m for m in validMoves if m.startRow == sqSelected[0] and m.startCol == sqSelected[1]]
                toHighlightCircle = [(m.stopRow, m.stopCol,CIRCLE_COLOR) for m in mm]

            if len(playerClicks) == 0 and len(gs.moveLog) > 0:
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


def replayBadOpenings():
    global main_menu
    main_menu.disable()
    main_menu.full_reset()
    replayBadPositions(analyzer.learningBases["openings"])
    return

def replayBlunders():
    global main_menu
    main_menu.disable()
    main_menu.full_reset()
    replayBadPositions(analyzer.learningBases["blunders"])
    return


def replayBadPositions(learningBase):
    global  screen

    # ll is a copy (non a deep copy) of data in the csv, not the same structure
    ll = analyzer.getRandomPositions(learningBase, positionParameters)

    running = True
    sqSelected = ()
    playerClicks = []
    moveMade = False
    animate = False
    gameOver = False
    errorsMade = []
    numberOfErrors = []
    maxErrorsToConsider = 10
    if len(ll)==0:
        text = "No positions found"
        main_background()
        BS.drawEndGameText(screen, text)
        BS.update()
        p.time.delay(2 * 1000)

    while (len(ll) > 0 or len(errorsMade) > 0) and running:
        # index of current error being examined or None if it is still not present in errorsMade
        isNewPosition = True
        currentElement = random.randint(0, maxErrorsToConsider-1)
        if currentElement >= len(errorsMade) and len(ll)>0:
            pos = ll.pop()  # this does not remove data from the csv
        else:
            if currentElement >= len(errorsMade):
                currentElement = len(errorsMade)-1
            pos = errorsMade[currentElement]
            isNewPosition = False

        # print(f"currentElement is {currentElement}, len(errorsMade) = {len(errorsMade)}, "
        #       f"len(numberOfErrors) is {len(numberOfErrors)}")
        # print(errorsMade)
        fen = pos["fen"].split()
        header = ["White:"+pos["white"], "Black:"+pos["black"], "ECO:"+pos["eco"], "Date:"+pos["date"],
                  "mistake was " + pos["move"]]


        moves = pos["moves"].split()
        gs = Board.GameState()
        gs.setHeader(header)
        #gs.setFen(pos["fen"])
        #BS.setWhiteUp(screen, not gs.whiteToMove())
        BS.setWhiteUp(screen, fen[1] == "b")
        BS.drawGameState(screen, gs, [], [], ())
        BS.update()

        currentMove = 0
        validMoves = gs.stdValidMoves()
        engineMove = 0
        mustSkip = False
        humanCanPlay = True

       

        

        while running and not mustSkip:
            updateStats = False

            
            if currentMove < len(moves):
                ucimove = moves[currentMove]
                currentMove += 1
                chessMove = chess.Move.from_uci(ucimove)
                move = Board.Move.fromChessMove(chessMove, gs)
                # print(f"made a move from list:{move.getChessNotation()}")
                gs.makeMove(move)
                moveMade = True
                animate = True
                validMoves = gs.stdValidMoves()

            if engineMove > 0:
                move = UCIEngines.bestMove(gs, validMoves, time=1.0)
                if move is not None:
                    if not hasattr(move, "move"):
                        move = Board.Move.fromChessMove(move, gs)
                gs.makeMove(move)
                # print(f"made a move from engine:{move.getChessNotation()}")

                moveMade = True
                animate = True
                validMoves = gs.stdValidMoves()
                engineMove = engineMove-1

            for e in p.event.get():
                if e.type == p.QUIT:
                    running = False            
                
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
                        move = Board.Move(playerClicks[0], playerClicks[1], gs)

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
                            # print(f"made a move from human:{move.getChessNotation()}")
                            gs.makeMove(validMove)
                            moveMade = True
                            animate = True
                            validMoves = gs.stdValidMoves()
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
                        BS.drawEndGameText(screen, text)
                        p.time.delay(2 * 1000)

                    if e.key == p.K_s:  # evaluate score
                        gs.setEvaluation(analyzer.evaluatePosition(gs.board, 5))

                    if e.key == p.K_q:
                        running = False

                    if e.key == p.K_n and not humanCanPlay:
                        mustSkip = True
                        break

            
            if moveMade and not mustSkip:
                moveMade = False
                lastMove = gs.moveLog[-1]
                if animate:
                    BS.animateMove(lastMove, screen, gs)

                    p.time.delay(100)
                    animate = False

                if updateStats:
                    if AN.updateInfoStats(gs.board, learningBase):
                        BS.drawEndGameText(screen, "Right")
                        BS.update()
                        p.time.delay(1 * 1000)

                        if not isNewPosition:
                            # print(f"currentElement is {currentElement}, len of numberOfErrors is {len(numberOfErrors)}")
                            numberOfErrors[currentElement] -= 1
                            if numberOfErrors[currentElement] == 0 or pos["skip"] == "S":
                                del numberOfErrors[currentElement]
                                del errorsMade[currentElement]
                                BS.drawEndGameText(screen, "position solved")
                                p.time.delay(2 * 1000)

                        engineMove = 4
                        humanCanPlay = False
                    else:

                        BS.drawEndGameText(screen, "Not the right move")
                        BS.update()
                        p.time.delay(2 * 1000)
                        BS.update()
                        gs.undoMove()
                        validMoves = gs.stdValidMoves()
                        moveMade = False
                        animate = False
                        if isNewPosition:
                            # print(f"wrong move, appending new error position")
                            currentElement = len(errorsMade)
                            errorsMade.append(pos)
                            numberOfErrors.append(3)
                            isNewPosition = False

                        else:
                            # print(f"wrong move, setting n.of error = 3")
                            numberOfErrors[currentElement] = 3

            if currentMove >= len(moves) and engineMove == 0:
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
    global screen

    gr = gamereader.PgnGameList(filename)

    running = True
    sqSelected = ()
    playerClicks = []
    moveMade = False
    animate = False


    if gr.isEmpty():
        text = "No positions found"
        main_background()
        BS.drawEndGameText(screen, text)
        BS.update()
        p.time.delay(2 * 1000)
        main_menu.enable()
        return

    while running:
        gr.chooseRandomGame()

        gs = gr.gs

        gs.setHeader([filename.stem])

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

        while running and not mustSkip:
            humanCanPlay = gs.colorToMove() == humanColor
            checkMove = False
            nextMove = gr.getNextMainMove()
            if nextMove is None:  # game is over anyway
                text = "Solved"
                main_background()
                BS.drawEndGameText(screen, text)
                BS.update()
                p.time.delay(2 * 1000)
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
                        move = Board.Move(playerClicks[0], playerClicks[1], gs)

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
                            else:
                                errors += 1
                                msg = "Not the right move"
                                if errors >= 3:
                                    rightMove = Board.Move.fromChessMove(gr.getNextMainMove(), gs)
                                    msg = f"hint:{rightMove.uci[:2]}"

                                BS.drawEndGameText(screen, msg)
                                BS.update()
                                p.time.delay(1 * 1000)
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

                    if e.key == p.K_c:
                        # copy position to clibboard
                        pyperclip.copy(gs.board.fen())
                        text = "Position copied to clipboard"
                        BS.drawEndGameText(screen, text)
                        p.time.delay(2 * 1000)

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
                lastMove = gs.moveLog[-1]
                if animate:
                    BS.animateMove(lastMove, screen, gs)

                    p.time.delay(100)
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

    main_menu.enable()


main_running = True

def quit_program():
    print ("quit program called\n")
    global main_running
    main_running = False 

def mainMenu(width,height, test: bool = False) -> None:
    global clock
    global main_menu
    global screen
    global FPS
    global manager
    global main_running
    
    clock = p.time.Clock()

    playParameters["elomax"] = False
    surface = screen

    choosePlayParamsMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Choose play params',
        width=width
    )
    menu = choosePlayParamsMenu
    menu.add.selector('You play', [("White", 0), ("Black", 1), ("Random", 2)], onchange=setPlayColor)
    menu.add.range_slider('ELO', range_values=(1350, 2850), onchange=setPlayElo, default=2000, increment=50)
    menu.add.toggle_switch("ELO MAX", state_text=("Off", "On"), state_values=(False, True), onchange=setEloMax)
    menu.add.button('Play', playGame)
    menu.add.button('Return to main', pygame_menu.events.BACK)

    chooseOpeningParamsMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Choose openings filter',
        width=width
    )
    menu = chooseOpeningParamsMenu
    menu.add.text_input('ECO (optional)', default=positionParameters["eco"] or "", onchange=setPositionEco)
    menu.add.selector('You play', [("White", 0), ("Black", 1), ("Any", 2)], default=getCurrentColorIndex(),
                      onchange=setPositionColor)
    menu.add.button('Play', replayBadOpenings)
    menu.add.button('Return to main', pygame_menu.events.BACK)

    chooseModelGamesMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Choose model games',
        width=width
    )

    menu = chooseModelGamesMenu
    menu.add.selector('You play', [("White", 0), ("Black", 1)],
                      default=getCurrentColorIndex() if getCurrentColorIndex() < 2 else 0,
                      onchange=setPositionColor)
    menu.add.button('Choose file', chooseModelFile)
    menu.add.button('Play', playModels)
    menu.add.button('Return to main', pygame_menu.events.BACK)

    chooseBlundersParamsMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Choose position filter',
        width=width
    )
    menu = chooseBlundersParamsMenu
    menu.add.text_input('ECO (optional)', onchange=setPositionEco)
    menu.add.selector('You play', [("White", 0), ("Black", 1), ("Any", 2)], onchange=setPositionColor)
    menu.add.button('Play', replayBlunders)
    menu.add.button('Return to main', pygame_menu.events.BACK)


    main_menu = pygame_menu.Menu('Chess Phyton', width, height,
                                 theme=pygame_menu.themes.THEME_BLUE)
    main_menu.add.button('Play against computer', choosePlayParamsMenu)
    main_menu.add.button('Play between humans', humanPlay)
    main_menu.add.button('Learn openings', chooseOpeningParamsMenu)
    main_menu.add.button('Review blunders', chooseBlundersParamsMenu)
    main_menu.add.button('Exercise by models', chooseModelGamesMenu)
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
    p.init()
    global screen
    global W
    global H
    global manager

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
    
    UCIEngines.engine_close()
    sys.exit()


if __name__ == "__main__":
    runMain()
