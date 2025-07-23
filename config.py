import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
from types import SimpleNamespace

config = None

def load_config():
    """Legge la configurazione dal file JSON e la carica come oggetto"""
    global config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            config = SimpleNamespace(**data)
    except FileNotFoundError:
        config = SimpleNamespace(base_url="", id_student="", engine="")
    except Exception:
        config = SimpleNamespace(base_url="", id_student="", engine="")

def save_config():
    """Salva la configurazione come JSON"""
    global config
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config.__dict__, f, indent=4)
    except Exception:
        pass

load_config()

