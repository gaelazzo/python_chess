"""Engine (CPU) analysis side panel: the engine's evaluation lines."""
import pygame as p

import BoardScreen as BS
from .base import TextLinesPanel


class EnginePanel(TextLinesPanel):
    """Shows the engine analysis in the bottom CPU strip.

    The first row replaces the old "CPU" title with the **headline evaluation**
    (best line, White's POV) rendered LARGE, and the **engine name** next to it
    (e.g. `+0.80   Stockfish 16`). The analysis lines (time/nodes + variations)
    follow below in the normal font. Both the eval and the name come from
    `UCIEngines`; the lines are still passed in as plain strings.
    """

    def __init__(self):
        super().__init__(
            lambda: p.Rect(BS.CPU_X, BS.CPU_Y, BS.CPU_WIDTH, BS.CPU_HEIGHT),
            title="CPU",
        )
        self._big_font_cache = None

    def _big_font(self):
        if self._big_font_cache is None:
            self._big_font_cache = p.font.SysFont("Arial", 26, bold=True)
        return self._big_font_cache

    def render(self, screen, lines) -> None:
        import UCIEngines
        rect = self.clear(screen)
        if not self.visible:
            return
        font = self._font or BS.BOOKFONT
        assert font is not None, "BoardScreen.init() must run before rendering panels"
        pad = 5

        # Header row: big eval + engine name (replaces the old "CPU" title).
        big = self._big_font()
        header_h = big.get_height()
        x = rect.x + pad
        eval_str = UCIEngines.current_eval()
        if eval_str:
            es = big.render(eval_str, True, p.Color("white"))
            screen.blit(es, (x, rect.y + 2))
            x += es.get_width() + 12
        best = UCIEngines.current_best_move()
        if best:                                   # the move that eval belongs to
            bs = big.render(best, True, p.Color(120, 235, 140))   # green: the best move
            screen.blit(bs, (x, rect.y + 2))
            x += bs.get_width() + 12
        name = UCIEngines.engine_name()
        if name:
            ns = font.render(name, True, p.Color(170, 200, 235))   # soft blue-grey
            screen.blit(ns, (x, rect.y + 2 + (header_h - ns.get_height()) // 2))

        # Analysis lines below the header, clipped to the panel.
        line_spacing = 2
        text_y = 2 + header_h + line_spacing
        prev_clip = screen.get_clip()
        screen.set_clip(rect)
        try:
            for line in lines:
                surf = font.render(line, True, p.Color("white"))
                screen.blit(surf, (rect.x + pad, rect.y + text_y))
                text_y += surf.get_height() + line_spacing
        finally:
            screen.set_clip(prev_clip)
