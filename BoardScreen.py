import pygame as p
import math
import pygame_gui
from GameState import GameState
import chess
from typing import Optional,List,Dict,Tuple,Dict
import pygame.surface
import sys
import os
import pyttsx3

DIMENSION = 8
MOVELOGFONT:Optional[p.Font] = None
BOOKFONT:Optional[p.Font] = None

BOARD_WIDTH = 512
BOARD_HEIGHT = BOARD_WIDTH

SQ_SIZE = BOARD_HEIGHT / DIMENSION
MAX_FPS = 60
factor = 2.0
IMAGES:Dict[str,p.Surface] = {}
MOVE_LOG_HEIGHT = BOARD_HEIGHT
MOVE_LOG_WIDTH = 250
MOVE_LOG_X = BOARD_WIDTH
MOVE_LOG_Y = 0
whiteUp = False

ANALYSYS_PANEL_HEIGHT = BOARD_HEIGHT
ANALYSYS_PANEL_WIDTH = MOVE_LOG_WIDTH

BOOK_HEIGHT = 2* (BOARD_HEIGHT // 3)
BOOK_WIDTH = ANALYSYS_PANEL_WIDTH
BOOK_X = BOARD_WIDTH + MOVE_LOG_WIDTH
BOOK_Y = 0

PGN_HEIGHT = BOARD_HEIGHT - BOOK_HEIGHT
PGN_WIDTH = ANALYSYS_PANEL_WIDTH
PGN_X = BOARD_WIDTH + MOVE_LOG_WIDTH
PGN_Y = BOOK_HEIGHT

CPU_WIDTH = ANALYSYS_PANEL_WIDTH+BOARD_WIDTH+ANALYSYS_PANEL_WIDTH
CPU_HEIGHT = BOARD_HEIGHT // 3
CPU_X = 0
CPU_Y = BOARD_HEIGHT

SCREEN_WIDTH = BOARD_WIDTH + MOVE_LOG_WIDTH + ANALYSYS_PANEL_WIDTH
SCREEN_HEIGHT = BOARD_HEIGHT+ CPU_HEIGHT

clock:Optional[p.time.Clock] = None


colors = [p.Color("white"), p.Color("gray")]

show_book = True
show_pgn = True
show_cpu = True

def getFactor():
    global factor
    return factor

def setFactor(f):
    global factor
    if f>20:
        f=20

    if f < 0.1:
        f=0.1

    factor = f

def init():
    global MOVELOGFONT,BOOKFONT
    global clock

    loadImages()
    MOVELOGFONT = p.font.SysFont("Arial", 14, False, False)
    BOOKFONT = p.font.SysFont("Arial", 14, False, False)
    height = SCREEN_HEIGHT
    width = SCREEN_WIDTH
    clock = p.time.Clock()
    return width, height


def update():
    global clock
    global MAX_FPS
    #p.display.flip()
    p.display.update()
    assert(clock is not None)
    clock.tick(MAX_FPS)

def setWhiteUp(screen, up):
    global whiteUp
    whiteUp = up
    drawBoard(screen)

def flipBoard(screen):
    global whiteUp
    whiteUp = not whiteUp
    drawBoard(screen)

def choosePromotion(screen, color):
    pieces = ["R", "N", "B", "Q"]
    startCol = 2
    # Bishop, Knight, Rook, Queen
    p.draw.rect(screen, p.Color("lightyellow"),
                p.Rect(startCol * SQ_SIZE, 3 * SQ_SIZE, 4 * SQ_SIZE, 2 * SQ_SIZE))
    myfont = p.font.SysFont('Comic Sans MS', 20)
    textsurface = myfont.render('Choose piece to promote to', False, p.Color("black"))
    screen.blit(textsurface, (startCol * SQ_SIZE, 3 * SQ_SIZE))

    for i in range(4):
        piece = color + pieces[i]
        screen.blit(IMAGES[piece], p.Rect((startCol + i) * SQ_SIZE, 4 * SQ_SIZE, SQ_SIZE, SQ_SIZE))

    while True:
        for e in p.event.get():
            if e.type == p.QUIT:
                return None
            elif e.type == p.MOUSEBUTTONDOWN:
                location = p.mouse.get_pos()
                col = int(location[0] // SQ_SIZE) - startCol
                if not (0 <= col <= 3):
                    return None
                row = int(location[1] // SQ_SIZE)
                if row != 4:
                    return None
                return color + pieces[col]
        update()

def getRowColFromLocation(location):
    col = adjustedCol(int(location[0] // SQ_SIZE))
    row = adjustedRow(int(location[1] // SQ_SIZE))
    return row,col

def resource_path(relative_path):
    """Restituisce il path assoluto, compatibile con PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# load all images
def loadImages():
    pieces = ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR", "bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR", "bP",
              "wP"]
    for piece in pieces:
        IMAGES[piece] = p.transform.scale(p.image.load(resource_path("images/" + piece + ".png")), (SQ_SIZE, SQ_SIZE))


 
def drawBoard(screen):
    global colors
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            color = colors[(r + c) % 2]
            p.draw.rect(screen, color, p.Rect(c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE))


def drawPieces(screen, board: GameState):
    '''
       Draws the pieces on the board based on the current game state.
       Arguments:
       screen: The pygame screen to draw on.
       board: The current game state containing the board and pieces.
    '''

    for r in range(DIMENSION):
        for c in range(DIMENSION):
            piece = board.piece_at(r, c)
            if piece != "--":
                    screen.blit(IMAGES[piece], p.Rect(adjustedCol(c) * SQ_SIZE, adjustedRow(r) * SQ_SIZE, SQ_SIZE, SQ_SIZE))

def redraw(screen, board):
        drawBoard(screen)
        if board is not None:
            drawPieces(screen, board)
        

def drawEndGameText(screen, board, text,size=32):
    '''
    Draws a message in the center of the board.
    '''
    redraw(screen, board)
    font = p.font.SysFont("Helvetica", size, True, False)
    textObject = font.render(text, False, p.Color("Gray"))
    textLocation = p.Rect(0, 0, BOARD_WIDTH, BOARD_HEIGHT).move((BOARD_WIDTH - textObject.get_width()) / 2,
                                                                (BOARD_HEIGHT - textObject.get_height()) / 2)
    screen.blit(textObject, textLocation)
    textObject = font.render(text, False, p.Color("Black"))
    screen.blit(textObject, textLocation.move(2, 2))
    update()

# board first row are black pieces
# board last row are white pieces
# board first column is A
# board last column is H


def adjustedRow(n):
    """
    converts video row to game row
    param n: video row (first is 0 last is 7)
    return: board row (0 is first white row)
    """
    global whiteUp
    # if white up first row is 0  last row is 7
    # otherwise first row is 7 last row is 0
    if n >= 8:
        return n
    if not whiteUp:
        return n
    #white is up: must swap row numbers
    return 7-n

def adjustedCol(n):
    """
    converts video column to game column
    param n:
    return:
    """
    # if white up first column is H last column is A
    # otherwise first column is A last is H
    global whiteUp
    if n >= 8:
        return n
    if whiteUp:
        return 7 - n
    return n


def draw_rect_alpha(surface, color, rect):
    # surface = p.Surface(screen.get_size())
    shape_surf = p.Surface(p.Rect(rect).size, p.SRCALPHA)
    p.draw.rect(shape_surf, color, shape_surf.get_rect())
    surface.blit(shape_surf, rect)


def draw_circle_alpha(surface, color, center, radius):
    target_rect = p.Rect(center, (0, 0)).inflate((radius * 2, radius * 2))
    shape_surf = p.Surface(target_rect.size, p.SRCALPHA)
    p.draw.circle(shape_surf, color, (radius, radius), radius)
    surface.blit(shape_surf, target_rect)


def draw_polygon_alpha(surface, color, points):
    lx, ly = zip(*points)
    min_x, min_y, max_x, max_y = min(lx), min(ly), max(lx), max(ly)
    target_rect = p.Rect(min_x, min_y, max_x - min_x, max_y - min_y)
    shape_surf = p.Surface(target_rect.size, p.SRCALPHA)
    p.draw.polygon(shape_surf, color, [(x - min_x, y - min_y) for x, y in points])
    surface.blit(shape_surf, target_rect)



def highlightCircles(screen, squares):
    for s in squares:
        draw_circle_alpha(screen, s[2], (adjustedRow(s[1]) * SQ_SIZE + SQ_SIZE // 2,
                                                      adjustedCol(s[0]) * SQ_SIZE + SQ_SIZE // 2), SQ_SIZE // 4)


def highlightSquaresColor(screen, squares):
    for s in squares:
        draw_rect_alpha(screen, s[2],
                        p.Rect(adjustedRow(s[1]) * SQ_SIZE, adjustedCol(s[0]) * SQ_SIZE, SQ_SIZE, SQ_SIZE))

def add_txt_line(t: str, text_y: int, font, screen, move_log_rect, padding, line_spacing, color="white") -> int:
    text_object = font.render(t, True, p.Color(color))
    text_location = move_log_rect.move(padding, text_y)
    screen.blit(text_object, text_location)
    return text_object.get_height() + line_spacing

def clearBook(screen):
    bookRect = p.Rect(BOOK_X, BOOK_Y, BOOK_WIDTH, BOOK_HEIGHT)
    p.draw.rect(screen, p.Color("black"), bookRect)
    return bookRect

def drawBook(screen, gs: GameState):    
    book = gs.getMovesFromBook()
    bookRect = clearBook(screen)
    if not book or not show_book:
        return
    myfont = BOOKFONT
    textsurface = myfont.render('Book moves', False, p.Color("white"))
    screen.blit(textsurface, (BOOK_X+ 5, BOOK_Y+ 5))
    padding = 5
    textY = padding
    lineSpacing = 2
    textY += textsurface.get_height() + lineSpacing  # <-- AGGIUNGI QUESTA RIGA
    for entry in book:
        textY+= add_txt_line(entry.move.uci(), textY, myfont, screen, bookRect, padding, lineSpacing)
        
    update()


def drawCpu(screen, text:List[str]):
    cpuRect = clearCPU(screen)
    if not show_cpu:
        return
    myfont = BOOKFONT
    textsurface = myfont.render('CPU', False, p.Color("white"))
    screen.blit(textsurface, (CPU_X + 5, CPU_Y + 5))
    padding = 5
    textY = padding
    lineSpacing = 2
    textY += textsurface.get_height() + lineSpacing  # <-- AGGIUNGI QUESTA RIGA
    for txt in text:
        textY+= add_txt_line(txt, textY, myfont, screen, cpuRect, padding, lineSpacing)
    update()

def clearCPU(screen):
    cpuRect = p.Rect(CPU_X, CPU_Y, CPU_WIDTH, CPU_HEIGHT)
    p.draw.rect(screen, p.Color("black"), cpuRect)
    return cpuRect

def clearPgn(screen):
    pgnRect = p.Rect(PGN_X, PGN_Y, PGN_WIDTH, PGN_HEIGHT)
    p.draw.rect(screen, p.Color("black"), pgnRect)
    return pgnRect

def drawPgn(screen, gs: GameState):    
    moves = gs.getNextMoves()
    pgnRect = clearPgn(screen)
    myfont = BOOKFONT
    textsurface = myfont.render('PGN moves', False, p.Color("white"))
    screen.blit(textsurface, (PGN_X + 5, PGN_Y+5))
    padding = 5
    textY = padding
    lineSpacing = 2
    textY += textsurface.get_height() + lineSpacing  # <-- AGGIUNGI QUESTA RIGA
   
    for move in moves:
        textY+= add_txt_line(move.uci(), textY, myfont, screen, pgnRect, padding, lineSpacing)

    update()


def drawGameState(screen, gs, toHighlightCirclesColor, toHighlightSquareColor, sqSelected):
    drawBoard(screen)
    if sqSelected != ():
        p.draw.rect(screen, p.Color("lightgreen"),
                    p.Rect(adjustedRow(sqSelected[1]) * SQ_SIZE,
                           adjustedCol(sqSelected[0]) * SQ_SIZE, SQ_SIZE, SQ_SIZE))

    highlightCircles(screen, toHighlightCirclesColor)
    highlightSquaresColor(screen, toHighlightSquareColor)
    drawPieces(screen, gs)
    drawMoveLog(screen, gs)
    if show_book:
        drawBook(screen, gs)
    else:
        clearBook(screen)

    if show_pgn:
        drawPgn(screen, gs)
    else:
        clearPgn(screen)


def drawMoveLog(screen, gs):    
    movesPerRow = 3
    assert(MOVELOGFONT is not None)
    font:p.Font = MOVELOGFONT
    moveLogRect = p.Rect(MOVE_LOG_X, MOVE_LOG_Y,MOVE_LOG_WIDTH,MOVE_LOG_HEIGHT)
    p.draw.rect(screen, p.Color("black"), moveLogRect)
    moveLog = gs.moveLog
    moveTexts = []  # [m.getChessNotation() for m in moveLog]
    for i in range(0, len(moveLog),2 ):
        moveString = str(i//2 + 1)+"."+ moveLog[i].prettyChessNotation()
        if i +1 < len(moveLog):
            moveString += " " + moveLog[i+1].prettyChessNotation()
        moveTexts.append(moveString)
    padding = 5
    textY = padding
    lineSpacing = 2

    header = gs.getHeader()
    for i in range(0, len(header), 2):
        key = header[i]
        value = header[i + 1] if i + 1 < len(header) else ""
        textY+= add_txt_line(f"{key}: {value}", textY, font, screen, moveLogRect, padding, lineSpacing)
        
    for i in range(0, len(moveTexts), movesPerRow):
        text = ""
        for j in range(movesPerRow):
            if i+j < len(moveTexts):
                text += moveTexts[i+j]+" "
        #str(moveTexts[i])
        textY+= add_txt_line(text, textY, font, screen, moveLogRect, padding, lineSpacing)

    evaluation = gs.getEvaluation()
    if evaluation is not None:
        textY+= add_txt_line(f"Evaluation is {evaluation}", textY, font, screen, moveLogRect, padding, lineSpacing)        

    update()


def animateMove(move, screen, board:GameState):
    global colors
    global MAX_FPS
    #print(f"Drawing move with MAX_FPS:{MAX_FPS} and factor {factor}")
    update()
    dR = adjustedRow(move.stopRow) - adjustedRow(move.startRow)
    dC = adjustedCol(move.stopCol) - adjustedCol(move.startCol)
    framesPerSquare = int(MAX_FPS/3)
    framesCount = int(framesPerSquare / factor) #  math.sqrt(dR**2 + dC**2) *

    for frame in range(framesCount+1):
        r, c = (adjustedRow(move.startRow) + (dR * frame) / framesCount,
                adjustedCol(move.startCol) + (dC * frame) / framesCount)

        drawBoard(screen)
        drawPieces(screen, board)

        color = colors[(move.stopRow + move.stopCol) % 2]
        endSquare = p.Rect(adjustedCol(move.stopCol) * SQ_SIZE, adjustedRow(move.stopRow) * SQ_SIZE, SQ_SIZE, SQ_SIZE)
        p.draw.rect(screen, color, endSquare)

        if move.pieceCaptured != "--":
            if move.enPassant:
                enPassantRow = (move.stopRow + 1) if move.pieceCaptured[0] == "b" else move.stopRow - 1
                endSquare = p.Rect(adjustedCol(move.stopCol) * SQ_SIZE, adjustedRow(enPassantRow) * SQ_SIZE, SQ_SIZE, SQ_SIZE)

            screen.blit(IMAGES[move.pieceCaptured], endSquare)

        #  if move.pieceMoved != "--":
        screen.blit(IMAGES[move.pieceMoved], p.Rect(c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE))
        update()
        clock.tick(MAX_FPS)

    color = colors[(adjustedRow(move.stopRow) + adjustedCol(move.stopCol)) % 2]
    p.draw.rect(screen, color, p.Rect(adjustedCol(move.stopCol) * SQ_SIZE, adjustedRow(move.stopRow) * SQ_SIZE, SQ_SIZE, SQ_SIZE))
    drawPieces(screen, board)
    update()

    