"""Input port: a command stream the modes consume, independent of its source.

The whole point of BoardSession is that the game is *driven by commands* and
*queried as a view-model* -- never by pygame directly. This module is the input
half. A `Command` is a single intent (a board click or a named command); an
`InputSource` yields the commands pending since the last poll.

The source does not matter: a test feeds a `ScriptedInput`, the real app feeds a
pygame adapter (events -> Commands). Same controller, same `BoardSession.apply()`
path. This is the dual of the output side, where `view_model()` is the structure
and the renderer is the video.

Pure: no pygame, no GameState -- trivially testable and importable headless.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Command:
    """A single intent. `kind` selects the payload:

    - "click": a board square (row, col)
    - "do":    a named session command (name) -- "undo", "next", "book",
               "pgn", "flip", "analyze", "truncate", "delete", ...
    - "quit":  leave the mode
    """
    kind: str
    name: Optional[str] = None
    row: Optional[int] = None
    col: Optional[int] = None


def do(name: str) -> Command:
    """A named command, e.g. do("undo")."""
    return Command("do", name=name)


def click(row: int, col: int) -> Command:
    """A board click on (row, col)."""
    return Command("click", row=row, col=col)


QUIT = Command("quit")


class InputSource:
    """Port: returns the commands pending since the last poll (possibly empty)."""

    def poll(self) -> List[Command]:
        raise NotImplementedError


class ScriptedInput(InputSource):
    """Test adapter: replays a fixed list of commands, draining on first poll.

    `poll()` returns the whole script once, then empty lists -- mirroring a
    pygame event queue that empties as it is read.
    """

    def __init__(self, commands):
        self._commands = list(commands)

    def poll(self) -> List[Command]:
        pending, self._commands = self._commands, []
        return pending
