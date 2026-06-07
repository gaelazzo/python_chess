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
practice_order = "random"   # "priority" | "random"  -- ordering in Solve positions
                            # default Random: with real bases (especially openings) priority
                            # saturates the session on the same 3-4 positions with a very high wrong count.

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


# --- Persistence of the last menu selections --------------------------------
#
# Keys that are loaded from `config.user_prefs` at startup and saved every
# time a menu updater (`make_updater`/`make_selector_updater` in
# menu_helpers.py) modifies a value. In practice: the "Solve positions",
# "Study openings", "Play vs computer" etc. screens show, on restart, the
# last value chosen instead of the hard-coded defaults above.
#
# Form: (target, key)
# - target == "pp" -> positionParameters[key]
# - target == "play" -> playParameters[key]
# - target == "state" -> module-level scalar
#
# Intentionally does NOT include "gameid", "result", "courses", "id_course" -- they are
# volatile or loaded from BrainMaster, they make no sense as a "last choice".
_PERSIST_SPEC = [
    ("pp", "eco"),
    ("pp", "color"),
    ("pp", "filename"),
    ("pp", "base"),
    ("pp", "player"),
    ("pp", "movesToAnalyze"),
    ("pp", "blunderValue"),
    ("pp", "ponderTime"),
    ("pp", "useBook"),
    ("play", "whiteCPU"),
    ("play", "blackCPU"),
    ("play", "elo"),
    ("play", "elomax"),
    ("play", "white"),
    ("play", "black"),
    ("play", "event"),
    ("play", "site"),
    ("state", "num_moves_to_show"),
    ("state", "play_position"),
    ("state", "practice_order"),
]


def _saving_enabled() -> bool:
    """Disable saving during load (avoids noise in config.json)."""
    return _save_armed


_save_armed = False  # armed only after load_user_prefs()


def load_user_prefs() -> None:
    """Load the last menu selections from `config.user_prefs` into the dicts
    and the module variables. Types are already correct because JSON serializes
    native int/float/str/bool/None (just as we write them)."""
    global _save_armed
    import config as _cfg
    prefs = getattr(_cfg.config, "user_prefs", None) or {}
    for target, key in _PERSIST_SPEC:
        if key not in prefs:
            continue
        value = prefs[key]
        if target == "pp":
            positionParameters[key] = value
        elif target == "play":
            playParameters[key] = value
        elif target == "state":
            globals()[key] = value
    _save_armed = True


def save_user_prefs() -> None:
    """Snapshot the current selections into `config.user_prefs` and flush
    to disk. Called by every menu updater (idempotent)."""
    if not _save_armed:
        return
    import config as _cfg
    snapshot = {}
    for target, key in _PERSIST_SPEC:
        if target == "pp":
            snapshot[key] = positionParameters.get(key)
        elif target == "play":
            snapshot[key] = playParameters.get(key)
        elif target == "state":
            snapshot[key] = globals().get(key)
    _cfg.config.user_prefs = snapshot
    _cfg.save_config()


# Load immediately: on the first import of state, the dicts are already populated
# with the user's last selection. From this moment save_user_prefs() is armed.
load_user_prefs()
