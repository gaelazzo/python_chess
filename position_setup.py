"""Visual position editor for the Play between humans (analysis) mode.

Launched with the **U** key (set**U**p) or from the "Setup" toolbar button. Modal:
takes over rendering until the user presses Apply / Cancel
(or ENTER / ESC). On Apply, it replaces the current GameState with a new
game whose initial position is the editor's FEN; saving to
PGN then goes through the usual **S** key (save_load.save_menu).

UI:
- On-screen board (BS.drawBoard / drawPieces) mounted on a `chess.Board`
  that we mutate directly in response to clicks.
- Piece palette in the CPU strip below the board: 6 white + 6 black +
  an "Erase" cell. The "armed" cell is highlighted in yellow.
- Buttons: STM (toggle W/B side to move), Clear (empty board), Initial (initial
  position), Apply, Cancel.

MVP limits: no UI for castling rights / en passant / halfmove clock --
they are rarely relevant for endgames (start clean clock) and an expert user
can edit the FEN by hand in the PGN. Can be added in V2.
"""
from __future__ import annotations

from typing import Optional, List, Tuple, Any

import chess
import chess.pgn
import pygame as p

import BoardScreen as BS
from app_context import app
from GameState import GameState


_PALETTE_PIECES = (chess.PAWN, chess.KNIGHT, chess.BISHOP,
                   chess.ROOK, chess.QUEEN, chess.KING)
_PIECE_LETTER = {
    chess.PAWN: 'P', chess.KNIGHT: 'N', chess.BISHOP: 'B',
    chess.ROOK: 'R', chess.QUEEN: 'Q', chess.KING: 'K',
}


def _board_square_from_pos(pos: Tuple[int, int]) -> Optional[int]:
    """Returns the square index (0..63) from a click on the screen, or None
    if the click is outside the board. Respects the current orientation
    (flip board)."""
    row, col = BS.getRowColFromLocation(pos)
    if row < 0 or row > 7 or col < 0 or col > 7:
        return None
    # row 0 = top in board coords, but chess.square_at wants rank from the bottom
    return chess.square((col), (7 - row))


def _draw_palette(screen, cells: List[Tuple[p.Rect, Any]], armed) -> None:
    """Draws the palette cells with the pieces (icons) and the eraser."""
    for rect, item in cells:
        # Cell background
        bg = p.Color('darkgray')
        if armed is not None and item == armed:
            bg = p.Color('gold')  # armed cell highlighted
        p.draw.rect(screen, bg, rect)
        p.draw.rect(screen, p.Color('black'), rect, 1)
        if item == 'eraser':
            font = p.font.SysFont('Arial', 14, bold=True)
            txt = font.render('Erase', False, p.Color('black'))
            screen.blit(txt, txt.get_rect(center=rect.center))
        else:
            color, piece_type = item
            key = ('w' if color == chess.WHITE else 'b') + _PIECE_LETTER[piece_type]
            img = BS.IMAGES.get(key)
            if img is not None:
                # Center the image in the cell (images are SQ_SIZE=64,
                # cells are 48 -> we scale on the fly)
                scaled = p.transform.scale(img, (rect.width - 4, rect.height - 4))
                screen.blit(scaled, scaled.get_rect(center=rect.center))


def _draw_buttons(screen, buttons: List[Tuple[p.Rect, str]], stm_white: bool,
                   error: str) -> None:
    font = p.font.SysFont('Arial', 14, bold=True)
    for rect, label in buttons:
        if label == 'STM':
            label = 'W to move' if stm_white else 'B to move'
        p.draw.rect(screen, p.Color('steelblue'), rect)
        p.draw.rect(screen, p.Color('black'), rect, 1)
        txt = font.render(label, False, p.Color('white'))
        screen.blit(txt, txt.get_rect(center=rect.center))
    if error:
        font_err = p.font.SysFont('Arial', 14, bold=True)
        msg = font_err.render(f"Error: {error}", False, p.Color('red'))
        screen.blit(msg, (8, BS.CPU_Y + BS.CPU_HEIGHT - 22))


def _validate(board: chess.Board) -> Tuple[bool, str]:
    """Minimal checks for a sensible FEN in endgame/study mode.

    NB: we do not call board.is_valid() because it is typical for study
    positions to have "anomalous" material (e.g. 3 knights) or adjacent kings
    without a regular context. We validate only the essentials to avoid crashes.
    """
    n_wk = chess.popcount(board.kings & board.occupied_co[chess.WHITE])
    n_bk = chess.popcount(board.kings & board.occupied_co[chess.BLACK])
    if n_wk != 1:
        return False, f"exactly 1 white king required (found {n_wk})"
    if n_bk != 1:
        return False, f"exactly 1 black king required (found {n_bk})"
    # Pawns on the 1st or 8th rank = illegal position
    pawns = int(board.pawns)
    if pawns & 0x00000000000000FF or pawns & 0xFF00000000000000:
        return False, "pawns on the 1st or 8th rank"
    # Is the FEN parsable?
    try:
        chess.Board(board.fen())
    except Exception as ex:
        return False, f"FEN not parsable ({ex})"
    # The opponent's king CANNOT be in check when it's our turn: it would mean
    # the opponent left their own king under attack on the previous move,
    # a position impossible to reach in a real game.
    opp = not board.turn
    opp_king_sq = board.king(opp)
    if opp_king_sq is not None and board.is_attacked_by(board.turn, opp_king_sq):
        opp_name = "black" if opp == chess.BLACK else "white"
        side_name = "white" if board.turn == chess.WHITE else "black"
        return False, (f"{opp_name} king in check but it's {side_name} to move "
                       f"(illegal position)")
    return True, ""


