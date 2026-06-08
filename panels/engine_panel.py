"""Engine (CPU) analysis side panel: the engine's evaluation lines."""
import pygame as p

import BoardScreen as BS
from .base import TextLinesPanel


class EnginePanel(TextLinesPanel):
    """Shows the engine analysis lines in the bottom CPU strip, titled 'CPU'.

    Renders from a plain list of strings (the formatted engine info, e.g.
    `UCIEngines.analysis_results`) so it stays decoupled from the engine.
    """

    def __init__(self):
        super().__init__(
            lambda: p.Rect(BS.CPU_X, BS.CPU_Y, BS.CPU_WIDTH, BS.CPU_HEIGHT),
            title="CPU",
        )
