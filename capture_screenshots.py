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
import game_loop_common as glc
from app_context import app
from GameState import GameState
from toolbar import IconToolbar, ToolbarAction

# Representative popup texts for the masters-plans (G) and Lichess-database (D)
# screens -- hand-written so a screenshot needs no network.
PLANS_TEXT = (
    "Masters: 5043 games, Black to move, White 56%  (50 lines)\n"
    "Black plans typically:\n"
    "  [1] Bg7 + O-O + c5 + Na6   (24%, Black 44%)\n"
    "  [2] Bg7 + O-O + Nc6        (24%, Black 43%)\n"
    "  [3] Bg7 + O-O + dxe5       (21%, Black 41%)\n"
    "\n"
    "On [1], Black plays: Bg7 + O-O, then Bg4 (W31/D46/L23) or Nc7 (W30/D44/L26) or Rb8\n"
    "   Black does best with Bg4 (Black 47%)\n"
    "On [2], Black plays: Bg7 + O-O, then Nc6 + Bg4 or c6 + Nbd7 or c6 + Qc7\n"
    "On [3], Black plays: Bg7 + O-O + dxe5, then Nc6 + e5 or Qe7\n"
    "\n"
    "[1-3] show arrows on the board   -   [0] clear")
DB_TEXT = (
    "Lichess database: 3,792,835 games   White 53% / Draw 4% / Black 43%\n"
    "\n"
    "  Qd2    38.4%  (1,457,778 games)   W54/D3/B43\n"
    "  f3     35.1%  (1,331,679 games)   W55/D4/B42\n"
    "  Bd3     7.1%  (270,728 games)    W47/D3/B49\n"
    "  Nf3     5.2%  (195,999 games)    W50/D4/B46\n"
    "  h3      3.7%  (141,919 games)    W51/D4/B45\n"
    "  Be2     3.7%  (139,982 games)    W53/D4/B43")

# Icon toolbars, as (label, icon) specs that MIRROR the live modes. A screenshot
# only needs the buttons drawn, so the handlers are no-ops. `None` is a separator.
# Analysis (modes/play_game.py): main tools (left) + structure group (right) + the
# bottom navigation / move-actions bar.
ANALYSIS_MAIN = [("Open", "open"), ("Save", "save"), ("CopyFEN", "copyfen"),
                 ("CopyPGN", "copypgn"), ("Lock", "lock"), ("Openings", "openings"),
                 ("PGN", "pgn"), ("Statistics", "statistics"), ("Variations", "variations"),
                 ("Engine", "engine"), ("Flip", "flip"), ("Plans", "analyze"),
                 ("Ideas", "ideas"), ("DB", "db"), ("Help", "help")]
ANALYSIS_EDIT = [("EditPos", "editpos"), ("AddTactic", "addtac"), ("Truncate", "truncate"),
                 ("DeleteVar", "delvar"), None, ("Menu", "home")]
ANALYSIS_NAV = [("First", "first"), ("Prev", "prev"), ("Next", "next"), ("Last", "last"),
                ("Twins", "twins"), None,
                ("Annotate", "annotate"), ("Comment", "comment"), ("Promote", "promote")]
# Training modes (one top toolbar each), mirroring modes/{replay,openings,endgames}.py.
SOLVE_TB = [("Solution", "hint"), ("MoreMoves", "moremoves"), ("Next", "nextitem"),
            ("CopyFEN", "copyfen"), ("CopyPGN", "copypgn"), ("Openings", "openings"),
            ("PGN", "pgn"), ("Engine", "engine"), ("Menu", "home")]
OPENINGS_TB = [("Hint", "hint"), ("Next", "nextitem"), ("CopyFEN", "copyfen"),
               ("CopyPGN", "copypgn"), ("Openings", "openings"), ("PGN", "pgn"),
               ("Engine", "engine"), ("Flip", "flip"), ("Menu", "home")]
ENDGAME_TB = [("Hint", "hint"), ("Next", "nextitem"), ("CopyFEN", "copyfen"),
              ("PGN", "pgn"), ("Engine", "engine"), ("Flip", "flip"), ("Menu", "home")]


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


