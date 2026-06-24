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

import chess.pgn
import pygame as p
import pygame_menu

from app_context import app
import BoardScreen as BS
import analyzer
import UCIEngines
import chess_com_download
import pgngamelist
from LearningBase import LearningBase, learningBases
from state import positionParameters, small_font_theme, REVERSE_COLOR_MAP
from menu_helpers import add_menu_intro
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

_FOCUS_LABEL = {"tactics": "Tactics", "openings": "Openings"}


def buildImproveMenu(width, height) -> pygame_menu.Menu:
    """Build the wizard menu (added as a top-level button in chessMain)."""
    menu = pygame_menu.Menu(
        height=height, width=width,
        theme=pygame_menu.themes.THEME_BLUE,
        title="Improve from your games",
    )
    add_menu_intro(menu,
        "Build a personalised training set from your own online games: "
        "download them, let the engine find your mistakes, and practise them "
        "locally.")
    user_w = menu.add.text_input("Chess.com user: ", default=positionParameters.get("player") or "")
    # NOTE: we read selector values on Start click (get_value), NOT via
    # onchange: in pygame_menu, onchange only fires when the value changes, and
    # with defaults left untouched nothing would ever be set.
    color_w = menu.add.selector("You play: ", [("White", "w"), ("Black", "b"), ("Both", None)],
                                default=REVERSE_COLOR_MAP.get(positionParameters.get("color"), 0))
    limit_w = menu.add.selector("Games: ", [("Last 500", 500), ("Last 1000", 1000), ("Last 2000", 2000), ("All", None)],
                                default=1)
    focus_w = menu.add.selector("Focus: ", [("Tactics", "tactics"), ("Openings", "openings"), ("Both", "both")],
                                default=2)
    effort_w = menu.add.selector("Accuracy: ", [("Quick", "quick"), ("Balanced", "balanced"), ("Thorough", "thorough")],
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
    BS.drawEndGameText(app.screen, None, text, size=24)  # already calls update()
    p.event.pump()


def _message(text, secs=2):
    app.main_background()
    BS.drawEndGameText(app.screen, None, text, size=24)
    BS.update()
    app.delay(secs)


def _progress_cb(label, total):
    def cb(n):
        app.main_background()
        msg = f"{label}: analyzing {n}/{total}" if total else f"{label}: analyzing game {n}"
        BS.drawEndGameText(app.screen, None, msg + "   (ESC to stop)", size=24)
        # stop_requested() also drains events, keeping the window responsive.
        return BS.stop_requested()
    return cb


def _count_new_games(path, player, lb: LearningBase):
    """Games for `player` that analyzePgn(use_analyzed_range=True) will actually
    process: matching player AND whose date is not already inside the base's
    per-nick analyzed window. This is the right N/M denominator after an
    incremental download -- the previously-analyzed games are skipped, not redone."""
    n = 0
    try:
        with open(path, encoding="utf-8") as fh:
            while True:
                h = chess.pgn.read_headers(fh)
                if h is None:
                    break
                if not (analyzer._same_player(h.get("White"), player)
                        or analyzer._same_player(h.get("Black"), player)):
                    continue
                gdate = analyzer._game_date(h)
                if gdate is not None and lb.isInAnalyzedRange(player, gdate):
                    continue
                n += 1
    except OSError:
        return 0
    return n


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
        _message("Enter the Chess.com user")
        return

    app.main_menu.disable()
    app.main_menu.full_reset()
    try:
        # Analysis needs an engine: show a message and exit instead of crashing in
        # analyzer (engine.analyse on a None engine) when none is configured.
        if not UCIEngines.is_engine_ready():
            _message("Configure an engine first: Tools > Setup > Choose engine", secs=3)
            return
        pgn = f"{user}_games.pgn"             # canonical name, used everywhere
        path = os.path.join(pgngamelist.PGN_FOLDER, pgn)

        n_txt = "all" if limit is None else f"last {limit}"
        _wait_screen(f"Downloading {user}'s games ({n_txt})...")
        try:
            chess_com_download.load(user, pgn, color, max_games=limit)   # writes PGN_FOLDER/{user}_games.pgn verbatim
        except Exception as e:                          # network/user/parse
            _message(f"Download error: {e}")
            return

        if not os.path.exists(path) or os.path.getsize(path) == 0:
            _message(f"No games for '{user}' (user does not exist or has no games).")
            return

        focuses = ["tactics", "openings"] if focus == "both" else [focus]

        results = []   # (focus, baseName, nPositions)
        for f in focuses:
            prm = PRESETS[f][effort]
            baseName = f"{user}_{f}"
            lb = _ensure_base(baseName, prm)
            # Per-base count: each focus has its own analyzed window, so a base
            # already built skips the games it covers and only the new ones count.
            to_do = _count_new_games(path, user, lb)
            stopped = analyzer.analyzePgn(pgn, user, lb, progress=_progress_cb(_FOCUS_LABEL[f], to_do),
                                          use_analyzed_range=True)
            lb.save()
            results.append((f, baseName, len(lb.positions)))
            if stopped:        # user interrupted: don't roll on into the next focus
                break

        _show_results_and_practice(results, color)
    finally:
        p.event.clear()
        if app.main_menu is not None and not app.main_menu.is_enabled():
            app.main_menu.enable()


def _show_results_and_practice(results, color):
    """Summary + practice buttons; launching practice ends the wizard."""
    nonempty = [(f, b, c) for (f, b, c) in results if c > 0]
    if not nonempty:
        _message("No mistakes found to train on.")
        return

    menu = pygame_menu.Menu("Analysis Complete", app.W, app.H, theme=small_font_theme)
    summary = " | ".join(f"{_FOCUS_LABEL[f]}: {c}" for (f, b, c) in results)
    menu.add.label(summary)

    chosen = {"base": None}

    def pick(base):
        chosen["base"] = base
        menu.disable()          # exits the local loop

    for (f, b, c) in nonempty:
        menu.add.button(f"Train {_FOCUS_LABEL[f].lower()} ({c})", pick, b)
    menu.add.button("Back to menu", menu.disable)

    _run_menu_loop(menu)

    if chosen["base"]:
        positionParameters["base"] = chosen["base"]
        positionParameters["eco"] = None
        positionParameters["color"] = color
        solvePositionsFromBase(learningBases[chosen["base"]])  # re-enable the menu at the end


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
