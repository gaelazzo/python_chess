"""Regenerate the README screenshots automatically.

Renders the board+panel screens off the main loop (so they always match the
CURRENT layout) and writes them to ``docs/img/``. Run it after a layout change
instead of taking screenshots by hand:

    python capture_screenshots.py            # write the real docs/img/*.png
    python capture_screenshots.py --preview  # write docs/img/_preview_*.png instead

Only the board/panel screens are automated here (those are the ones a layout
change breaks). The pygame_menu screens (main menu, Tools, Improve) are stable
and stay manual for now.
"""
from __future__ import annotations

import sys

import pygame as p
import pygame_gui
import chess

import safe_font
import BoardScreen as BS
from app_context import app
from GameState import GameState
from panels import BookPanel, EnginePanel, TextLinesPanel
from toolbar import Toolbar, ToolbarAction

# The analysis toolbar, as labels (mirrors modes/play_game.py). A screenshot only
# needs the row of buttons drawn, so the handlers are no-ops.
TOOLBAR_LABELS = ["Undo", "Next", "Save", "Anal", "Flip", "Reset", "Eng", "Book",
                  "Moves", "Stats", "C-FEN", "C-PGN", "Load", "Annot", "Cmnt",
                  "Notat", "Setup", "AddTac", "Quit"]


# --- sample content (representative, just so the panels look real) ----------
SAMPLE_BOOK = ["e4   (46%)", "d4   (31%)", "Nf3  (12%)", "c4    (8%)", "g3    (3%)"]
SAMPLE_ENGINE = [
    "depth 24   score +0.32",
    "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6",
    "4. Ba4 Nf6 5. O-O Be7 6. Re1",
]
SAMPLE_STATS = [
    "Found 1240  (W POV)",
    "W 47%  D 27%  L 26%",
    "",
    "move     n  W/D/L",
    "Nf3     412  190/120/102",
    "Bb5     330  165/95/70",
    "Bc4     210  98/60/52",
    "d4      180  80/55/45",
    "Nc3     108  50/30/28",
]
# Ruy Lopez; we play the whole line then step back a few so the PGN panel has a
# real continuation to show and the board sits in a recognisable middlegame.
SAMPLE_LINE = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6",
               "b5a4", "g8f6", "e1g1", "f8e7", "f1e1", "b7b5",
               "a4b3", "d7d6", "c2c3", "e8g8"]
STEP_BACK = 4


def boot():
    """Initialise pygame + BoardScreen + the app context, off the main loop."""
    p.init()
    safe_font.install()
    screen = p.display.set_mode((BS.SCREEN_WIDTH, BS.SCREEN_HEIGHT))
    p.display.set_caption("capture_screenshots")
    BS.init()                       # loads piece images + the panel fonts
    # Analysis renders the side panels itself, so drawGameState must only CLEAR
    # their boxes (not try to draw the book, which needs a loaded Polyglot file).
    BS.show_book = BS.show_pgn = BS.show_cpu = False
    app.screen = screen
    app.W, app.H = BS.SCREEN_WIDTH, BS.SCREEN_HEIGHT
    app.clock = p.time.Clock()
    app.manager = pygame_gui.UIManager((app.W, app.H))
    return screen


def draw_toolbar(screen):
    """Draw the top button row (decorative, for the screenshot)."""
    actions = [ToolbarAction(lbl, lbl, lambda: None) for lbl in TOOLBAR_LABELS]
    Toolbar(actions)
    app.manager.update(0.05)
    app.manager.draw_ui(screen)


def sample_game():
    gs = GameState()
    for uci in SAMPLE_LINE:
        gs.makeChessMove(chess.Move.from_uci(uci))
    for _ in range(STEP_BACK):      # step back so there is a continuation ahead
        gs.undoMove()
    return gs


def capture_analysis(screen, path):
    """Analysis screen: board + opening book + PGN moves + Personal Stats + engine."""
    gs = sample_game()

    screen.fill(p.Color("black"))
    BS.drawGameState(screen, gs, [], [], ())

    book = BookPanel()
    book.visible = True
    book.render(screen, SAMPLE_BOOK)

    pgn = TextLinesPanel(
        lambda: p.Rect(BS.PGN_X, BS.PGN_Y, BS.PGN_WIDTH, BS.PGN_HEIGHT),
        title="PGN moves",
    )
    pgn.visible = True
    pgn.render(screen, gs.getContinuationLines())

    stats = TextLinesPanel(
        lambda: p.Rect(BS.DBSTATS_X, BS.DBSTATS_Y, BS.DBSTATS_WIDTH, BS.DBSTATS_HEIGHT),
        title="Personal Stats",
        font=p.font.SysFont('Consolas,Courier New,Lucida Console', 16),
    )
    stats.visible = True
    stats.render(screen, SAMPLE_STATS)

    engine = EnginePanel()
    engine.visible = True
    engine.render(screen, SAMPLE_ENGINE)

    draw_toolbar(screen)

    p.image.save(screen, path)
    print("wrote", path)


# --- helpers for the training screens (board + move log + cyan context label) -
def game_from_pgn(path, idx=0):
    with open(path, encoding="utf-8", errors="replace") as f:
        g = None
        for _ in range(idx + 1):
            g = chess.pgn.read_game(f)
            if g is None:
                break
    return g


def gs_at(game, advance=0):
    """A GameState set to `game`, advanced `advance` mainline moves (the rest of
    the line stays ahead, so the move log + any PGN panel look real)."""
    gs = GameState()
    gs.setPgn(game)
    for _ in range(advance):
        nxt = gs.node.next()
        if nxt is None:
            break
        gs.makeChessMove(nxt.move)
    return gs


def capture_board(screen, path, gs, label):
    """A training-style screen: board + move log (with the cyan label) + toolbar.
    The side panels stay off, exactly as the training modes show them."""
    BS.set_context_label(label)
    screen.fill(p.Color("black"))
    BS.drawGameState(screen, gs, [], [], ())
    draw_toolbar(screen)
    p.image.save(screen, path)
    BS.set_context_label(None)
    print("wrote", path)


def capture_solve(screen, path):
    from LearningBase import learningBases
    lb = learningBases.get("C42Russian")
    if not lb or not lb.positions:
        lb = next((b for b in learningBases.values() if b.positions), None)
    pos = next(iter(lb.positions.values()))
    game = chess.pgn.Game()               # the puzzle position itself (Skip lead-in)
    game.setup(chess.Board(pos.fen))
    gs = GameState()
    gs.setPgn(game)
    capture_board(screen, path, gs, f"Training: {lb.filename}")


def capture_openings(screen, path):
    gs = gs_at(game_from_pgn("openings/B12CaroKan.pgn"), advance=6)
    capture_board(screen, path, gs, "Opening: B12CaroKan (Black)")


def capture_endgame(screen, path):
    g = game_from_pgn("endgames/esempi.pgn")
    title = (g.headers.get("White") or g.headers.get("Event") or "study")
    capture_board(screen, path, gs_at(g, advance=0),
                  f"Endgame: esempi -- {title} (1/2, playing White)")


def main():
    preview = "--preview" in sys.argv
    screen = boot()
    prefix = "docs/img/_preview_" if preview else "docs/img/"
    capture_analysis(screen, f"{prefix}stats.png")
    capture_solve(screen, f"{prefix}solve.png")
    capture_openings(screen, f"{prefix}openings.png")
    capture_endgame(screen, f"{prefix}endgame.png")
    p.quit()


if __name__ == "__main__":
    main()
