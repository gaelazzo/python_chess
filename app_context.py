"""Shared application/UI context for the chess trainer.

Holds the pygame infrastructure (display surface, GUI manager, window
dimensions, clock, font, the root menu and the main-loop flag) that used to
live as module-level globals in ``chessMain.py``.

A single shared instance, ``app``, is imported wherever this state is needed.
Reading or *reassigning* one of these values is done through ``app`` (e.g.
``app.screen = ...``), so the ``global`` keyword is no longer required and the
functions that use them can be moved to other modules without dragging the
globals along.
"""
from __future__ import annotations

from typing import Optional

import pygame as p


class AppContext:
    """Single source of truth for the shared pygame/UI state."""

    def __init__(self) -> None:
        # Display / GUI infrastructure (initialised in chessMain.runMain).
        self.screen: Optional[p.Surface] = None
        self.manager = None          # pygame_gui.UIManager
        self.W: Optional[int] = None
        self.H: Optional[int] = None
        self.clock: Optional[p.time.Clock] = None
        self.myfont: Optional[p.font.Font] = None

        # Constants / tunables.
        self.FPS: int = 60
        self.timeFactor: float = 500.0

        # Main menu lifecycle.
        self.main_menu = None        # pygame_menu.Menu (built in chessMain.mainMenu)
        self.main_running: bool = True

    def main_background(self) -> None:
        """Fill the window with the menu background colour."""
        self.screen.fill(p.Color("white"))

    def delay(self, unit: float) -> None:
        """Pause for ``unit`` time units (scaled by ``timeFactor``)."""
        p.time.delay(int(unit * self.timeFactor))


# Single shared instance imported across the application.
app = AppContext()
