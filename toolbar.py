"""Top toolbar of clickable colour-icon buttons for the in-game loops.

`IconToolbar` is a custom-drawn (no pygame_gui) horizontal row of colour PNG
icons (images/icons/<name>.png, baked from emoji by tools/generate_icons.py).
Every mode builds one or more: the analysis screen (modes/play_game.py) uses a
main tool row, a right-aligned structure group and a bottom navigation/move bar;
the training modes use a single top row with their own buttons.

Drawing it ourselves gives full control over the icons, the hover / active /
disabled states and a tooltip we can keep clean. The keyboard shortcuts remain
active in parallel: every button's `handler` posts the same key its action uses,
so the KEYDOWN code path does the work and nothing is duplicated.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import pygame as p

import BoardScreen as BS
from app_context import app


@dataclass
class ToolbarAction:
    label: str                                      # accessible name / text fallback when no icon
    tooltip: str                                    # on-hover text
    handler: Callable[[], None]                     # callback on click
    enabled: Callable[[], bool] = field(default=lambda: True)  # re-evaluated every frame
    active: Callable[[], bool] = field(default=lambda: False)   # True -> button "pressed" (re-evaluated every frame)
    icon: Optional[str] = None                      # icon name in images/icons/<icon>.png


_BTN_MARGIN_X = 8
_BTN_MARGIN_Y = 4


# --------------------------------------------------------------------------- #
# Icon toolbar: a custom-drawn row of colour PNG icons (images/icons/<name>.png).
# Used by the analysis screen (top tool row + right structure group + bottom
# navigation bar) and by every training mode (a single top row). Drawing it
# ourselves gives full control over the colour icons, hover/active/disabled
# states and a tooltip we can keep clean.
# --------------------------------------------------------------------------- #

_ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "icons")
_icon_cache: dict = {}

_ICONBAR_BG = p.Color(238, 238, 238)        # light-grey strip, reads as a toolbar
_ICONBAR_SEP = p.Color(200, 200, 200)       # thin separator line vs. the board
_BTN_HOVER = p.Color(212, 226, 245)         # light blue behind a hovered button
_BTN_ACTIVE = p.Color(170, 200, 235)        # stronger blue for an active toggle
_BTN_ACTIVE_BORDER = p.Color(70, 120, 190)
_TIP_BG = p.Color(45, 45, 45)
_TIP_FG = p.Color(245, 245, 245)
_TIP_DELAY = 0.5                            # seconds of hover before the tooltip


def _load_icon(name: str, size: int):
    """Load images/icons/<name>.png scaled to size x size (cached). Returns None
    when the file is missing so the button falls back to its text label."""
    key = (name, size)
    if key in _icon_cache:
        return _icon_cache[key]
    path = os.path.join(_ICONS_DIR, f"{name}.png")
    surf = None
    if os.path.exists(path):
        img = p.image.load(path)
        try:
            img = img.convert_alpha()
        except p.error:
            pass                            # no display yet (headless): blit as-is
        surf = p.transform.smoothscale(img, (size, size))
    _icon_cache[key] = surf
    return surf


class _IconButton:
    __slots__ = ("action", "rect", "icon")

    def __init__(self, action: ToolbarAction, rect: p.Rect, icon):
        self.action = action
        self.rect = rect
        self.icon = icon


class IconToolbar:
    """A horizontal row of colour-icon buttons, drawn by hand (no pygame_gui).

    The surface API is process_event / update / draw / kill / pointer_in_toolbar,
    so a mode can hold one or several. Each button shows a hover highlight, an
    "active" toggle state and a greyed-out disabled state, plus a tooltip after a
    short hover. The strip is repainted every frame, so a tooltip cannot leave
    residue inside it.
    """

    def __init__(self, actions, *, y: int, height: int, x0: int = 0,
                 width=None, align: str = "left", tooltip_above: bool = False,
                 icon_size=None):
        self._actions = list(actions)
        self._y = y
        self._height = height
        self._x0 = x0
        self._width = width if width is not None else BS.SCREEN_WIDTH - x0
        self._tooltip_above = tooltip_above
        self._tip_font = p.font.SysFont("Arial", 13)
        btn = height - 2 * _BTN_MARGIN_Y                       # square button side
        isize = icon_size if icon_size is not None else btn - 6
        gap = 6
        spacer = btn // 2                                      # width of a `None` separator
        # A `None` entry in `actions` is a group separator (a half-width gap), so
        # one toolbar can hold visually distinct groups (e.g. nav | move actions).
        widths = [(btn if a is not None else spacer) for a in self._actions]
        total = sum(widths) + gap * max(0, len(widths) - 1)
        if align == "center":
            start = x0 + max(_BTN_MARGIN_X, (self._width - total) // 2)
        elif align == "right":
            start = x0 + max(_BTN_MARGIN_X, self._width - total - _BTN_MARGIN_X)
        else:
            start = x0 + _BTN_MARGIN_X
        self._buttons: List[_IconButton] = []
        x = start
        for a, w in zip(self._actions, widths):
            if a is not None:
                rect = p.Rect(x, y + _BTN_MARGIN_Y, btn, btn)
                icon = _load_icon(a.icon, isize) if a.icon else None
                self._buttons.append(_IconButton(a, rect, icon))
            x += w + gap
        self._hover_idx = None
        self._hover_time = 0.0

    def process_event(self, event) -> bool:
        """True if the click is ours (a button press, or anywhere on the strip)."""
        if event.type == p.MOUSEBUTTONDOWN and event.button == 1:
            for b in self._buttons:
                if b.rect.collidepoint(event.pos) and b.action.enabled():
                    b.action.handler()
                    return True
            return self.pointer_in_toolbar(event.pos)   # swallow strip clicks
        return False

    def update(self, time_delta: float) -> None:
        pos = p.mouse.get_pos()
        idx = None
        for i, b in enumerate(self._buttons):
            if b.rect.collidepoint(pos) and b.action.enabled():
                idx = i
                break
        if idx != self._hover_idx:
            self._hover_idx = idx
            self._hover_time = 0.0
        elif idx is not None:
            self._hover_time += time_delta

    def draw(self, surface) -> None:
        strip = p.Rect(self._x0, self._y, self._width, self._height)
        surface.fill(_ICONBAR_BG, strip)
        # separator on the side that faces the board
        if self._tooltip_above:   # nav bar (board is above) -> line on top
            p.draw.line(surface, _ICONBAR_SEP, (self._x0, self._y),
                        (self._x0 + self._width - 1, self._y))
        else:                     # top bar (board is below) -> line on bottom
            yb = self._y + self._height - 1
            p.draw.line(surface, _ICONBAR_SEP, (self._x0, yb),
                        (self._x0 + self._width - 1, yb))
        for i, b in enumerate(self._buttons):
            enabled = b.action.enabled()
            if b.action.active():
                p.draw.rect(surface, _BTN_ACTIVE, b.rect, border_radius=6)
                p.draw.rect(surface, _BTN_ACTIVE_BORDER, b.rect, width=2, border_radius=6)
            elif enabled and i == self._hover_idx:
                p.draw.rect(surface, _BTN_HOVER, b.rect, border_radius=6)
            if b.icon is not None:
                icon = b.icon
                if not enabled:
                    icon = b.icon.copy()
                    icon.fill((255, 255, 255, 80), special_flags=p.BLEND_RGBA_MULT)
                surface.blit(icon, icon.get_rect(center=b.rect.center))
            else:
                txt = self._tip_font.render(b.action.label, True, p.Color(40, 40, 40))
                surface.blit(txt, txt.get_rect(center=b.rect.center))
        self._draw_tooltip(surface)

    def _draw_tooltip(self, surface) -> None:
        if self._hover_idx is None or self._hover_time < _TIP_DELAY:
            return
        b = self._buttons[self._hover_idx]
        text = b.action.tooltip
        if not text:
            return
        ts = self._tip_font.render(text, True, _TIP_FG)
        pad = 5
        w, h = ts.get_width() + 2 * pad, ts.get_height() + 2 * pad
        top = (b.rect.top - h - 4) if self._tooltip_above else (b.rect.bottom + 4)
        left = max(2, min(b.rect.centerx - w // 2, BS.SCREEN_WIDTH - w - 2))
        p.draw.rect(surface, _TIP_BG, p.Rect(left, top, w, h), border_radius=4)
        surface.blit(ts, (left + pad, top + pad))

    def pointer_in_toolbar(self, pos) -> bool:
        return (self._x0 <= pos[0] < self._x0 + self._width and
                self._y <= pos[1] < self._y + self._height)

    def icon_rect(self, name: str):
        """Screen rect of the button with the given icon name, or None. Lets a
        modal sub-flow (e.g. the variation picker) hit-test a nav button while
        the main loop -- and its process_event -- is suspended."""
        for b in self._buttons:
            if b.action.icon == name:
                return b.rect
        return None

    def content_right(self) -> int:
        """Right edge (x) of the last button -- so a caller can place a second,
        right-aligned toolbar right after this one without overlap."""
        if not self._buttons:
            return self._x0 + _BTN_MARGIN_X
        return self._buttons[-1].rect.right

    def kill(self) -> None:
        self._buttons = []
        self._hover_idx = None
