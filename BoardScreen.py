import pygame as p
import math
import pygame_gui
from Board import GameState
import chess
from typing import Optional,List,Dict,Tuple,Dict
import pygame.surface

DIMENSION = 8
MOVELOGFONT:Optional[p.Font] = None

BOARD_WIDTH = 512
BOARD_HEIGHT = BOARD_WIDTH

SQ_SIZE = BOARD_HEIGHT / DIMENSION
MAX_FPS = 30
IMAGES:Dict[str,p.Surface] = {}
MOVE_LOG_PANEL_HEIGHT = BOARD_HEIGHT
MOVE_LOG_PANEL_WIDTH = 250
whiteUp = False

clock:Optional[p.time.Clock] = None


colors = [p.Color("white"), p.Color("gray")]


def init():
    global MOVELOGFONT
    global clock

    loadImages()
    MOVELOGFONT = p.font.SysFont("Arial", 14, False, False)
    height = BOARD_HEIGHT
    width = BOARD_WIDTH+MOVE_LOG_PANEL_WIDTH
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

# load all images
def loadImages():
    pieces = ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR", "bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR", "bP",
              "wP"]
    for piece in pieces:
        IMAGES[piece] = p.transform.scale(p.image.load("images/" + piece + ".png"), (SQ_SIZE, SQ_SIZE))


 
def drawBoard(screen):
    global colors
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            color = colors[(r + c) % 2]
            p.draw.rect(screen, color, p.Rect(c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE))


def drawPieces(screen, board: GameState):
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            piece = board.piece_at(r, c)
            if piece != "--":
                    screen.blit(IMAGES[piece], p.Rect(adjustedCol(c) * SQ_SIZE, adjustedRow(r) * SQ_SIZE, SQ_SIZE, SQ_SIZE))


def drawEndGameText(screen, text):
    font = p.font.SysFont("Helvetica", 32, True, False)
    textObject = font.render(text, False, p.Color("Gray"))
    textLocation = p.Rect(0, 0, BOARD_WIDTH, BOARD_HEIGHT).move((BOARD_WIDTH - textObject.get_width()) / 2,
                                                                (BOARD_HEIGHT - textObject.get_height()) / 2)
    screen.blit(textObject, textLocation)
    textObject = font.render(text, False, p.Color("Black"))
    screen.blit(textObject, textLocation.move(2, 2))

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



def drawMoveLog(screen, gs):
    movesPerRow = 3
    assert(MOVELOGFONT is not None)
    font:p.Font = MOVELOGFONT
    moveLogRect = p.Rect(BOARD_WIDTH,0,MOVE_LOG_PANEL_WIDTH,MOVE_LOG_PANEL_HEIGHT)
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

    def addTxtLine(t):
        nonlocal textY
        textObject = font.render(t, True, p.Color("white"))
        textLocation = moveLogRect.move(padding, textY)
        screen.blit(textObject, textLocation)
        textY += textObject.get_height() + lineSpacing

    header = gs.getHeader()
    for i in range(len(header)):
        addTxtLine(header[i])

    for i in range(0, len(moveTexts), movesPerRow):
        text = ""
        for j in range(movesPerRow):
            if i+j < len(moveTexts):
                text += moveTexts[i+j]+" "
        #str(moveTexts[i])
        addTxtLine(text)

    evaluation = gs.getEvaluation()
    if evaluation is not None:
        addTxtLine(f"Evaluation is {evaluation}")

    update()


def animateMove(move, screen, board):
    global colors
    global MAX_FPS
    update()
    dR = adjustedRow(move.stopRow) - adjustedRow(move.startRow)
    dC = adjustedCol(move.stopCol) - adjustedCol(move.startCol)
    framesPerSquare = int(MAX_FPS/3)
    framesCount = framesPerSquare #  math.sqrt(dR**2 + dC**2) *

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

    color = colors[(adjustedRow(move.stopRow) + adjustedCol(move.stopCol)) % 2]
    p.draw.rect(screen, color, p.Rect(adjustedCol(move.stopCol) * SQ_SIZE, adjustedRow(move.stopRow) * SQ_SIZE, SQ_SIZE, SQ_SIZE))
    drawPieces(screen, board)
    update()