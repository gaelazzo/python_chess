"""Opening-book side panel: the book moves for the current position."""
import os

import pygame as p

import BoardScreen as BS
from config import config
from .base import TextLinesPanel


class BookPanel(TextLinesPanel):
    """Shows the opening-book moves (at most 10), titled 'Book moves'.

    The title also carries the name of the configured book (e.g. 'Book moves
    (PowerBook2022)'), recomputed every render so it follows a book change made
    in Tools > Setup. Renders from a plain list of move strings (SAN or UCI)
    produced upstream -- e.g. `BoardSession.book_view()` -- so it never touches
    the book or GameState.
    """

    _BASE_TITLE = "Book moves"
    _MAX_NAME = 18          # keep the title from overflowing the narrow panel

    def __init__(self, font=None):
        super().__init__(
            lambda: p.Rect(BS.BOOK_X, BS.BOOK_Y, BS.BOOK_WIDTH, BS.BOOK_HEIGHT),
            title=self._BASE_TITLE,
            max_lines=10,
            font=font,
        )

    @classmethod
    def _book_name(cls) -> str:
        """Bare name of the configured book (no folder, no extension), or ''."""
        fn = (getattr(config, "book", "") or "").strip()
        if not fn:
            return ""
        name = os.path.splitext(os.path.basename(fn))[0]
        return (name[:cls._MAX_NAME - 1] + "…") if len(name) > cls._MAX_NAME else name

    def render(self, screen, lines) -> None:
        name = self._book_name()
        self.title = f"{self._BASE_TITLE} ({name})" if name else self._BASE_TITLE
        super().render(screen, lines)
