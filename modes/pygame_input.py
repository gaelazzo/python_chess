"""Pygame adapter for the input port: translates pygame events into Commands.

The real game loops interleave event handling with the UI manager and the
toolbar, so this is a per-event translator (`translate`) rather than a queue-
draining `poll()`: the loop forwards each event to the manager/toolbar first,
then asks for the Command (if any). Keys absent from `keymap` and non-board
events return None -- the loop handles those itself (modal sub-flows, zoom,
engine, ...).

This is the mouse/keyboard arm of the same port a test drives with a
`ScriptedInput`: both produce Commands consumed by `BoardSession.apply()`.
"""
from typing import Dict, Optional

import pygame as p

import BoardScreen as BS
from modes.commands import Command, do, click, QUIT


class PygameInput:
    def __init__(self, keymap: Dict[int, str]):
        self.keymap = keymap          # {pygame key constant: session command name}

    def translate(self, event) -> Optional[Command]:
        """Map a single pygame event to a Command, or None if it isn't one."""
        if event.type == p.QUIT:
            return QUIT
        # Plain keys only: a held Shift/Ctrl means a different binding (e.g.
        # Shift+F = copy FEN vs. F = flip), so let modified keys fall through to
        # the loop's explicit handlers instead of the plain keymap.
        if (event.type == p.KEYDOWN and event.key in self.keymap
                and not (getattr(event, "mod", 0) & (p.KMOD_SHIFT | p.KMOD_CTRL))):
            return do(self.keymap[event.key])
        if event.type == p.MOUSEBUTTONDOWN and event.button == 1:
            row, col = BS.getRowColFromLocation(event.pos)
            return click(row, col)
        return None