def _build_game_from_board(board: chess.Board) -> chess.pgn.Game:
    g = chess.pgn.Game()
    g.headers["FEN"] = board.fen()
    g.headers["SetUp"] = "1"
    g.headers["Event"] = "Position setup"
    return g


def run(gs: GameState) -> bool:
    """Enters the setup sub-mode. Mutates `gs` (via setPgn) if the user
    applies. Returns True if applied, False if cancelled.

    Starts from the current position of `gs` (so you can edit it); to
    start over from scratch use the "Clear" button inside the editor.
    """
    # Initial snapshot (with castling/clock cleared for the "freshness" typical
    # of study positions). The user can reload the standard starting position
    # with the "Initial" button.
    try:
        start = gs.node.board().copy() if gs.node is not None else chess.Board()
    except Exception:
        start = chess.Board()
    board = start
    board.castling_rights = 0
    board.ep_square = None
    board.halfmove_clock = 0
    board.fullmove_number = 1

    armed = None  # (color, piece_type) | 'eraser' | None
    error = ""

    # Layout: palette pieces in the CPU strip
    CELL = 48
    PALETTE_Y = BS.CPU_Y + 8
    cells: List[Tuple[p.Rect, Any]] = []
    x = 8
    for color in (chess.WHITE, chess.BLACK):
        for piece in _PALETTE_PIECES:
            cells.append((p.Rect(x, PALETTE_Y, CELL, CELL), (color, piece)))
            x += CELL + 2
        x += 12  # gap between white and black
    cells.append((p.Rect(x, PALETTE_Y, CELL, CELL), 'eraser'))

    # Buttons below the palette
    BTN_W, BTN_H = 96, 30
    BTN_Y = PALETTE_Y + CELL + 8
    buttons: List[Tuple[p.Rect, str]] = []
    bx = 8
    for lbl in ('STM', 'Clear', 'Initial', 'Paste FEN', 'Apply', 'Cancel'):
        buttons.append((p.Rect(bx, BTN_Y, BTN_W, BTN_H), lbl))
        bx += BTN_W + 4

    applied = False
    running = True
    while running:
        app.clock.tick(60)

        # Temporary GameState to draw via BS (requires SetUp+FEN)
        tmp_gs = GameState()
        try:
            tmp_game = _build_game_from_board(board)
            tmp_gs.setPgn(tmp_game)
        except Exception:
            tmp_gs = None

        # Render
        app.main_background()
        BS.drawBoard(app.screen)
        if tmp_gs is not None:
            BS.drawPieces(app.screen, tmp_gs)
        # Palette area: clear and draw (reuses the CPU-strip rect via its panel)
        BS.engine.clear(app.screen)
        _draw_palette(app.screen, cells, armed)
        _draw_buttons(app.screen, buttons, board.turn == chess.WHITE, error)
        BS.update()

        for e in p.event.get():
            if e.type == p.QUIT:
                running = False
            elif e.type == p.KEYDOWN:
                if e.key == p.K_ESCAPE:
                    running = False
                elif e.key == p.K_RETURN:
                    ok, msg = _validate(board)
                    if ok:
                        gs.setPgn(_build_game_from_board(board))
                        applied = True
                        running = False
                    else:
                        error = msg
            elif e.type == p.MOUSEBUTTONDOWN:
                # 1) buttons
                clicked_button = None
                for rect, lbl in buttons:
                    if rect.collidepoint(e.pos):
                        clicked_button = lbl
                        break
                if clicked_button is not None:
                    if clicked_button == 'STM':
                        board.turn = not board.turn
                    elif clicked_button == 'Clear':
                        board.clear()
                    elif clicked_button == 'Initial':
                        board = chess.Board()
                        board.castling_rights = 0  # for consistency with study positions
                    elif clicked_button == 'Paste FEN':
                        # Import a FEN from the clipboard. Also accepts partial
                        # FENs (e.g. only the piece-placement + side-to-move fields)
                        # thanks to the python-chess parser.
                        try:
                            import pyperclip
                            text = (pyperclip.paste() or '').strip()
                            if not text:
                                error = "empty clipboard"
                            else:
                                # python-chess accepts a FEN as a whole string.
                                candidate = chess.Board(text)
                                board = candidate
                                error = ""
                        except ValueError as ex:
                            error = f"invalid FEN: {ex}"
                        except Exception as ex:
                            error = f"clipboard not readable ({ex})"
                    elif clicked_button == 'Apply':
                        ok, msg = _validate(board)
                        if ok:
                            gs.setPgn(_build_game_from_board(board))
                            applied = True
                            running = False
                        else:
                            error = msg
                    elif clicked_button == 'Cancel':
                        running = False
                    continue
                # 2) palette
                palette_hit = False
                for rect, item in cells:
                    if rect.collidepoint(e.pos):
                        armed = item
                        error = ""
                        palette_hit = True
                        break
                if palette_hit:
                    continue
                # 3) board
                sq = _board_square_from_pos(e.pos)
                if sq is None:
                    continue
                if e.button == 3 or armed == 'eraser':
                    board.remove_piece_at(sq)
                elif e.button == 1 and armed is not None:
                    color, piece_type = armed
                    board.set_piece_at(sq, chess.Piece(piece_type, color))

    return applied
