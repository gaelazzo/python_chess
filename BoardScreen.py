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
import UCIEngines

DIMENSION = 8
MOVELOGFONT:Optional[p.font.Font] = None
BOOKFONT:Optional[p.font.Font] = None

BOARD_WIDTH = 512
BOARD_HEIGHT = BOARD_WIDTH

SQ_SIZE = BOARD_HEIGHT / DIMENSION
MAX_FPS = 60
factor = 2.0
IMAGES:Dict[str,p.Surface] = {}

# Top strip for the icon-button toolbar (tools). Everything else (board +
# panels + nav bar + CPU strip) is pushed down by TOOLBAR_HEIGHT.
TOOLBAR_HEIGHT = 40
BOARD_Y = TOOLBAR_HEIGHT

# Bottom navigation toolbar: sits DIRECTLY UNDER THE BOARD (board width), between
# the board and the engine/eval strip. Only the analysis screen draws buttons
# here; the other modes simply leave the strip empty. The whole window is a bit
# taller to make room (CPU_Y / SIDE_HEIGHT / SCREEN_HEIGHT all account for it).
NAV_HEIGHT = 44
NAV_X = 0
NAV_WIDTH = BOARD_WIDTH
NAV_Y = BOARD_Y + BOARD_HEIGHT

MOVE_LOG_WIDTH = 250
MOVE_LOG_X = BOARD_WIDTH
MOVE_LOG_Y = TOOLBAR_HEIGHT
whiteUp = False

ANALYSYS_PANEL_WIDTH = MOVE_LOG_WIDTH

# Engine / eval bar: sits UNDER THE BOARD ONLY (board width), below the nav bar.
CPU_HEIGHT = BOARD_HEIGHT // 3
CPU_WIDTH = BOARD_WIDTH
CPU_X = 0
CPU_Y = BOARD_HEIGHT + TOOLBAR_HEIGHT + NAV_HEIGHT

# The two side columns run the FULL content height -- past the board, down beside
# the nav bar and the engine bar -- so the panels are TALLER than the board and
# stop clipping their content at the bottom (Personal Stats / book / move lists
# were cut off).
SIDE_HEIGHT = BOARD_HEIGHT + NAV_HEIGHT + CPU_HEIGHT
ANALYSYS_PANEL_HEIGHT = SIDE_HEIGHT

