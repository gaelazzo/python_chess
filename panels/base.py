"""Base classes for the side panels (see panels/__init__.py for the rationale).

A `Panel` owns a fixed screen rectangle and a `visible` flag. Rendering is pure:
it paints into its rectangle and never flips the display -- the caller decides
when to present (the main loop's single flip, or a partial update for a panel
drawn off the main render path, e.g. the engine callback).

`TextLinesPanel` is the common shape of every existing side box (book / engine /
pgn in BoardScreen): a black rectangle, a white title, then a list of text lines.
It renders from a plain list of strings -- never from GameState -- so the view
stays decoupled from the logic.
"""
import pygame as p

import BoardScreen as BS


class Panel:
    """A fixed-rectangle side panel with a visibility flag.

    Subclasses implement `render(screen, data)`. `clear` blanks the rectangle;
    a hidden panel renders as just the cleared rectangle (so toggling it off
    leaves no ghost). `rect` is read lazily from the geometry primitives so it
    tracks any BoardScreen layout change.
    """

    def __init__(self, rect_fn, title=""):
        self._rect_fn = rect_fn      # () -> p.Rect, read lazily (geometry may change)
        self.title = title
        self.visible = True

    @property
    def rect(self) -> p.Rect:
        return self._rect_fn()

    def clear(self, screen) -> p.Rect:
        rect = self.rect
        p.draw.rect(screen, p.Color("black"), rect)
        return rect

    def render(self, screen, data) -> None:
        raise NotImplementedError


class TextLinesPanel(Panel):
    """Title + a list of text lines, laid out exactly like the old BoardScreen
    draw* helpers (same font, padding and line spacing, so the pixels match).

    `lines` is the list of strings to show. `max_lines` caps it (the book box
    showed at most 10); None means no cap. A hidden panel just clears its box.
    """

    def __init__(self, rect_fn, title="", max_lines=None):
        super().__init__(rect_fn, title)
        self.max_lines = max_lines

    def render(self, screen, lines) -> None:
        rect = self.clear(screen)
        if not self.visible:
            return
        font = BS.BOOKFONT
        assert font is not None, "BoardScreen.init() must run before rendering panels"
        # Title: antialias off, matching the old draw* helpers.
        title_surf = font.render(self.title, False, p.Color("white"))
        screen.blit(title_surf, (rect.x + 5, rect.y + 5))
        padding = 5
        line_spacing = 2
        text_y = padding + title_surf.get_height() + line_spacing
        shown = lines if self.max_lines is None else lines[:self.max_lines]
        for line in shown:
            surf = font.render(line, True, p.Color("white"))   # lines: antialias on
            screen.blit(surf, (rect.x + padding, rect.y + text_y))
            text_y += surf.get_height() + line_spacing
