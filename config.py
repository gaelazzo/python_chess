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

