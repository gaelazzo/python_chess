"""Opening-book side panel: the book moves for the current position."""
import pygame as p

import BoardScreen as BS
from .base import TextLinesPanel


class BookPanel(TextLinesPanel):
    """Shows the opening-book moves (at most 10), titled 'Book moves'.

    Renders from a plain list of move strings (SAN or UCI) produced upstream --
    e.g. `BoardSession.book_view()` -- so it never touches the book or GameState.
    """

    def __init__(self, font=None):
        super().__init__(
            lambda: p.Rect(BS.BOOK_X, BS.BOOK_Y, BS.BOOK_WIDTH, BS.BOOK_HEIGHT),
            title="Book moves",
            max_lines=10,
            font=font,
        )
