# =============================================================================
# config.py — Module de Configuration d'AURA
# =============================================================================
# Ce module gère :
# - Le chargement/sauvegarde des paramètres utilisateur (settings.json)
# - Le système de traduction bilingue (translations.json)
# - Les chemins de fichiers de l'application
# - Le logging centralisé
# =============================================================================

import json
import os
import logging
from pathlib import Path
import sys

# ---------------------------------------------------------------------------
# CHEMINS — On utilise AppData pour que les configurations (clé API, etc.)
# soient conservées même si l'application est déplacée ou relancée.
# ---------------------------------------------------------------------------

# Dossier d'installation (là où l'exe ou le py se trouve pour les ressources fixes)
INSTALL_DIR = Path(__file__).parent.resolve()

# Dossier de sauvegarde persistante (AppData/Roaming/AURA)
APP_DATA_DIR = Path(os.getenv("APPDATA")) / "AURA"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Les fichiers de données vont dans AppData pour ne jamais être perdus
SETTINGS_FILE = APP_DATA_DIR / "settings.json"
HISTORY_FILE = APP_DATA_DIR / "history.json"
LOG_FILE = APP_DATA_DIR / "aura.log"

# Les fichiers statiques peuvent rester dans le dossier d'installation
TRANSLATIONS_FILE = INSTALL_DIR / "translations.json"
INDEX_FILE = APP_DATA_DIR / "index.json"

# ---------------------------------------------------------------------------
# VALEURS PAR DÉFAUT — Utilisées si settings.json est absent ou incomplet
# Aucun texte n'est codé en dur dans les autres modules
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "language": "fr",
    "hotkey": "ctrl+space",
    "scan_directories": [
        "C:\\Program Files",
        "C:\\Program Files (x86)"
    ],
    "deep_scan_drives": ["C:\\", "D:\\"],
    "theme": "auto",
    "voice_speed": 180,
    "voice_volume": 0.9,
    "max_suggestions": 8,
    "history_size": 50,
    "log_level": "INFO",
    "autostart": False,
    "stealth_hotkey": "f9",
    "gemini_api_key": ""
}

# ---------------------------------------------------------------------------
# CHARGEMENT DES FICHIERS JSON
# ---------------------------------------------------------------------------

def _load_json(filepath: Path, default: dict) -> dict:
    """
    Charge un fichier JSON. Si le fichier n'existe pas ou est corrompu,
    retourne la valeur par défaut et recrée le fichier.
    """
    try:
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        else:
            # Le fichier n'existe pas : on le crée avec les valeurs par défaut
            _save_json(filepath, default)
            return default.copy()
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"Erreur de lecture de {filepath.name}: {e}. Utilisation des valeurs par défaut.")
        return default.copy()


def _save_json(filepath: Path, data: dict) -> None:
    """Sauvegarde un dictionnaire dans un fichier JSON formaté."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        logging.error(f"Impossible de sauvegarder {filepath.name}: {e}")

# ---------------------------------------------------------------------------
# SETTINGS — Paramètres de l'utilisateur
# ---------------------------------------------------------------------------

# Chargement initial des paramètres
# On fusionne avec DEFAULT_SETTINGS pour garantir que toutes les clés existent
_raw_settings = _load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
settings = {**DEFAULT_SETTINGS, **_raw_settings}


def save_settings() -> None:
    """
    Sauvegarde les paramètres actuels dans settings.json.
    Appellée après modification d'un paramètre (ex: changement de langue).
    """
    _save_json(SETTINGS_FILE, settings)


def get_setting(key: str, default=None):
    """Récupère un paramètre par sa clé. Retourne 'default' si absent."""
    return settings.get(key, default)


def set_setting(key: str, value) -> None:
    """Modifie un paramètre et sauvegarde automatiquement."""
    settings[key] = value
    save_settings()

def set_autostart(enable: bool) -> None:
    """Ajoute ou retire AURA du démarrage de Windows via le Registre."""
    import sys
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "AURA_V3"
    
    if getattr(sys, 'frozen', False):
        exe_path = f'"{sys.executable}"'
    else:
        main_script = (INSTALL_DIR / "main.py").resolve()
        exe_path = f'"{sys.executable}" "{main_script}"'
        
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            logging.info("AURA ajouté au démarrage de Windows.")
        else:
            try:
                winreg.DeleteValue(key, app_name)
                logging.info("AURA retiré du démarrage de Windows.")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        logging.error(f"Erreur configuration autostart: {e}")

# ---------------------------------------------------------------------------
# TRADUCTIONS — Système i18n bilingue (fr/en)
# ---------------------------------------------------------------------------

# Chargement des traductions
_translations = _load_json(TRANSLATIONS_FILE, {"fr": {}, "en": {}})


def t(key: str, **kwargs) -> str:
    """
    Récupère une traduction pour la langue active.
    
    Utilisation :
        t("welcome")                       → "Bonjour ! Je suis AURA..."
        t("app_launching", name="Chrome")   → "Lancement de Chrome..."
        t("time_response", time="14h30")    → "Il est actuellement 14h30."
    
    Les {variables} dans le texte sont remplacées par les kwargs.
    Si la clé n'existe pas, retourne la clé elle-même (pour faciliter le debug).
    """
    lang = settings.get("language", "fr")
    lang_dict = _translations.get(lang, _translations.get("fr", {}))
    text = lang_dict.get(key, key)
    
    # Remplacement des variables dans le texte
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):
        return text


def reload_translations() -> None:
    """Recharge les traductions depuis le fichier (utile après modification)."""
    global _translations
    _translations = _load_json(TRANSLATIONS_FILE, {"fr": {}, "en": {}})

# ---------------------------------------------------------------------------
# LOGGING — Configuration centralisée des logs
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    """
    Configure le système de logging.
    - Écrit dans aura.log (fichier)
    - Affiche aussi dans la console (pour le debug)
    - Le niveau est configurable via settings.json
    """
    log_level = getattr(logging, settings.get("log_level", "INFO").upper(), logging.INFO)
    
    logger = logging.getLogger("AURA")
    logger.setLevel(log_level)
    
    # Éviter les doublons si setup_logging est appelé plusieurs fois
    if logger.handlers:
        return logger
    
    # Format des messages de log
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Handler fichier (aura.log)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Handler console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Initialisation du logger dès l'import du module
logger = setup_logging()

# ---------------------------------------------------------------------------
# HISTORIQUE — Sauvegarde des commandes récentes
# ---------------------------------------------------------------------------

def load_history() -> list:
    """Charge l'historique des commandes depuis history.json."""
    data = _load_json(HISTORY_FILE, {"commands": []})
    return data.get("commands", [])


def save_history(commands: list) -> None:
    """Sauvegarde l'historique (limité à history_size entrées)."""
    max_size = settings.get("history_size", 50)
    _save_json(HISTORY_FILE, {"commands": commands[-max_size:]})


def add_to_history(command: str) -> None:
    """Ajoute une commande à l'historique."""
    history = load_history()
    history.append(command)
    save_history(history)
