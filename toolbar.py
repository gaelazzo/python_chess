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
    label: str                                      # testo del bottone (1-2 char)
    tooltip: str                                    # testo on-hover
    handler: Callable[[], None]                     # callback al click
    enabled: Callable[[], bool] = field(default=lambda: True)  # rivalutato a ogni frame
    active: Callable[[], bool] = field(default=lambda: False)   # True -> bottone "premuto" (rivalutato a ogni frame)


_BTN_WIDTH = 56     # abbastanza largo per parole brevi tipo "Undo"/"Reset"
_BTN_GAP = 4
_BTN_MARGIN_X = 8
_BTN_MARGIN_Y = 4


class Toolbar:
    """Fascia di pulsanti-icona in alto. Usa l'UIManager gia' inizializzato
    in `chessMain.runMain` (lo stesso che ospita i file dialog).
    """

    def __init__(self, actions: List[ToolbarAction], y: int = 0, height: int = BS.TOOLBAR_HEIGHT):
        self._actions = list(actions)
        self._y = y
        self._height = height
        self._buttons: List[UIButton] = []
        x = _BTN_MARGIN_X
        btn_h = max(16, height - 2 * _BTN_MARGIN_Y)
        for a in self._actions:
            btn = UIButton(
                relative_rect=p.Rect(x, y + _BTN_MARGIN_Y, _BTN_WIDTH, btn_h),
                text=a.label,
                manager=app.manager,
                tool_tip_text=a.tooltip,
            )
            self._buttons.append(btn)
            x += _BTN_WIDTH + _BTN_GAP

    def process_event(self, event) -> bool:
        """Ritorna True se l'evento e' un click su uno dei nostri bottoni."""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            for i, btn in enumerate(self._buttons):
                if event.ui_element is btn:
                    self._actions[i].handler()
                    return True
        return False

    def update(self, time_delta: float) -> None:
        """Rivaluta gli enabled, poi aggiorna il manager."""
        for a, btn in zip(self._actions, self._buttons):
            if a.enabled():
                btn.enable()
            else:
                btn.disable()
            # stato "attivo/premuto": usa lo stato selected di pygame_gui
            # (reso con i colori @selected del tema)
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
        """True se le coordinate cadono dentro la fascia toolbar."""
        return self._y <= pos[1] < self._y + self._height

    def kill(self) -> None:
        """Rimuove tutti i nostri UIButton dal manager. Da chiamare quando
        si esce dal mode, altrimenti i bottoni si accumulerebbero tra invocazioni.
        """
        for btn in self._buttons:
            btn.kill()
        self._buttons = []
