"""Add the current position to a learning base as a tactics problem.

User workflow: in analysis mode (Play between humans) set up a
position (optionally via U/Setup), play the correct move on the
board, then press **K** (or click the toolbar button "AddTac"): this
menu opens asking for the target base, after which it inserts a
`LearnPosition` into the base with:

- zobrist/fen = state of the board BEFORE the move just played,
- `ok` = the move just played (UCI),
- `severity` = 100 (reasonable default for drill priority).
"""
from __future__ import annotations

from typing import Optional

import chess
import chess.pgn
import pygame as p
import pygame_menu

from app_context import app
import BoardScreen as BS
from GameState import GameState
from LearningBase import LearningBase, learningBases
from menu_helpers import make_base_selector
from modes.common import show_message


def can_add(gs: GameState) -> bool:
    """True if there is at least one played move whose parent position can be saved."""
    return bool(gs.moveLog) and gs.node is not None and gs.node.parent is not None


def addPositionToBaseMenu(gs: GameState) -> bool:
    """Open a learning base selection menu and insert the current
    position + the last move played into it as a tactics problem.

    Returns True if the user saved, False otherwise.
    """
    if not can_add(gs):
        show_message(gs, "Play the correct move first")
        app.delay(2)
        return False

    board_before = gs.node.parent.board()
    correct_uci = gs.moveLog[-1].move.uci()
    # Source game for the metadata (date/eco/players). In analysis mode
    # gs.pgn typically exists as a root Game without meaningful headers:
    # we pass what we have and leave the optional fields as None.
    game = gs.pgn or chess.pgn.Game()

    selected_existing: Optional[str] = None
    new_name = ""
    saved = False
    menu_running = True

    def do_pick_base(name: str):
        nonlocal selected_existing
        selected_existing = name

    def do_new_name(value: str):
        nonlocal new_name
        new_name = value or ""

    def do_save():
        nonlocal saved, menu_running
        target = (new_name.strip() or selected_existing or "").strip()
        if not target:
            return
        # Get or create base
        if target in learningBases:
            lb = learningBases[target]
        else:
            lb = LearningBase(movesToAnalyze=16, blunderValue=80,
                              ponderTime=0.5, useBook=False)
            lb.setFileName(target)
            learningBases[target] = lb
        try:
            # `updatePosition(moveMade, goodMove, game, board, severity)`:
            # with `moveMade == goodMove` the position enters as an already
            # registered "correct answer"; but we want the user to see it as
            # 'to be solved', so the stats are initialized to zero
            # (`create_first_position` does this when zobrist is not in `positions`).
            lb.updatePosition(correct_uci, correct_uci, game, board_before, severity=100)
            lb.save()
            saved = True
        except Exception as e:
            print(f"add_to_base: save failed: {e}")
            return
        menu_running = False

    def do_cancel():
        nonlocal menu_running
        menu_running = False

    menu = pygame_menu.Menu(
        'Add to learning base', app.W, app.H,
        theme=pygame_menu.themes.THEME_BLUE,
    )
    # Show (truncated) FEN and move we are about to save
    fen_short = board_before.fen()
    if len(fen_short) > 60:
        fen_short = fen_short[:57] + "..."
    try:
        san = board_before.san(chess.Move.from_uci(correct_uci))
    except Exception:
        san = correct_uci
    menu.add.label(f"Position: {fen_short}", font_size=14)
    menu.add.label(f"Correct move: {san} ({correct_uci})", font_size=16)
    menu.add.vertical_margin(10)

    # File selector for the existing base (consistent style with Solve positions).
    labels = []
    choose_base = make_base_selector(None, labels, callback=do_pick_base)
    menu.add.button('Choose base file', choose_base, font_size=18)
    label = menu.add.button("(no choice)", choose_base, font_size=18,
                            background_color=None,
                            selection_effect=pygame_menu.widgets.NoneSelection())
    labels.append(label)

    menu.add.text_input('Or new base: ', default='', onchange=do_new_name, font_size=18)
    menu.add.vertical_margin(10)
    menu.add.button('Save', do_save, font_size=20)
    menu.add.button('Cancel', do_cancel, font_size=20)

    while menu_running:
        events = p.event.get()
        for e in events:
            if e.type == p.QUIT:
                return False
            if e.type == p.KEYDOWN and e.key == p.K_ESCAPE:
                menu_running = False
        app.screen.fill(p.Color('black'))
        menu.update(events)
        menu.draw(app.screen)
        p.display.flip()

    return saved
