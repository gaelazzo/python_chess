import os
import json
import sys



def get_base_path():
    """Restituisce il percorso della cartella dove si trova l'eseguibile o lo script"""
    if getattr(sys, 'frozen', False):  # Se è un eseguibile PyInstaller
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
CONFIG_FILE = os.path.join(BASE_PATH, "config.json")

#CONFIG_FILE = os.path.join(os.getcwd(), "config.json")
from types import SimpleNamespace

config = None

DEFAULT_CONFIG = {
    "base_url": "",
    "id_student": "",
    "engine": "stockfish.exe",
    "book": "",
    "engine_options": {
        "Hash": "1024",
        "Threads": "4",
        "SyzygyPath": ""
    }
}

import os
import json
from types import SimpleNamespace

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "base_url": "",
    "id_student": "",
    "engine": "",
    "book": "",
    "engine_options": {
        "Hash": "1024",
        "Threads": "4",
        "SyzygyPath": ""
    }
}

def load_config():
    """Legge la configurazione dal file JSON e la carica come oggetto, completando i valori mancanti"""
    global config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}

        # Unisce i default con i dati letti
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)

        # Gestisce i sotto-dizionari come engine_options
        engine_options = DEFAULT_CONFIG["engine_options"].copy()
        engine_options.update(data.get("engine_options", {}))
        merged["engine_options"] = engine_options

        config = SimpleNamespace(**merged)

        # (opzionale) salva di nuovo il file per aggiornare con i default mancanti
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"Errore nella lettura del file di configurazione: {e}")
        config = SimpleNamespace(**DEFAULT_CONFIG)



def save_config():
    """Salva la configurazione come JSON"""
    global config
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config.__dict__, f, indent=4)
    except Exception:
        pass

load_config()

