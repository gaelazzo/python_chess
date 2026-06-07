"""Persistent program configuration (loaded from / saved to config.json).

Espone un SimpleNamespace `config` popolato all'import fondendo `config.json`
con `DEFAULT_CONFIG` (le chiavi mancanti vengono aggiunte al file). Il path di
`config.json` e' ancorato alla cartella dello script/eseguibile, cosi' funziona
indipendentemente dalla directory di lancio (e supporta i bundle PyInstaller).
"""
import os
import json
import sys
from types import SimpleNamespace


def get_base_path():
    """Cartella dello script Python o dell'eseguibile PyInstaller."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_PATH = get_base_path()
CONFIG_FILE = os.path.join(BASE_PATH, "config.json")

DEFAULT_CONFIG = {
    "base_url": "",
    "id_student": "",
    "engine": "",
    "book": "",
    "engine_options": {
        "Hash": "1024",
        "Threads": "4",
        "SyzygyPath": "",
    },
    "maxErrorsToConsider": 10,   # capacita' della sessione di ripasso (Solve positions)
    "correctsToLearn": 3,         # risposte corrette consecutive per uscire dalla sessione
    "user_prefs": {},             # ultime selezioni nei menu (popolate da state.save_user_prefs)
    # TTS: sostringa case-insensitive cercata in voice.name o voice.id; vuoto =
    # selezione automatica per inglese. Le voci disponibili vengono stampate
    # sulla console all'avvio (vedi GameState.Voce._select_voice).
    "tts_voice": "",
    # Velocita' TTS in parole-per-minuto (default Windows ~200). 150-180 e' la
    # banda comoda per testi tecnici; sotto 100 = molto lento, oltre 250 = scattante.
    "tts_rate": 170,
    # Path assoluto a un PGN usato come "database di riferimento" dalla feature
    # di analisi posizione (tasto Y in Play between humans). Vuoto = non
    # configurato. Settato dal menu Setup ("Choose reference DB").
    "reference_db": "",
}

config = None


def load_config():
    """Legge config.json e popola `config`, completando le chiavi mancanti dai default."""
    global config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}

        merged = DEFAULT_CONFIG.copy()
        merged.update(data)

        # Sotto-dizionari (engine_options): default + override utente.
        engine_options = DEFAULT_CONFIG["engine_options"].copy()
        engine_options.update(data.get("engine_options", {}))
        merged["engine_options"] = engine_options

        config = SimpleNamespace(**merged)

        # Riscrive il file per propagare le chiavi di default mancanti.
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"Error reading the configuration file: {e}")
        config = SimpleNamespace(**DEFAULT_CONFIG)


def save_config():
    """Salva la configurazione corrente come JSON."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config.__dict__, f, indent=4)
    except Exception:
        pass


load_config()
