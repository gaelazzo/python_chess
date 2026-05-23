"""Shared session state and constants for the chess trainer.

Holds the mutable parameter dicts and the UI/colour constants that used to be
module-level globals in chessMain.py, so the modules split out of chessMain can
import them without importing chessMain itself (which would create cycles).

The dicts (playParameters, positionParameters) are never reassigned, only
mutated, so importers can `from state import playParameters` safely. Values that
get *reassigned* (num_moves_to_show, play_position, id_course, courses, the menu
labels) live here too but are accessed as attributes -- `state.<name>` -- so a
reassignment is visible to every importer.
"""
import pygame_menu

# --- Play / position parameter dicts (mutated in place, never reassigned) ---
playParameters = {
    "whiteCPU": False,
    "blackCPU": True,
    "elo": None,
    "elomax": True,
    "white": "White",
    "black": "Black",
    "result": "",
    "event": "Play",
    "site": "Local",
    "gameid": "",
}

positionParameters = {
    "eco": None,
    "color": "w",
    "filename": None,
    "base": "openings",
    "player": None,
    "movesToAnalyze": 16,
    "blunderValue": 80,
    "ponderTime": 0.5,
    "useBook": False,
    "filename": "",
}

# --- Colour / selector constants ---
COLOR_MAP = {
    0: "w",
    1: "b",
    2: None,
}
REVERSE_COLOR_MAP = {v: k for k, v in COLOR_MAP.items()}

CIRCLE_COLOR = (15, 50, 180, 90)

# --- Menu theme ---
small_font_theme = pygame_menu.themes.THEME_BLUE.copy()
small_font_theme.title_font_size = 24
small_font_theme.widget_font_size = 18

# --- Reassigned session scalars (access as state.<name> so writes propagate) ---
num_moves_to_show = 4
play_position = 1  # 1 = skip initial stored moves, 0 = play them all

# Selected BrainMaster course (set from the course-chooser menu).
id_course = None
courses = None

# --- Menu label widgets (created in chessMain.mainMenu, read by the displays) ---
current_base_label = None
current_base_label2 = None
current_base_label3 = None
current_filename_label = None
current_filename_label3 = None
current_filename_label4 = None
current_ChessComFile_label = None