def _acts(specs):
    """Turn (label, icon) / None specs into ToolbarActions (no-op handlers)."""
    out = []
    for s in specs:
        if s is None:
            out.append(None)
        else:
            label, icon = s
            out.append(ToolbarAction(label, label, lambda: None, icon=icon))
    return out


def draw_top_toolbar(screen, specs):
    """Draw a single top icon toolbar (the training modes)."""
    tb = IconToolbar(_acts(specs), y=0, height=BS.TOOLBAR_HEIGHT)
    tb.update(0.0)
    tb.draw(screen)


def draw_analysis_toolbars(screen):
    """Draw the analysis screen's three icon toolbars (mirrors play_game)."""
    main = IconToolbar(_acts(ANALYSIS_MAIN), y=0, height=BS.TOOLBAR_HEIGHT)
    edit_x0 = main.content_right() + 16
    edit = IconToolbar(_acts(ANALYSIS_EDIT), y=0, height=BS.TOOLBAR_HEIGHT,
                       x0=edit_x0, width=BS.SCREEN_WIDTH - edit_x0, align="right")
    nav = IconToolbar(_acts(ANALYSIS_NAV), y=BS.NAV_Y, height=BS.NAV_HEIGHT,
                      x0=BS.NAV_X, width=BS.NAV_WIDTH, align="center", tooltip_above=True)
    for t in (main, edit, nav):
        t.update(0.0)
        t.draw(screen)


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

    # Use the shared singletons so the screenshot matches the live app exactly
    # (fonts, titles, rects); feed them representative sample data.
    BS.book.visible = True
    BS.book.render(screen, SAMPLE_BOOK)
    BS.pgn.visible = True
    BS.pgn.render(screen, BS.pgn_lines(gs))
    BS.dbstats.visible = True
    BS.dbstats.render(screen, SAMPLE_STATS)
    BS.engine.visible = True
    BS.engine.render(screen, SAMPLE_ENGINE)

    draw_analysis_toolbars(screen)

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


def capture_board(screen, path, gs, label, toolbar_specs):
    """A training-style screen: board + move log (with the cyan label) + the mode's
    icon toolbar. The side panels stay off, exactly as the training modes show them."""
    BS.set_context_label(label)
    screen.fill(p.Color("black"))
    BS.drawGameState(screen, gs, [], [], ())
    draw_top_toolbar(screen, toolbar_specs)
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
    capture_board(screen, path, gs, f"Training: {lb.filename}", SOLVE_TB)


def capture_openings(screen, path):
    gs = gs_at(game_from_pgn("openings/B12CaroKan.pgn"), advance=6)
    capture_board(screen, path, gs, "Opening: B12CaroKan (Black)", OPENINGS_TB)


def capture_endgame(screen, path):
    g = game_from_pgn("endgames/esempi.pgn")
    title = (g.headers.get("White") or g.headers.get("Event") or "study")
    capture_board(screen, path, gs_at(g, advance=0),
                  f"Endgame: esempi -- {title} (1/2, playing White)", ENDGAME_TB)


# --- modal screens: grab the FIRST rendered frame, then inject Esc to exit -----
def capture_modal(path, call):
    """Run a modal render function (its own event loop), save the first frame it
    presents, and post Esc so it returns -- without touching the modal's code.
    We hook display.flip/update (whatever it uses to present) and grab app.screen."""
    state = {"saved": False}
    orig_flip, orig_update = p.display.flip, p.display.update

    def hook(*a, **k):
        if not state["saved"]:
            state["saved"] = True
            p.image.save(app.screen, path)
            print("wrote", path)
            p.event.post(p.event.Event(p.KEYDOWN, key=p.K_ESCAPE, mod=0, unicode="\x1b"))

    p.display.flip = hook
    p.display.update = hook
    try:
        call()
    finally:
        p.display.flip, p.display.update = orig_flip, orig_update


def capture_notation(screen, path):
    import io
    import notation
    pgn_text = ('[Event "Demo"]\n\n'
                '1. e4 e5 2. Nf3 Nc6 3. Bb5! {The Ruy Lopez -- the main line.} '
                '(3. Bc4 {Italian Game} 3... Bc5 4. c3 Nf6) '
                '3... a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 *\n')
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    gs = GameState()
    gs.setPgn(game)
    capture_modal(path, lambda: notation.show_notation(gs))


