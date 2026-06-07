"""Top toolbar of clickable icon buttons for the in-game loops.

Builds a horizontal row of `pygame_gui.UIButton` on the shared `app.manager`,
each with a `tool_tip_text` shown on hover. Phase 1: used only by
`modes/play_game.py`. Reusable as-is by other game-loop modes (Solve positions,
Study openings, etc.) — only the list of `ToolbarAction` changes.

The keyboard shortcuts remain active in parallel: every button's `handler`
calls the same code path as the corresponding key handler.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List

import pygame as p
import pygame_gui
from pygame_gui.elements import UIButton

import BoardScreen as BS
from app_context import app


@dataclass
class ToolbarAction:
    label: str                                      # button text (1-2 chars)
    tooltip: str                                    # on-hover text
    handler: Callable[[], None]                     # callback on click
    enabled: Callable[[], bool] = field(default=lambda: True)  # re-evaluated every frame
    active: Callable[[], bool] = field(default=lambda: False)   # True -> button "pressed" (re-evaluated every frame)


_BTN_WIDTH = 56     # wide enough for short words like "Undo"/"Reset"
_BTN_GAP = 4
_BTN_MARGIN_X = 8
_BTN_MARGIN_Y = 4


class Toolbar:
    """Top row of icon buttons. Uses the UIManager already initialized
    in `chessMain.runMain` (the same one that hosts the file dialogs).
    """

    def __init__(self, actions: List[ToolbarAction], y: int = 0, height: int = BS.TOOLBAR_HEIGHT):
        self._actions = list(actions)
        self._y = y
        self._height = height
        self._buttons: List[UIButton] = []
        x = _BTN_MARGIN_X
        btn_h = max(16, height - 2 * _BTN_MARGIN_Y)
        # Adaptive button width: if the buttons don't all fit within the
        # screen with _BTN_WIDTH=56, we shrink them to avoid the last one (Quit)
        # getting cut off. For smaller toolbars the default 56 stays.
        n = max(1, len(self._actions))
        available = BS.SCREEN_WIDTH - 2 * _BTN_MARGIN_X - (n - 1) * _BTN_GAP
        btn_width = min(_BTN_WIDTH, max(36, available // n))
        for a in self._actions:
            btn = UIButton(
                relative_rect=p.Rect(x, y + _BTN_MARGIN_Y, btn_width, btn_h),
                text=a.label,
                manager=app.manager,
                tool_tip_text=a.tooltip,
            )
            self._buttons.append(btn)
            x += btn_width + _BTN_GAP

    def process_event(self, event) -> bool:
        """Returns True if the event is a click on one of our buttons."""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            for i, btn in enumerate(self._buttons):
                if event.ui_element is btn:
                    self._actions[i].handler()
                    return True
        return False

    def update(self, time_delta: float) -> None:
        """Re-evaluates the enabled states, then updates the manager."""
        for a, btn in zip(self._actions, self._buttons):
            if a.enabled():
                btn.enable()
            else:
                btn.disable()
            # "active/pressed" state: use pygame_gui's selected state
            # (rendered with the theme's @selected colors)
            if a.active():
                if not btn.is_selected:
                    btn.select()
            else:
                if btn.is_selected:
                    btn.unselect()
        app.manager.update(time_delta)

    def draw(self, surface) -> None:
        app.manager.draw_ui(surface)

    def pointer_in_toolbar(self, pos) -> bool:
        """True if the coordinates fall within the toolbar strip."""
        return self._y <= pos[1] < self._y + self._height

    def kill(self) -> None:
        """Removes all our UIButtons from the manager. Must be called when
        leaving the mode, otherwise the buttons would accumulate across invocations.
        """
        for btn in self._buttons:
            btn.kill()
        self._buttons = []
