"""Persistent program configuration (loaded from / saved to config.json).

Exposes a SimpleNamespace `config` populated at import time by merging `config.json`
with `DEFAULT_CONFIG` (missing keys are added to the file). The path of
`config.json` is anchored to the script/executable folder, so it works
regardless of the launch directory (and supports PyInstaller bundles).
"""
import os
import json
import sys
from types import SimpleNamespace


def get_base_path():
    """Folder of the Python script or of the PyInstaller executable."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_PATH = get_base_path()
CONFIG_FILE = os.path.join(BASE_PATH, "config.json")

DEFAULT_CONFIG = {
    "base_url": "",
    "id_student": "",
    "api_key": "",        # BrainMaster device key, auto-filled on first use (ensure_registered)
    "admin_token": "",    # BrainMaster authoring token, maintainer-only (empty for normal users)
    "engine": "",
    "book": "",
    "engine_options": {
        "Hash": "1024",
        "Threads": "4",
        "SyzygyPath": "",
    },
    "maxErrorsToConsider": 10,   # capacity of the review session (Solve positions)
    "correctsToLearn": 3,         # consecutive correct answers needed to exit the session
    "user_prefs": {},             # last menu selections (populated by state.save_user_prefs)
    # TTS: case-insensitive substring searched in voice.name or voice.id; empty =
    # automatic selection for English. The available voices are printed
    # to the console at startup (see GameState.Voce._select_voice).
    "tts_voice": "",
    # TTS speed in words-per-minute (Windows default ~200). 150-180 is the
    # comfortable band for technical texts; below 100 = very slow, above 250 = snappy.
    "tts_rate": 170,
    # Absolute path to a PGN used as the "reference database" by the position
    # analysis feature (Y key in Play between humans). Empty = not
    # configured. Set from the Setup menu ("Choose reference DB").
    "reference_db": "",
}

config = None


def load_config():
    """Read config.json and populate `config`, completing missing keys from the defaults."""
    global config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}

        merged = DEFAULT_CONFIG.copy()
        merged.update(data)

        # Sub-dictionaries (engine_options): defaults + user override.
        engine_options = DEFAULT_CONFIG["engine_options"].copy()
        engine_options.update(data.get("engine_options", {}))
        merged["engine_options"] = engine_options

        config = SimpleNamespace(**merged)

        # Rewrite the file to propagate missing default keys.
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"Error reading the configuration file: {e}")
        config = SimpleNamespace(**DEFAULT_CONFIG)


def save_config():
    """Save the current configuration as JSON."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config.__dict__, f, indent=4)
    except Exception:
        pass


load_config()
