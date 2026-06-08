"""View layer: one class per side panel (book, engine, ...).

Each panel renders from a plain data slice (e.g. a list of SAN strings) -- never
from GameState -- so the view stays decoupled from the logic, exactly like
`BoardSession.view_model()`. The data modules (book, UCIEngines, position_stats)
stay pure; panels depend only on those *values* and on BoardScreen's geometry
primitives. Toggling a panel is just flipping its `visible` flag (owned by the
session); a renderer draws the visible panels from the view-model.
"""
from .base import Panel, TextLinesPanel
from .book_panel import BookPanel
from .engine_panel import EnginePanel

__all__ = ["Panel", "TextLinesPanel", "BookPanel", "EnginePanel"]
