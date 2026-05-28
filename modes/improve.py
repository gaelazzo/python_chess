"""Guided "Improve from your Chess.com games" wizard.

High-level feature that orchestrates the existing primitives (download games ->
build/refresh a learning base -> analyze for mistakes -> practice locally) so
the user doesn't have to run the Tools steps by hand with non-obvious params.

Both tactical and opening mistakes are found by the SAME player-aware
`analyzer.analyzePgn`; they differ only in the learning-base preset:
- tactics : useBook=False, large movesToAnalyze, high blunderValue (only real blunders)
- openings: useBook=True, small movesToAnalyze (opening phase), lower blunderValue;
            book moves are never flagged, deviations are judged by the engine.

Practice is the local `solvePositionsFromBase` (no BrainMaster server).
"""
from __future__ import annotations

import os
import sys
from collections import namedtuple

import pygame as p
import pygame_menu

from app_context import app
import BoardScreen as BS
import analyzer
import chess_com_download
import pgngamelist
from LearningBase import LearningBase, learningBases
from state import positionParameters, small_font_theme, REVERSE_COLOR_MAP
from modes.replay import solvePositionsFromBase


# (ponderTime, blunderValue, movesToAnalyze, useBook)
Preset = namedtuple("Preset", "ponderTime blunderValue movesToAnalyze useBook")

PRESETS = {
    "tactics": {
        "quick":    Preset(0.2, 200, 40, False),
        "balanced": Preset(0.3, 200, 120, False),
        "thorough": Preset(0.6, 150, 200, False),
    },
    "openings": {
        "quick":    Preset(0.3, 100, 12, True),
        "balanced": Preset(0.5, 80, 16, True),
        "thorough": Preset(0.8, 60, 20, True),
    },
}

_FOCUS_LABEL = {"tactics": "Tattica", "openings": "Aperture"}


def buildImproveMenu(width, height) -> pygame_menu.Menu:
    """Build the wizard menu (added as a top-level button in chessMain)."""
    menu = pygame_menu.Menu(
        height=height, width=width,
        theme=pygame_menu.themes.THEME_BLUE,
        title="Migliora dalle tue partite",
    )
    user_w = menu.add.text_input("Utente Chess.com: ", default=positionParameters.get("player") or "")
    # NB: leggiamo i valori dei selector al click su Start (get_value), NON via
    # onchange: in pygame_menu onchange scatta solo quando il valore cambia, e
    # con i default lasciati intatti non verrebbe mai impostato nulla.
    color_w = menu.add.selector("Giochi: ", [("Bianco", "w"), ("Nero", "b"), ("Entrambi", None)],
                                default=REVERSE_COLOR_MAP.get(positionParameters.get("color"), 0))
    limit_w = menu.add.selector("Partite: ", [("Ultime 500", 500), ("Ultime 1000", 1000), ("Ultime 2000", 2000), ("Tutte", None)],
                                default=1)
    focus_w = menu.add.selector("Focus: ", [("Tattica", "tactics"), ("Aperture", "openings"), ("Entrambi", "both")],
                                default=2)
    effort_w = menu.add.selector("Accuratezza: ", [("Quick", "quick"), ("Balanced", "balanced"), ("Thorough", "thorough")],
                                 default=1)

    menu.add.button("Start", lambda: runImproveWizard(
        user_w.get_value(),
        color_w.get_value()[0][1],
        focus_w.get_value()[0][1],
        effort_w.get_value()[0][1],
        limit_w.get_value()[0][1],
    ))
    return menu


def _wait_screen(text):
    """Draw a blocking 'please wait' frame (no delay) and pump events."""
    app.main_background()
    BS.drawEndGameText(app.screen, None, text, size=24)  # chiama gia' update()
    p.event.pump()


def _message(text, secs=2):
    app.main_background()
    BS.drawEndGameText(app.screen, None, text, size=24)
    BS.update()
    app.delay(secs)


def _progress_cb(label, total):
    def cb(n):
        app.main_background()
        msg = f"{label}: analizzo {n}/{total}" if total else f"{label}: analizzo partita {n}"
        BS.drawEndGameText(app.screen, None, msg, size=24)
        p.event.pump()   # tiene viva la finestra (niente "non risponde")
    return cb


