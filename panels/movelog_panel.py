"""Move-log side panel (column 2, top): game headers + the move list, with the
context label, scroll-to-tail, the evaluation and the wrapped comment of the
current move.

Unlike the other side boxes this one is NOT a flat list of strings: its layout
is height-aware (it drops the earliest rows so the latest moves stay visible) and
multi-colour, so it reads the GameState directly instead of pre-formatted lines.
It still honours the single-panel contract: one render() (write) plus the
inherited clear(). Logic moved verbatim from BoardScreen.drawMoveLog so the
pixels match.
"""
import pygame as p

import BoardScreen as BS
from .base import TextLinesPanel


class MoveLogPanel(TextLinesPanel):
    """The move log. Title-less; renders from a GameState (`gs`)."""

    def render(self, screen, gs) -> None:
        rect = self.clear(screen)
        if not self.visible:
            return
        font = self._font or BS.MOVELOGFONT
        assert font is not None, "BoardScreen.init() must run before rendering panels"
        movesPerRow = 1
        padding = 5
        lineSpacing = 2

        # Clip to the panel: a long comment / move list must not overflow into
        # the boxes below (which this render does not clear).
        prev_clip = screen.get_clip()
        screen.set_clip(rect)
        try:
            moveLog = gs.moveLog
            glyphs = gs.getMoveGlyphs()  # annotation glyph per move ('' if none)
            moveTexts = []
            for i in range(0, len(moveLog), 2):
                moveString = str(i // 2 + 1) + "." + moveLog[i].prettyChessNotation() + glyphs[i]
                if i + 1 < len(moveLog):
                    moveString += " " + moveLog[i + 1].prettyChessNotation() + glyphs[i + 1]
                moveTexts.append(moveString)
            textY = padding

            # Context label (what I am training): first line, cyan.
            if BS.context_label:
                textY += BS.add_txt_line(BS.context_label, textY, font, screen, rect, padding, lineSpacing, color="cyan")

            header = gs.getHeader()
            for i in range(0, len(header), 2):
                key = header[i]
                value = header[i + 1] if i + 1 < len(header) else ""
                textY += BS.add_txt_line(f"{key}: {value}", textY, font, screen, rect, padding, lineSpacing)

            # Scroll to the tail: drop the earliest rows so the latest moves stay
            # visible, with a "..." marker for the hidden ones.
            lineHeight = font.get_height() + lineSpacing
            n_rows = (len(moveTexts) + movesPerRow - 1) // movesPerRow
            max_rows = max(1, (BS.MOVE_LOG_HEIGHT - textY) // lineHeight)
            start_row = max(0, n_rows - max_rows)
            if start_row > 0:
                BS.add_txt_line("...", textY, font, screen, rect, padding, lineSpacing, color="gray")
                textY += lineHeight
                start_row = min(n_rows, start_row + 1)
            for r in range(start_row, n_rows):
                i = r * movesPerRow
                text = ""
                for j in range(movesPerRow):
                    if i + j < len(moveTexts):
                        text += moveTexts[i + j] + " "
                textY += BS.add_txt_line(text, textY, font, screen, rect, padding, lineSpacing)

            comment = gs.getMoveComment()
            if comment:
                textY += BS.add_txt_line("Comment:", textY, font, screen, rect, padding, lineSpacing, color="yellow")
                maxw = BS.MOVE_LOG_WIDTH - 2 * padding
                lines = []
                line = ""
                for word in comment.split():
                    trial = (line + " " + word).strip()
                    if line and font.size(trial)[0] > maxw:
                        lines.append(line)
                        line = word
                    else:
                        line = trial
                if line:
                    lines.append(line)
                lineHeight = font.get_height() + lineSpacing
                maxLines = max(0, (BS.MOVE_LOG_HEIGHT - textY) // lineHeight)
                if len(lines) > maxLines:
                    lines = lines[:max(0, maxLines - 1)] + ["..."]
                for ln in lines:
                    textY += BS.add_txt_line(ln, textY, font, screen, rect, padding, lineSpacing)
        finally:
            screen.set_clip(prev_clip)
