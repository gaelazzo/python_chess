"""Study advisor: reads a user's PGN (e.g. a download from chess.com), aggregates
the games by ECO code and proposes a ranking of "study urgency".

Pure analysis of the PGN headers -- no engine, no learning bases
traversed. Fast even on PGNs with thousands of games.

Urgency score (v1):
    score = losses + 0.5 * draws
equivalent to "points lost in the tournament" from the user's point of view.
The openings at the top are the ones where you have accumulated the most point debt --
they combine "you play them a lot" and "you lose them often".
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import os
import sys
from typing import Callable, List, Optional

import chess.pgn
import pygame as p
import pygame_menu

from app_context import app
import BoardScreen as BS
from state import positionParameters, small_font_theme
import pgngamelist
from menu_helpers import make_updater, addChoosePGNFile
import analyzer
from LearningBase import LearningBase, learningBases
from modes.replay import solvePositionsFromBase


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

@dataclass
class ECOStat:
    eco: str
    num_games: int
    wins: int
    draws: int
    losses: int

    @property
    def win_rate(self) -> float:
        if self.num_games == 0:
            return 0.0
        return (self.wins + 0.5 * self.draws) / self.num_games

    @property
    def score(self) -> float:
        # Deficit = points lost BELOW the 50% threshold (= a break-even "expected score").
        # This way openings where you win >=50% have deficit 0 and disappear from the
        # ranking regardless of volume; the ones at the top are those where you
        # really under-perform. Favors actual under-performance instead
        # of pure volume.
        expected = 0.5 * self.num_games
        actual = self.wins + 0.5 * self.draws
        return max(0.0, expected - actual)


def _user_outcome(result: str, user_color: str) -> Optional[str]:
    """Returns 'wins' / 'draws' / 'losses' from the user's point of view,
    or None if the game is not finished."""
    if result == "1-0":
        return "wins" if user_color == "w" else "losses"
    if result == "0-1":
        return "wins" if user_color == "b" else "losses"
    if result.startswith("1/2"):
        return "draws"
    return None


def analyze_pgn(pgn_path: str, username: str, color: Optional[str]) -> List[ECOStat]:
    """Scans only the PGN headers and aggregates by ECO.

    Args:
        pgn_path: absolute path of the PGN.
        username: who we are (case-insensitive match on [White]/[Black]).
        color: 'w' / 'b' / None (both). Filters to games where the user
            played with the specified color.
    """
    username_lower = (username or "").lower()
    by_eco = defaultdict(lambda: {"games": 0, "wins": 0, "draws": 0, "losses": 0})

    with open(pgn_path, encoding="utf-8", errors="replace") as fh:
        while True:
            try:
                headers = chess.pgn.read_headers(fh)
            except Exception:
                break
            if headers is None:
                break

            white = (headers.get("White") or "").lower()
            black = (headers.get("Black") or "").lower()
            if white == username_lower:
                user_color = "w"
            elif black == username_lower:
                user_color = "b"
            else:
                continue   # the user was not in this game

            if color is not None and user_color != color:
                continue

            eco = (headers.get("ECO") or "?").strip() or "?"
            result = headers.get("Result", "*")
            outcome = _user_outcome(result, user_color)
            if outcome is None:
                continue   # game not finished

            d = by_eco[eco]
            d["games"] += 1
            d[outcome] += 1

    stats = [ECOStat(eco=eco, num_games=d["games"], wins=d["wins"],
                     draws=d["draws"], losses=d["losses"])
             for eco, d in by_eco.items()]
    # Order: deficit desc (under-performance), then volume desc (for equal
    # deficit, favor the openings played more often), then alphabetical.
    stats.sort(key=lambda s: (-s.score, -s.num_games, s.eco))
    return stats


# ---------------------------------------------------------------------------
# UI: input menu
# ---------------------------------------------------------------------------

def buildAdvisorMenu(width, height) -> pygame_menu.Menu:
    """Builds the 'What should I study now?' menu (called by chessMain.mainMenu)."""
    menu = pygame_menu.Menu(
        height=height, width=width,
        theme=pygame_menu.themes.THEME_BLUE,
        title="Suggestion for study",
    )
    user_w = menu.add.text_input("User: ", default=positionParameters.get("player") or "")
    color_w = menu.add.selector(
        "Color: ",
        [("Both", None), ("White", "w"), ("Black", "b")],
        default=0,
    )
    addChoosePGNFile(menu)
    menu.add.button(
        "Analyze",
        lambda: runAdvisor(user_w.get_value(), color_w.get_value()[0][1]),
    )
    return menu


# ---------------------------------------------------------------------------
# Orchestration and results screen
# ---------------------------------------------------------------------------

def _wait_screen(text: str) -> None:
    app.main_background()
    BS.drawEndGameText(app.screen, None, text, size=24)
    p.event.pump()


def _message(text: str, secs: float = 2) -> None:
    app.main_background()
    BS.drawEndGameText(app.screen, None, text, size=24)
    BS.update()
    app.delay(secs)


def runAdvisor(user: str, color: Optional[str]) -> None:
    user = (user or "").strip()
    pgn_name = positionParameters.get("filename") or ""
    if not user:
        _message("Enter the user")
        return
    if not pgn_name:
        _message("Choose a PGN file")
        return

    # addChoosePGNFile saves the filename WITHOUT extension; we add .pgn.
    pgn_path = os.path.join(pgngamelist.PGN_FOLDER, pgn_name + ".pgn")
    if not os.path.exists(pgn_path):
        # also try the name as-is (compat with those who save without extension)
        alt = os.path.join(pgngamelist.PGN_FOLDER, pgn_name)
        if os.path.exists(alt):
            pgn_path = alt
        else:
            _message(f"PGN not found: {pgn_name}")
            return

    app.main_menu.disable()
    app.main_menu.full_reset()
    try:
        _wait_screen(f"Analyzing {os.path.basename(pgn_path)} for {user}...")
        stats = analyze_pgn(pgn_path, user, color)
        if not stats:
            _message(f"No games by '{user}' found in {os.path.basename(pgn_path)}")
            return
        color_label = {"w": "White", "b": "Black", None: "Both"}[color]
        header = f"Study priorities for {user} ({color_label}) — {sum(s.num_games for s in stats)} games, {len(stats)} ECO"
        _show_results(stats, header, user, color, pgn_path)
    finally:
        p.event.clear()
        if app.main_menu is not None and not app.main_menu.is_enabled():
            app.main_menu.enable()


def _show_results(stats: List[ECOStat], header: str, user: str,
                  color: Optional[str], pgn_path: str) -> None:
    """Custom screen with a ranked table of the ECOs.
    Click on a row -> starts a focused analysis on that ECO and then practice.
    Esc / Q closes and returns to the menu.
    """
    BG = (20, 20, 28)
    FG = (235, 235, 235)
    HDR = (180, 200, 255)
    LOSE_COLOR = (240, 150, 130)
    WIN_COLOR = (170, 240, 170)
    TOP_HIGHLIGHT = (255, 220, 90)     # banner on #1
    ROW_HOVER_BG = (45, 45, 70)

    title_font = p.font.SysFont("Arial", 22, bold=True)
    hint_font = p.font.SysFont("Arial", 14, italic=True)
    hdr_font = p.font.SysFont("Arial", 16, bold=True)
    row_font = p.font.SysFont("Consolas,DejaVu Sans Mono,Courier", 16)
    info_font = p.font.SysFont("Arial", 14)

    line_h = row_font.get_linesize() + 6
    margin_x = 24
    top_title = 16
    top_hint = 44
    top_header = 76
    top_rows = 104

    visible_rows = max(1, (app.H - top_rows - 36) // line_h)
    scroll = 0
    max_scroll = max(0, len(stats) - visible_rows)

    def row_at(pos):
        x, y = pos
        if y < top_rows or y >= top_rows + visible_rows * line_h:
            return None
        return scroll + (y - top_rows) // line_h

    running = True
    clicked_eco: Optional[str] = None
    mouse_pos = (0, 0)
    while running:
        for e in p.event.get():
            if e.type == p.QUIT:
                p.quit()
                sys.exit()
            elif e.type == p.MOUSEMOTION:
                mouse_pos = e.pos
            elif e.type == p.KEYDOWN:
                if e.key in (p.K_ESCAPE, p.K_q):
                    running = False
                elif e.key in (p.K_DOWN, p.K_PAGEDOWN):
                    scroll = min(max_scroll, scroll + (visible_rows if e.key == p.K_PAGEDOWN else 1))
                elif e.key in (p.K_UP, p.K_PAGEUP):
                    scroll = max(0, scroll - (visible_rows if e.key == p.K_PAGEUP else 1))
                elif e.key == p.K_HOME:
                    scroll = 0
                elif e.key == p.K_END:
                    scroll = max_scroll
            elif e.type == p.MOUSEWHEEL:
                scroll = max(0, min(max_scroll, scroll - e.y * 3))
            elif e.type == p.MOUSEBUTTONDOWN and e.button == 1:
                idx = row_at(e.pos)
                if idx is not None and 0 <= idx < len(stats):
                    clicked_eco = stats[idx].eco
                    running = False

        app.screen.fill(BG)
        # title
        app.screen.blit(title_font.render(header, True, FG), (margin_x, top_title))
        # hint
        hint = ("Row 1 = highest priority. Score = 'Deficit' = points lost BELOW 50%: "
                "if you win >=50% in an opening the deficit is 0 (whatever the volume). "
                "Click a row -> I analyze that opening's games and take you to drill them.")
        app.screen.blit(hint_font.render(hint, True, (200, 200, 200)), (margin_x, top_hint))
        # column header
        cols = [
            (margin_x,         "ECO"),
            (margin_x + 90,    "Games"),
            (margin_x + 180,   "W"),
            (margin_x + 230,   "D"),
            (margin_x + 280,   "L"),
            (margin_x + 340,   "Win%"),
            (margin_x + 420,   "Deficit"),
        ]
        for x, label in cols:
            app.screen.blit(hdr_font.render(label, True, HDR), (x, top_header))

        # hover row
        hover_idx = row_at(mouse_pos)
        if hover_idx is not None and 0 <= hover_idx - scroll < visible_rows and hover_idx < len(stats):
            y = top_rows + (hover_idx - scroll) * line_h
            p.draw.rect(app.screen, ROW_HOVER_BG, p.Rect(margin_x - 4, y - 2, app.W - 2*margin_x + 8, line_h - 2))

        # rows
        for i in range(visible_rows):
            idx = scroll + i
            if idx >= len(stats):
                break
            s = stats[idx]
            y = top_rows + i * line_h
            # "I recommend this one" banner on the first row
            if idx == 0:
                p.draw.rect(app.screen, TOP_HIGHLIGHT, p.Rect(margin_x - 10, y - 2, 4, line_h - 2))
            row_color = LOSE_COLOR if s.win_rate < 0.45 else (WIN_COLOR if s.win_rate > 0.55 else FG)
            cells = [
                (margin_x,         f"{idx+1:>3}. {s.eco}"),
                (margin_x + 90,    f"{s.num_games}"),
                (margin_x + 180,   f"{s.wins}"),
                (margin_x + 230,   f"{s.draws}"),
                (margin_x + 280,   f"{s.losses}"),
                (margin_x + 340,   f"{s.win_rate*100:5.1f}%"),
                (margin_x + 420,   f"{s.score:5.1f}"),
            ]
            for x, text in cells:
                app.screen.blit(row_font.render(text, True, row_color), (x, y))

        # info bar at the bottom
        bar_y = app.H - 28
        info = (f"  {scroll+1}-{min(scroll+visible_rows, len(stats))} of {len(stats)}   "
                f"|   ↑/↓ PgUp/PgDn wheel: scroll   |   click a row: study that opening   |   Esc/Q: close")
        p.draw.rect(app.screen, (38, 38, 52), p.Rect(0, bar_y - 4, app.W, 32))
        app.screen.blit(info_font.render(info, True, (210, 210, 170)), (margin_x, bar_y))

        p.display.flip()
        app.clock.tick(30)

    if clicked_eco is not None:
        _run_focused_analysis(clicked_eco, user, color, pgn_path)


# ---------------------------------------------------------------------------
# Focused analysis on a single opening, then practice
# ---------------------------------------------------------------------------

def _count_games_with_eco(pgn_path: str, username: str, eco: str,
                          color: Optional[str]) -> int:
    """Counts the games that satisfy the filter (for the N/M denominator)."""
    n = 0
    target = eco.upper()
    username_lower = (username or "").lower()
    with open(pgn_path, encoding="utf-8", errors="replace") as fh:
        while True:
            try:
                h = chess.pgn.read_headers(fh)
            except Exception:
                break
            if h is None:
                break
            if (h.get("ECO") or "").strip().upper() != target:
                continue
            w = (h.get("White") or "").lower()
            b = (h.get("Black") or "").lower()
            if w == username_lower:
                user_color = "w"
            elif b == username_lower:
                user_color = "b"
            else:
                continue
            if color is not None and user_color != color:
                continue
            n += 1
    return n


def _run_focused_analysis(eco: str, user: str, color: Optional[str],
                          pgn_path: str) -> None:
    """Analyzes only the games with the given ECO, builds/updates a dedicated
    base and immediately proposes practice via solvePositionsFromBase."""
    # preset openings/Balanced (same as the wizard)
    base_name = f"{user}_{eco}"
    moves_to_analyze = 16
    blunder_value = 80
    ponder_time = 0.5
    use_book = True

    lb = learningBases.get(base_name)
    if lb is None:
        lb = LearningBase(moves_to_analyze, blunder_value, ponder_time, use_book)
        lb.setFileName(base_name)
        learningBases[base_name] = lb
        lb.save()
    else:
        lb.movesToAnalyze = moves_to_analyze
        lb.blunderValue = blunder_value
        lb.ponderTime = ponder_time
        lb.useBook = use_book

    total = _count_games_with_eco(pgn_path, user, eco, color)
    if total == 0:
        _message(f"No {eco} games for '{user}' in the PGN.")
        return

    def progress_cb(n):
        app.main_background()
        BS.drawEndGameText(app.screen, None, f"{eco}: analyzing {n}/{total}", size=24)
        p.event.pump()

    # analyzePgn expects the name relative to PGN_FOLDER
    pgn_name = os.path.basename(pgn_path)
    analyzer.analyzePgn(pgn_name, user, lb, progress=progress_cb, eco=eco)
    lb.save()

    if not lb.positions:
        _message(f"No mistake positions found for {eco}.")
        return

    # Practice immediately on the focused base
    positionParameters["base"] = base_name
    positionParameters["eco"] = None        # ECO filter already applied at the base level
    positionParameters["color"] = color
    solvePositionsFromBase(lb)