def _count_games(path):
    """Cheap game count for the N/M denominator (one [Event] tag per game)."""
    n = 0
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("[Event "):
                    n += 1
    except OSError:
        return 0
    return n


def _ensure_base(name, prm: Preset) -> LearningBase:
    """Reuse the base if already loaded, otherwise create+register it; refresh
    its analysis params from the chosen preset either way."""
    lb = learningBases.get(name)
    if lb is None:
        lb = LearningBase(prm.movesToAnalyze, prm.blunderValue, prm.ponderTime, prm.useBook)
        lb.setFileName(name)
        learningBases[name] = lb
        lb.save()
    else:
        lb.movesToAnalyze = prm.movesToAnalyze
        lb.blunderValue = prm.blunderValue
        lb.ponderTime = prm.ponderTime
        lb.useBook = prm.useBook
    return lb


def runImproveWizard(user, color, focus, effort, limit=None):
    """Orchestrate the whole pipeline, then offer to practice locally."""
    user = (user or "").strip()
    if not user:
        _message("Inserisci l'utente Chess.com")
        return

    app.main_menu.disable()
    app.main_menu.full_reset()
    try:
        pgn = f"{user}_games.pgn"                       # nome canonico, usato ovunque
        path = os.path.join(pgngamelist.PGN_FOLDER, pgn)

        n_txt = "tutte" if limit is None else f"ultime {limit}"
        _wait_screen(f"Scarico le partite di {user} ({n_txt})...")
        try:
            chess_com_download.load(user, pgn, color, max_games=limit)   # scrive PGN_FOLDER/{user}_games.pgn verbatim
        except Exception as e:                          # rete/utente/parse
            _message(f"Errore nel download: {e}")
            return

        if not os.path.exists(path) or os.path.getsize(path) == 0:
            _message(f"Nessuna partita per '{user}' (utente inesistente o nessuna partita).")
            return

        total = _count_games(path)
        focuses = ["tactics", "openings"] if focus == "both" else [focus]

        results = []   # (focus, baseName, nPositions)
        for f in focuses:
            prm = PRESETS[f][effort]
            baseName = f"{user}_{f}"
            lb = _ensure_base(baseName, prm)
            analyzer.analyzePgn(pgn, user, lb, progress=_progress_cb(_FOCUS_LABEL[f], total))
            lb.save()
            results.append((f, baseName, len(lb.positions)))

        _show_results_and_practice(results, color)
    finally:
        p.event.clear()
        if app.main_menu is not None and not app.main_menu.is_enabled():
            app.main_menu.enable()


def _show_results_and_practice(results, color):
    """Summary + practice buttons; launching practice ends the wizard."""
    nonempty = [(f, b, c) for (f, b, c) in results if c > 0]
    if not nonempty:
        _message("Nessun errore trovato da allenare.")
        return

    menu = pygame_menu.Menu("Analisi completata", app.W, app.H, theme=small_font_theme)
    summary = " | ".join(f"{_FOCUS_LABEL[f]}: {c}" for (f, b, c) in results)
    menu.add.label(summary)

    chosen = {"base": None}

    def pick(base):
        chosen["base"] = base
        menu.disable()          # esce dal loop locale

    for (f, b, c) in nonempty:
        menu.add.button(f"Allena {_FOCUS_LABEL[f].lower()} ({c})", pick, b)
    menu.add.button("Torna al menu", menu.disable)

    _run_menu_loop(menu)

    if chosen["base"]:
        positionParameters["base"] = chosen["base"]
        positionParameters["eco"] = None
        positionParameters["color"] = color
        solvePositionsFromBase(learningBases[chosen["base"]])   # riabilita il menu alla fine


def _run_menu_loop(menu):
    """Modal loop for a transient pygame_menu (closes when menu.disable() runs)."""
    surface = app.screen
    clock = p.time.Clock()
    menu.enable()
    while menu.is_enabled():
        events = p.event.get()
        for ev in events:
            if ev.type == p.QUIT:
                p.quit()
                sys.exit()
        menu.update(events)
        if not menu.is_enabled():
            break
        surface.fill((0, 0, 0))
        menu.draw(surface)
        p.display.flip()
        clock.tick(app.FPS)