def capture_setup(screen, path):
    import position_setup
    gs = gs_at(game_from_pgn("openings/B12CaroKan.pgn"), advance=6)
    capture_modal(path, lambda: position_setup.run(gs))


def capture_advisor(screen, path):
    from modes.study_advisor import _show_results, ECOStat
    stats = [
        ECOStat("C01", 637, 292, 31, 314), ECOStat("B01", 631, 291, 31, 309),
        ECOStat("C77", 75, 31, 1, 43),     ECOStat("B45", 15, 3, 0, 12),
        ECOStat("B27", 147, 67, 5, 75),    ECOStat("C89", 58, 23, 4, 31),
        ECOStat("C00", 257, 122, 6, 129),  ECOStat("C64", 218, 102, 7, 109),
        ECOStat("C70", 111, 51, 2, 58),    ECOStat("A46", 156, 68, 14, 74),
        ECOStat("C66", 59, 26, 1, 32),     ECOStat("E60", 30, 12, 0, 18),
        ECOStat("A10", 24, 7, 4, 13),      ECOStat("B29", 12, 3, 0, 9),
        ECOStat("C40", 176, 83, 5, 88),
    ]
    header = "Study priorities for hires (Both) -- 18627 games, 168 ECO"
    capture_modal(path, lambda: _show_results(stats, header, "hires", None, "pgn/all.pgn"))


def capture_plan_arrows(screen, path):
    """Analysis board with the masters-plan ARROWS (key G then 1-9): White's plan
    in white, Black's reply in black. Pirc 150-Attack after 4.Be3."""
    gs = GameState()
    for u in ["e2e4", "d7d6", "d2d4", "g8f6", "b1c3", "g7g6", "c1e3"]:
        gs.makeChessMove(chess.Move.from_uci(u))
    W, Bk, sq = BS.PLAN_ARROW_WHITE, BS.PLAN_ARROW_BLACK, chess.parse_square
    BS.set_plan_arrows([
        (sq("d1"), sq("d2"), W), (sq("f2"), sq("f3"), W), (sq("e1"), sq("c1"), W),   # Qd2 f3 O-O-O
        (sq("f8"), sq("g7"), Bk), (sq("e8"), sq("g8"), Bk),                          # ...Bg7 ...O-O
    ])
    screen.fill(p.Color("black"))
    BS.drawGameState(screen, gs, [], [], ())
    BS.book.visible = True;    BS.book.render(screen, SAMPLE_BOOK)
    BS.pgn.visible = True;     BS.pgn.render(screen, BS.pgn_lines(gs))
    BS.dbstats.visible = True; BS.dbstats.render(screen, SAMPLE_STATS)
    BS.engine.visible = True;  BS.engine.render(screen, SAMPLE_ENGINE)
    draw_analysis_toolbars(screen)
    p.image.save(screen, path)
    BS.set_plan_arrows([])
    print("wrote", path)


def capture_plans(screen, path):
    capture_modal(path, lambda: glc.show_text_popup("Masters plans", PLANS_TEXT))


def capture_database(screen, path):
    capture_modal(path, lambda: glc.show_text_popup("Lichess database", DB_TEXT))


def main():
    preview = "--preview" in sys.argv
    screen = boot()
    prefix = "docs/img/_preview_" if preview else "docs/img/"
    capture_analysis(screen, f"{prefix}stats.png")
    capture_plan_arrows(screen, f"{prefix}plan_arrows.png")
    capture_plans(screen, f"{prefix}plans.png")
    capture_database(screen, f"{prefix}database.png")
    capture_solve(screen, f"{prefix}solve.png")
    capture_openings(screen, f"{prefix}openings.png")
    capture_endgame(screen, f"{prefix}endgame.png")
    capture_notation(screen, f"{prefix}notation.png")
    capture_setup(screen, f"{prefix}setup.png")
    # advisor uses mock data; the committed advisor.png is the author's real-data
    # screenshot, so only (re)generate it in --preview (for verification). Flip
    # this if you'd rather have the fully-automated mock version.
    if preview:
        capture_advisor(screen, f"{prefix}advisor.png")
    p.quit()


if __name__ == "__main__":
    main()
