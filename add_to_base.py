"""Aggiungi a una learning base la posizione corrente come problema di tattica.

Workflow utente: nella modalita' analisi (Play between humans) imposta una
posizione (eventualmente via U/Setup), gioca la mossa corretta sulla
scacchiera, poi preme **K** (o clicca il bottone toolbar "AddTac"): si apre
questo menu che chiede la base di destinazione, dopodiche' inserisce un
`LearnPosition` nella base con:

- zobrist/fen = stato della board PRIMA della mossa appena giocata,
- `ok` = la mossa appena giocata (UCI),
- `severity` = 100 (default ragionevole per priorita' di drill).
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
    """True se c'e' almeno una mossa giocata di cui salvare la posizione-padre."""
    return bool(gs.moveLog) and gs.node is not None and gs.node.parent is not None


def addPositionToBaseMenu(gs: GameState) -> bool:
    """Apre un menu di scelta della learning base e vi inserisce la posizione
    corrente + l'ultima mossa giocata come problema di tattica.

    Ritorna True se l'utente ha salvato, False altrimenti.
    """
    if not can_add(gs):
        show_message(gs, "Gioca prima la mossa corretta")
        app.delay(2)
        return False

    board_before = gs.node.parent.board()
    correct_uci = gs.moveLog[-1].move.uci()
    # Game di provenienza per i metadati (date/eco/players). In analisi
    # tipicamente gs.pgn esiste come Game radice senza headers significativi:
    # passiamo quello che c'e' e lasciamo i campi opzionali a None.
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
            # con `moveMade == goodMove` la posizione entra come "risposta
            # corretta" gia' registrata; ma vogliamo che l'utente la veda come
            # 'da risolvere', quindi le stat sono inizializzate a zero
            # (`create_first_position` lo fa quando zobrist non e' in `positions`).
            lb.updatePosition(correct_uci, correct_uci, game, board_before, severity=100)
            lb.save()
            saved = True
        except Exception as e:
            print(f"add_to_base: save fallito: {e}")
            return
        menu_running = False

    def do_cancel():
        nonlocal menu_running
        menu_running = False

    menu = pygame_menu.Menu(
        'Aggiungi a learning base', app.W, app.H,
        theme=pygame_menu.themes.THEME_BLUE,
    )
    # Mostra (truncato) FEN e mossa che stiamo per salvare
    fen_short = board_before.fen()
    if len(fen_short) > 60:
        fen_short = fen_short[:57] + "..."
    try:
        san = board_before.san(chess.Move.from_uci(correct_uci))
    except Exception:
        san = correct_uci
    menu.add.label(f"Posizione: {fen_short}", font_size=14)
    menu.add.label(f"Mossa corretta: {san} ({correct_uci})", font_size=16)
    menu.add.vertical_margin(10)

    # File selector per la base esistente (stile uniforme con Solve positions).
    labels = []
    choose_base = make_base_selector(None, labels, callback=do_pick_base)
    menu.add.button('Choose base file', choose_base, font_size=18)
    label = menu.add.button("(nessuna scelta)", choose_base, font_size=18,
                            background_color=None,
                            selection_effect=pygame_menu.widgets.NoneSelection())
    labels.append(label)

    menu.add.text_input('Oppure nuova base: ', default='', onchange=do_new_name, font_size=18)
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
