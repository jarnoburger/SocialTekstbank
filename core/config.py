"""Instellingen en vaste paden van SocialTekstbank."""
import json
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
ONLINE_PATH = os.path.join(DATA_DIR, "online.json")
LINKS_PATH = os.path.join(DATA_DIR, "links.json")
HASHES_PATH = os.path.join(DATA_DIR, "hashes.json")
OPRUIMEN_PATH = os.path.join(DATA_DIR, "opruimen.json")
EXPORT_DIR = os.path.join(DATA_DIR, "export")

DEFAULT_CONFIG = {
    # Meta Graph API-versie; aanpasbaar als Meta een versie uitfaseert.
    "graph_version": "v25.0",
    "app_id": "",
    "app_secret": "",
    "user_token_long": "",
    "user_token_expires": "",
    # Wordt gevuld door de installatie-stap: per FB-pagina het gekoppelde IG-account.
    "accounts": [],
    # Lokale mappen die gescand worden. merk = label in het dashboard.
    "roots": [
        {"merk": "SJB", "pad": r"C:\Users\jarno\OneDrive\_Studio JarnoBurger\_To Promote"},
        {"merk": "Lichtjes", "pad": r"C:\Users\jarno\OneDrive\_Lichtjes Dome\_To Promote"},
        # werken die op beide eigen plekken gepost zijn (verplaatst 06-10-2026)
        {"merk": "SJB", "pad": r"C:\Users\jarno\OneDrive\_Studio JarnoBurger\_Promoted"},
        {"merk": "Lichtjes", "pad": r"C:\Users\jarno\OneDrive\_Lichtjes Dome\_Promoted"},
    ],
    # Hamming-afstand (van 64 bits) waaronder twee beelden als 'zelfde' gelden.
    "hash_drempel": 10,
}


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    _ensure_dirs()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(load_json(CONFIG_PATH, {}))
    return cfg


def save_config(cfg):
    save_json(CONFIG_PATH, cfg)
