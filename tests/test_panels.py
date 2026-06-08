"""Behavioural tests for the side-panel view layer (panels/).

Headless (conftest forces SDL dummy): the panels render onto an off-screen
Surface, so we can assert the actual pixels -- the box is cleared to black, the
title/lines are drawn when visible, and a hidden panel leaves only the cleared
box. Geometry is checked against the BoardScreen primitives the panels read.
"""
import pygame as p
import pytest

import BoardScreen as BS
from panels import Panel, TextLinesPanel, BookPanel, EnginePanel


@pytest.fixture(scope="module", autouse=True)
def _font():
    """Provide the shared panel font without a full BS.init() (no image load)."""
    p.font.init()
    BS.BOOKFONT = p.font.SysFont("Arial", 14, False, False)
    yield


@pytest.fixture
def screen():
    return p.Surface((BS.SCREEN_WIDTH, BS.SCREEN_HEIGHT))


def _row_has_ink(screen, rect, y_off, x_span=80):
    """True if any non-black pixel sits on the title/first-line row."""
    return any(screen.get_at((x, rect.y + y_off))[:3] != (0, 0, 0)
               for x in range(rect.x + 5, rect.x + x_span))


def test_visible_panel_clears_box_and_draws_title(screen):
    screen.fill((123, 123, 123))
    bp = BookPanel()
    bp.visible = True
    bp.render(screen, ["e4", "Nf3", "Bb5"])
    r = bp.rect
    assert screen.get_at((r.x + 1, r.y + 1))[:3] == (0, 0, 0)   # cleared to black
    assert _row_has_ink(screen, r, 10)                          # "Book moves" title drawn


def test_hidden_panel_only_clears_box(screen):
    screen.fill((50, 50, 50))
    bp = BookPanel()
    bp.visible = False
    bp.render(screen, ["e4", "Nf3"])
    r = bp.rect
    assert screen.get_at((r.x + 1, r.y + 1))[:3] == (0, 0, 0)   # box blanked
    assert not _row_has_ink(screen, r, 10)                      # nothing drawn on the title row


def test_book_panel_caps_lines(screen):
    """BookPanel shows at most 10 lines -- the 11th row stays blank."""
    bp = BookPanel()
    bp.visible = True
    bp.render(screen, [f"m{i}" for i in range(30)])
    r = bp.rect
    line_h = BS.BOOKFONT.get_height() + 2
    first_line_y = 5 + line_h + 2                  # padding + title + spacing
    eleventh_y = first_line_y + 10 * line_h        # row that must remain empty
    if r.y + eleventh_y < r.bottom:
        assert not _row_has_ink(screen, r, eleventh_y)


def test_text_lines_panel_renders_arbitrary_lines(screen):
    pgn = TextLinesPanel(
        lambda: p.Rect(BS.PGN_X, BS.PGN_Y, BS.PGN_WIDTH, BS.PGN_HEIGHT),
        title="PGN moves",
    )
    pgn.visible = True
    pgn.render(screen, ["e2e4", "d2d4"])
    assert _row_has_ink(screen, pgn.rect, 10)


def test_panel_rects_match_boardscreen_geometry():
    assert tuple(BookPanel().rect) == (BS.BOOK_X, BS.BOOK_Y, BS.BOOK_WIDTH, BS.BOOK_HEIGHT)
    assert tuple(EnginePanel().rect) == (BS.CPU_X, BS.CPU_Y, BS.CPU_WIDTH, BS.CPU_HEIGHT)


def test_base_panel_render_is_abstract(screen):
    with pytest.raises(NotImplementedError):
        Panel(lambda: p.Rect(0, 0, 10, 10)).render(screen, None)