# Column 2 (next to the board): move log on top (2/3), PGN-moves panel below (1/3).
MOVE_LOG_HEIGHT = 2 * (SIDE_HEIGHT // 3)
PGN_WIDTH = MOVE_LOG_WIDTH
PGN_X = MOVE_LOG_X
PGN_Y = MOVE_LOG_Y + MOVE_LOG_HEIGHT
PGN_HEIGHT = SIDE_HEIGHT - MOVE_LOG_HEIGHT

# Column 3 (analysis): opening book on top (keeps its old size), Personal Stats
# below -- and Personal Stats takes ALL the extra height of the taller column.
BOOK_HEIGHT = 2 * (BOARD_HEIGHT // 3) - 90
BOOK_WIDTH = ANALYSYS_PANEL_WIDTH
BOOK_X = BOARD_WIDTH + MOVE_LOG_WIDTH
BOOK_Y = TOOLBAR_HEIGHT

DBSTATS_WIDTH = ANALYSYS_PANEL_WIDTH
DBSTATS_X = BOARD_WIDTH + MOVE_LOG_WIDTH
DBSTATS_Y = BOOK_HEIGHT + TOOLBAR_HEIGHT
DBSTATS_HEIGHT = SIDE_HEIGHT - BOOK_HEIGHT

SCREEN_WIDTH = BOARD_WIDTH + MOVE_LOG_WIDTH + ANALYSYS_PANEL_WIDTH
SCREEN_HEIGHT = TOOLBAR_HEIGHT + BOARD_HEIGHT + NAV_HEIGHT + CPU_HEIGHT

clock:Optional[p.time.Clock] = None


colors = [p.Color("white"), p.Color("gray")]

show_book = True
show_pgn = True
show_cpu = True

# Shared side-panel singletons: ONE instance per box, the single render()/clear()
# interface every writer goes through (drawGameState, the engine callback,
# play_game). Built in init() once the fonts exist; None until then. Because each
# panel reads its rect lazily from the geometry constants above, moving a panel
# moves it for everyone.
book = None
engine = None
pgn = None
movelog = None
dbstats = None

# Context label shown at the top of the move log (e.g. "Training: c96" or
# "Opening: openings.pgn") and replicated in the window caption. Set by
# the various modes on entry and cleared on exit. None = no label.
context_label: Optional[str] = None
_DEFAULT_CAPTION = 'Hires Chess Trainer'


def set_context_label(label: Optional[str]) -> None:
    """Set the context label (move log + window caption).
    Pass None to reset (typically in a finally at the end of a mode)."""
    global context_label
    context_label = label
    try:
        if label:
            p.display.set_caption(f"{_DEFAULT_CAPTION} -- {label}")
        else:
            p.display.set_caption(_DEFAULT_CAPTION)
    except p.error:
        pass   # display not yet initialized (e.g. headless test)

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
    # Segoe UI Symbol (Win) / Cambria Math cover the chess annotation glyphs
    # (= ± ∓ ⩲ ⩱ ∞ □ ⨀); Arial does not. Fall back gracefully elsewhere.
    MOVELOGFONT = p.font.SysFont("Segoe UI Symbol,Cambria Math,DejaVu Sans,Arial", 16, False, False)
    BOOKFONT = p.font.SysFont("Arial", 14, False, False)

    # Build the shared side-panel singletons now that the fonts exist. Local
    # import keeps the BoardScreen<->panels dependency one-way (no import cycle).
    global book, engine, pgn, movelog, dbstats
    from panels import BookPanel, EnginePanel, TextLinesPanel, MoveLogPanel
    # A slightly bigger font for the book + PGN boxes (readability), kept separate
    # from BOOKFONT so the dense CPU/engine strip stays at its compact size.
    panel_font = p.font.SysFont("Arial", 16, False, False)
    book = BookPanel(font=panel_font)
    engine = EnginePanel()
    pgn = TextLinesPanel(
        lambda: p.Rect(PGN_X, PGN_Y, PGN_WIDTH, PGN_HEIGHT), title="PGN moves",
        font=panel_font)
    dbstats = TextLinesPanel(
        lambda: p.Rect(DBSTATS_X, DBSTATS_Y, DBSTATS_WIDTH, DBSTATS_HEIGHT),
        title="Personal Stats",
        font=p.font.SysFont('Consolas,Courier New,Lucida Console', 16),
    )
    movelog = MoveLogPanel(
        lambda: p.Rect(MOVE_LOG_X, MOVE_LOG_Y, MOVE_LOG_WIDTH, MOVE_LOG_HEIGHT),
        font=MOVELOGFONT)

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


def stop_requested() -> bool:
    """True if the user asked to interrupt a long-running work loop (e.g. PGN
    analysis): ESC key or the window close button. Drains the pending events
    (so it doubles as the event.pump() that keeps the window responsive), hence
    call it ONLY from a blocking work loop, never from the normal game loop.
    A QUIT is re-posted so the app can still close cleanly after the caller
    has saved and returned."""
    stop = False
    for e in p.event.get():
        if e.type == p.QUIT:
            p.event.post(p.event.Event(p.QUIT))
            stop = True
        elif e.type == p.KEYDOWN and e.key == p.K_ESCAPE:
            stop = True
    return stop

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
                p.Rect(startCol * SQ_SIZE, BOARD_Y + 3 * SQ_SIZE, 4 * SQ_SIZE, 2 * SQ_SIZE))
    myfont = p.font.SysFont('Comic Sans MS', 20)
    textsurface = myfont.render('Choose piece to promote to', False, p.Color("black"))
    screen.blit(textsurface, (startCol * SQ_SIZE, BOARD_Y + 3 * SQ_SIZE))

    for i in range(4):
        piece = color + pieces[i]
        screen.blit(IMAGES[piece], p.Rect((startCol + i) * SQ_SIZE, BOARD_Y + 4 * SQ_SIZE, SQ_SIZE, SQ_SIZE))

    while True:
        for e in p.event.get():
            if e.type == p.QUIT:
                return None
            elif e.type == p.MOUSEBUTTONDOWN:
                location = p.mouse.get_pos()
                col = int(location[0] // SQ_SIZE) - startCol
                if not (0 <= col <= 3):
                    return None
                row = int((location[1] - BOARD_Y) // SQ_SIZE)
                if row != 4:
                    return None
                return color + pieces[col]
        update()

def getRowColFromLocation(location):
    # Click above the board strip (e.g. in the toolbar) -> coordinates outside the board
    # so callers (which already filter col>=8 / row>=8) ignore it safely.
    y = location[1] - BOARD_Y
    if y < 0:
        return 8, 8
    col = adjustedCol(int(location[0] // SQ_SIZE))
    row = adjustedRow(int(y // SQ_SIZE))
    return row, col

def resource_path(relative_path):
    """Return the absolute path, compatible with PyInstaller."""
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
            p.draw.rect(screen, color, p.Rect(c * SQ_SIZE, BOARD_Y + r * SQ_SIZE, SQ_SIZE, SQ_SIZE))


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
                    screen.blit(IMAGES[piece], p.Rect(adjustedCol(c) * SQ_SIZE, BOARD_Y + adjustedRow(r) * SQ_SIZE, SQ_SIZE, SQ_SIZE))

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
    # The text is centered below; a line wider than the board would start at a
    # negative x and get clipped on the left. Shrink the font until it fits.
    while size > 8 and font.size(text)[0] > BOARD_WIDTH - 10:
        size -= 1
        font = p.font.SysFont("Helvetica", size, True, False)
    textObject = font.render(text, False, p.Color("Gray"))
    textLocation = p.Rect(0, BOARD_Y, BOARD_WIDTH, BOARD_HEIGHT).move((BOARD_WIDTH - textObject.get_width()) / 2,
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



# Blue "only move" arrow (semi-transparent), drawn over the pieces.
ONLY_MOVE_ARROW_COLOR = (40, 110, 240, 215)


def _square_center(square):
    """Pixel centre of a chess square, honouring the current board orientation.
    `square` is a python-chess square index (0=a1 .. 63=h8)."""
    internal_row = 7 - chess.square_rank(square)   # row 0 = rank 8 (see notes above)
    internal_col = chess.square_file(square)        # col 0 = file a
    sc = adjustedCol(internal_col)
    sr = adjustedRow(internal_row)
    return (sc * SQ_SIZE + SQ_SIZE / 2, BOARD_Y + sr * SQ_SIZE + SQ_SIZE / 2)


def drawArrow(screen, from_square, to_square, color=ONLY_MOVE_ARROW_COLOR):
    """Draw a thick arrow from `from_square` to `to_square` on the board."""
    sx, sy = _square_center(from_square)
    ex, ey = _square_center(to_square)
    overlay = p.Surface((BOARD_WIDTH, BOARD_HEIGHT), p.SRCALPHA)
    sy -= BOARD_Y
    ey -= BOARD_Y
    dx, dy = ex - sx, ey - sy
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist
    head = SQ_SIZE * 0.40
    width = max(4, int(SQ_SIZE * 0.14))
    bx, by = ex - ux * head, ey - uy * head      # base of the arrowhead
    px, py = -uy, ux                              # perpendicular unit
    half = head * 0.62
    p.draw.line(overlay, color, (sx, sy), (bx, by), width)
    p.draw.polygon(overlay, color,
                   [(ex, ey), (bx + px * half, by + py * half), (bx - px * half, by - py * half)])
    screen.blit(overlay, (0, BOARD_Y))


def _draw_only_move_arrow(screen):
    """If the live engine analysis flagged an only move, draw its blue arrow."""
    mv = getattr(UCIEngines, "latest_only_move", None)
    if mv is not None and UCIEngines.is_analysing():
        drawArrow(screen, mv.from_square, mv.to_square)


# Plan arrows from the masters-plans popup: White's moves white, Black's black.
PLAN_ARROW_WHITE = (245, 245, 245, 225)
PLAN_ARROW_BLACK = (20, 20, 20, 235)
plan_arrows = []   # list of (from_square, to_square, color)


def set_plan_arrows(arrows):
    """Set (or clear, with [] ) the plan arrows shown over the board."""
    global plan_arrows
    plan_arrows = list(arrows or [])


def _draw_plan_arrows(screen):
    for fr, to, col in plan_arrows:
        drawArrow(screen, fr, to, col)


def draw_board_only(screen, gs):
    """Redraw just the board (pieces + arrows) and flip its rect -- used to show
    plan arrows live while the masters-plans popup is open over the side panel."""
    drawBoard(screen)
    drawPieces(screen, gs)
    _draw_only_move_arrow(screen)
    _draw_plan_arrows(screen)
    p.display.update(p.Rect(0, BOARD_Y, BOARD_WIDTH, BOARD_HEIGHT))


def highlightCircles(screen, squares):
    for s in squares:
        draw_circle_alpha(screen, s[2], (adjustedRow(s[1]) * SQ_SIZE + SQ_SIZE // 2,
                                                      BOARD_Y + adjustedCol(s[0]) * SQ_SIZE + SQ_SIZE // 2), SQ_SIZE // 4)


def highlightSquaresColor(screen, squares):
    for s in squares:
        draw_rect_alpha(screen, s[2],
                        p.Rect(adjustedRow(s[1]) * SQ_SIZE, BOARD_Y + adjustedCol(s[0]) * SQ_SIZE, SQ_SIZE, SQ_SIZE))

def add_txt_line(t: str, text_y: int, font, screen, move_log_rect, padding, line_spacing, color="white") -> int:
    text_object = font.render(t, True, p.Color(color))
    text_location = move_log_rect.move(padding, text_y)
    screen.blit(text_object, text_location)
    return text_object.get_height() + line_spacing

def book_lines(gs):
    """Opening-book move strings (UCI) for the current position; [] if none.
    The single source feeding the shared `book` panel (BookPanel caps at 10)."""
    return [entry.move.uci() for entry in (gs.getMovesFromBook() or [])]


def pgn_lines(gs):
    """Feeds the `pgn` panel: the next main move + its alternative variations
    (the upcoming fork), so navigating you see a branch coming."""
    return gs.getNextMoveLines()


def drawGameState(screen, gs, toHighlightCirclesColor, toHighlightSquareColor, sqSelected):
    drawBoard(screen)
    if sqSelected != ():
        p.draw.rect(screen, p.Color("lightgreen"),
                    p.Rect(adjustedRow(sqSelected[1]) * SQ_SIZE,
                           BOARD_Y + adjustedCol(sqSelected[0]) * SQ_SIZE, SQ_SIZE, SQ_SIZE))

    highlightCircles(screen, toHighlightCirclesColor)
    highlightSquaresColor(screen, toHighlightSquareColor)
    drawPieces(screen, gs)
    _draw_only_move_arrow(screen)   # blue arrow when the engine found an only move
    _draw_plan_arrows(screen)       # white/black arrows when a plan variant is selected

    # Side boxes through the shared panel singletons (the one render/clear per
    # box). visible=show_* means a hidden panel renders as just a cleared rect,
    # so the old "if show: draw else: clear" collapses into one render() each.
    movelog.render(screen, gs)
    book.visible = show_book
    book.render(screen, book_lines(gs) if show_book else [])
    pgn.visible = show_pgn
    pgn.render(screen, pgn_lines(gs) if show_pgn else [])
    # DB-stats slot (analysis column, lower third): blanked here; the analysis
    # mode's own render paints it.
    dbstats.clear(screen)
    # NB: no present here -- every caller flips after drawing (one-shot calls do
    # BS.update() right after; the loops flip once per iteration; play_game repaints
    # book/pgn/dbstats from its view-model first). Presenting here would show those
    # boxes cleared for one frame before play_game refills them = flicker.


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
        endSquare = p.Rect(adjustedCol(move.stopCol) * SQ_SIZE, BOARD_Y + adjustedRow(move.stopRow) * SQ_SIZE, SQ_SIZE, SQ_SIZE)
        p.draw.rect(screen, color, endSquare)

        if move.pieceCaptured != "--":
            if move.enPassant:
                enPassantRow = (move.stopRow + 1) if move.pieceCaptured[0] == "b" else move.stopRow - 1
                endSquare = p.Rect(adjustedCol(move.stopCol) * SQ_SIZE, BOARD_Y + adjustedRow(enPassantRow) * SQ_SIZE, SQ_SIZE, SQ_SIZE)

            screen.blit(IMAGES[move.pieceCaptured], endSquare)

        #  if move.pieceMoved != "--":
        screen.blit(IMAGES[move.pieceMoved], p.Rect(c * SQ_SIZE, BOARD_Y + r * SQ_SIZE, SQ_SIZE, SQ_SIZE))
        update()
        clock.tick(MAX_FPS)

    color = colors[(adjustedRow(move.stopRow) + adjustedCol(move.stopCol)) % 2]
    p.draw.rect(screen, color, p.Rect(adjustedCol(move.stopCol) * SQ_SIZE, BOARD_Y + adjustedRow(move.stopRow) * SQ_SIZE, SQ_SIZE, SQ_SIZE))
    drawPieces(screen, board)
    update()

    
