# =============================================================================
# scanner.py — Module de Scan de Disque Intelligent
# =============================================================================
# Ce module gère :
# - Le scan rapide des dossiers standards (Program Files, Bureau, Menu Démarrer)
# - Le scan profond de tous les disques
# - La résolution des raccourcis Windows (.lnk)
# - L'indexation des applications dans index.json
# - Le compteur de fréquence d'utilisation pour trier les résultats
# - Cache mémoire + rapidfuzz pour une recherche ultra-rapide
# =============================================================================

import os
import json
import threading
import time
from pathlib import Path
from config import INDEX_FILE, settings, logger

# ---------------------------------------------------------------------------
# RAPIDFUZZ — Recherche fuzzy ultra-rapide (remplace difflib)
# ---------------------------------------------------------------------------

try:
    from rapidfuzz import fuzz, process as rfprocess
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    from difflib import SequenceMatcher
    logger.warning("rapidfuzz non installé — fallback sur difflib (plus lent).")

# ---------------------------------------------------------------------------
# RÉSOLUTION DES RACCOURCIS .LNK (Windows)
# ---------------------------------------------------------------------------
# On utilise win32com pour lire la cible réelle d'un raccourci .lnk
# Si pywin32 n'est pas installé, on ignore simplement les .lnk

try:
    import win32com.client
    _SHELL = win32com.client.Dispatch("WScript.Shell")
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    logger.warning("pywin32 non installé — les raccourcis .lnk seront ignorés.")


def _resolve_lnk(lnk_path: str) -> str | None:
    """
    Résout un fichier .lnk vers le chemin réel de l'exécutable.
    Retourne None si le raccourci est invalide ou ne pointe pas vers un .exe.
    """
    if not HAS_WIN32:
        return None
    try:
        shortcut = _SHELL.CreateShortcut(str(lnk_path))
        target = shortcut.TargetPath
        if target and target.lower().endswith(".exe"):
            return target
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# DOSSIERS STANDARDS À SCANNER
# ---------------------------------------------------------------------------

# Dossiers système critiques à NE JAMAIS modifier/exécuter
DANGEROUS_PATHS = {
    os.path.normcase(p) for p in [
        "C:\\Windows\\System32",
        "C:\\Windows\\SysWOW64",
        "C:\\Windows\\security",
        "C:\\Windows\\servicing",
        "C:\\Windows\\WinSxS",
        "C:\\Windows\\Installer",
        "C:\\Windows\\Temp",
        "C:\\$Recycle.Bin",
        "C:\\Recovery",
        "C:\\System Volume Information",
    ]
}

def _is_safe_path(path: str) -> bool:
    """Vérifie qu'un chemin n'est pas dans une zone système critique."""
    norm = os.path.normcase(path)
    for dangerous in DANGEROUS_PATHS:
        if norm.startswith(dangerous):
            return False
    # Extra safety: reject paths with suspicious characters
    if ".." in path or "\0" in path:
        return False
    return True


def _get_standard_directories() -> list[str]:
    """
    Retourne la liste des dossiers standards à scanner.
    Combine les dossiers configurés par l'utilisateur + les dossiers système.
    """
    dirs = list(settings.get("scan_directories", []))
    
    # Bureau de l'utilisateur
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        dirs.append(str(desktop))
    
    # Bureau public (commun à tous les utilisateurs)
    public_desktop = Path("C:/Users/Public/Desktop")
    if public_desktop.exists():
        dirs.append(str(public_desktop))
    
    # Menu Démarrer (utilisateur)
    start_menu_user = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    if start_menu_user.exists():
        dirs.append(str(start_menu_user))
    
    # Menu Démarrer (système)
    start_menu_system = Path("C:/ProgramData/Microsoft/Windows/Start Menu/Programs")
    if start_menu_system.exists():
        dirs.append(str(start_menu_system))
        
    # Applications Modernes (Local AppData) -> Spotify, WhatsApp, VS Code, Discord...
    local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
    
    win_apps = local_appdata / "Microsoft" / "WindowsApps"
    if win_apps.exists():
        dirs.append(str(win_apps))
        
    local_programs = local_appdata / "Programs"
    if local_programs.exists():
        dirs.append(str(local_programs))
        
    return dirs

# ---------------------------------------------------------------------------
# MOTEUR DE SCAN
# ---------------------------------------------------------------------------

def _scan_directory(directory: str, results: dict, max_depth: int = 4) -> None:
    """
    Parcourt récursivement un dossier pour trouver les .exe et .lnk.
    
    - max_depth : limite la profondeur de récursion pour la performance
    - results : dictionnaire {nom_affiché: chemin_exe} mis à jour en place
    """
    try:
        for root, dirs, files in os.walk(directory):
            # Calcul de la profondeur actuelle
            depth = root.replace(directory, "").count(os.sep)
            if depth >= max_depth:
                dirs.clear()  # Ne pas descendre plus profond
                continue
            
            # Ignorer les dossiers système/cachés courants
            dirs[:] = [d for d in dirs if not d.startswith(('.', '$', '_'))
                       and d.lower() not in ('cache', 'temp', 'logs', '__pycache__',
                                             'node_modules', '.git', 'backup', 'old')]
            
            for filename in files:
                filepath = os.path.join(root, filename)
                name_lower = filename.lower()
                
                # Sécurité : ignorer les fichiers dans des zones dangereuses
                if not _is_safe_path(filepath):
                    continue
                
                if name_lower.endswith(".exe"):
                    # Ignorer les utilitaires systèmes communs (uninstallers, etc.)
                    skip_keywords = ["unins", "update", "setup", "install", "crash",
                                     "helper", "service", "daemon", "updater",
                                     "repair", "diagnostic", "migrate", "redist"]
                    base = os.path.splitext(filename)[0].lower()
                    if any(kw in base for kw in skip_keywords):
                        continue
                    
                    # Vérifier que le fichier existe vraiment (pas un lien mort)
                    if not os.path.isfile(filepath):
                        continue
                    
                    # Nom affiché = nom du fichier sans extension, nettoyé
                    display_name = os.path.splitext(filename)[0]
                    results[display_name] = filepath
                
                elif name_lower.endswith(".lnk"):
                    # Résolution du raccourci
                    target = _resolve_lnk(filepath)
                    if target and os.path.isfile(target):
                        display_name = os.path.splitext(filename)[0]
                        results[display_name] = target
                        
    except PermissionError:
        pass  # Ignorer les dossiers sans permission d'accès
    except Exception as e:
        logger.warning(f"Erreur lors du scan de {directory}: {e}")

# ---------------------------------------------------------------------------
# SCAN RAPIDE vs SCAN PROFOND
# ---------------------------------------------------------------------------

def quick_scan() -> dict:
    """
    Scan rapide : parcourt uniquement les dossiers standards.
    Retourne un dictionnaire {nom: chemin_exe}.
    """
    logger.info("Démarrage du scan rapide...")
    results = {}
    
    for directory in _get_standard_directories():
        if os.path.isdir(directory):
            _scan_directory(directory, results)
    
    logger.info(f"Scan rapide terminé : {len(results)} applications trouvées.")
    return results


def deep_scan() -> dict:
    """
    Scan profond : parcourt TOUS les disques définis dans settings.json.
    Plus lent mais exhaustif. Déclenché par "Scan profond" / "Si, je l'ai".
    """
    logger.info("Démarrage du scan profond...")
    results = {}
    
    # D'abord les dossiers standards
    for directory in _get_standard_directories():
        if os.path.isdir(directory):
            _scan_directory(directory, results)
    
    # Puis tous les disques configurés
    drives = settings.get("deep_scan_drives", ["C:\\"])
    for drive in drives:
        if os.path.exists(drive):
            logger.info(f"Scan du disque {drive}...")
            _scan_directory(drive, results, max_depth=6)
    
    logger.info(f"Scan profond terminé : {len(results)} applications trouvées.")
    return results

# ---------------------------------------------------------------------------
# INDEX — Stockage, Chargement et CACHE MÉMOIRE
# ---------------------------------------------------------------------------

# Cache mémoire global — évite de relire index.json à chaque frappe clavier
_index_cache = None
_index_cache_lock = threading.Lock()
# Noms pré-calculés en minuscules pour la recherche
_search_names_lower = {}
# Noms tokenisés pour recherche rapide par mots-clés
_search_tokens = {}


def _load_index() -> dict:
    """Charge l'index depuis index.json."""
    try:
        if INDEX_FILE.exists():
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {"apps": {}, "usage_count": {}, "last_scan": None, "scan_type": None}


def _save_index(data: dict) -> None:
    """Sauvegarde l'index dans index.json."""
    try:
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Impossible de sauvegarder l'index : {e}")


def _refresh_cache(data: dict) -> None:
    """Met à jour le cache mémoire et les noms pré-calculés."""
    global _index_cache, _search_names_lower, _search_tokens
    with _index_cache_lock:
        _index_cache = data
        _search_names_lower = {name: name.lower() for name in data.get("apps", {})}
        # Pré-tokeniser les noms pour recherche par mots-clés
        _search_tokens = {}
        for name in data.get("apps", {}):
            # Tokenize: split on spaces, hyphens, underscores, dots
            import re
            tokens = set(re.split(r'[\s\-_\.]+', name.lower()))
            _search_tokens[name] = tokens


def get_index() -> dict:
    """
    Retourne l'index courant des applications (depuis le cache si possible).
    Si l'index n'existe pas, lance un scan rapide automatiquement.
    """
    global _index_cache
    
    with _index_cache_lock:
        if _index_cache is not None:
            return _index_cache
    
    index = _load_index()
    if not index.get("apps"):
        # Premier lancement : scan rapide automatique
        apps = quick_scan()
        index = {
            "apps": apps,
            "usage_count": {},
            "last_scan": time.strftime("%Y-%m-%d %H:%M:%S"),
            "scan_type": "quick"
        }
        _save_index(index)
    
    _refresh_cache(index)
    return index


def update_index(scan_type: str = "quick") -> dict:
    """
    Met à jour l'index avec un nouveau scan.
    Préserve les compteurs d'utilisation.
    """
    old_index = _load_index()
    usage_count = old_index.get("usage_count", {})
    
    if scan_type == "deep":
        apps = deep_scan()
    else:
        apps = quick_scan()
    
    new_index = {
        "apps": apps,
        "usage_count": usage_count,
        "last_scan": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scan_type": scan_type
    }
    _save_index(new_index)
    _refresh_cache(new_index)
    return new_index


def increment_usage(app_name: str) -> None:
    """Incrémente le compteur d'utilisation d'une application."""
    index = get_index()
    usage = index.get("usage_count", {})
    usage[app_name] = usage.get(app_name, 0) + 1
    index["usage_count"] = usage
    _save_index(index)
    _refresh_cache(index)

# ---------------------------------------------------------------------------
# RECHERCHE — Fuzzy Search ultra-rapide (rapidfuzz ou fallback difflib)
# ---------------------------------------------------------------------------

def search_apps(query: str, max_results: int = None) -> list[tuple[str, str, float]]:
    """
    Recherche une application par nom (fuzzy match ultra-rapide).
    
    Retourne une liste de tuples (nom, chemin, score) triée par pertinence.
    Le score combine la similarité textuelle ET la fréquence d'utilisation.
    
    Paramètres :
        query       : texte recherché par l'utilisateur
        max_results : nombre max de résultats (défaut: settings.max_suggestions)
    """
    if max_results is None:
        max_results = settings.get("max_suggestions", 8)
    
    index = get_index()
    apps = index.get("apps", {})
    usage = index.get("usage_count", {})
    query_lower = query.lower().strip()
    
    if not query_lower:
        return []
    
    scored = []
    
    # Pré-tokeniser la requête pour matching par mots-clés
    import re as _re
    query_tokens = set(_re.split(r'[\s\-_\.]+', query_lower))
    
    if HAS_RAPIDFUZZ:
        # --- RAPIDFUZZ BATCH MODE (ultra-rapide) ---
        # Utiliser process.extract pour scorer tout d'un coup
        app_names = list(apps.keys())
        if not app_names:
            return []
        
        # Rapidfuzz batch extraction — beaucoup plus rapide que boucle individuelle
        batch_results = rfprocess.extract(
            query_lower,
            {name: _search_names_lower.get(name, name.lower()) for name in app_names},
            scorer=fuzz.WRatio,
            limit=max_results * 3,  # Prendre plus pour pouvoir re-trier
            score_cutoff=35
        )
        
        for name_lower, rf_score, key in batch_results:
            name = key
            path = apps[name]
            text_score = rf_score / 100.0
            
            # Bonus pour correspondance exacte ou préfixe
            nl = _search_names_lower.get(name, name.lower())
            if nl == query_lower:
                text_score = 1.0
            elif nl.startswith(query_lower):
                text_score = max(text_score, 0.92)
            elif query_lower in nl:
                text_score = max(text_score, 0.72)
            
            # Bonus token match (si un mot-clé de la requête correspond exactement)
            name_tokens = _search_tokens.get(name, set())
            token_matches = query_tokens & name_tokens
            if token_matches:
                text_score = max(text_score, 0.7 + 0.1 * len(token_matches))
            
            # Bonus de fréquence d'utilisation
            use_count = usage.get(name, 0)
            freq_bonus = min(use_count * 0.02, 0.15)
            
            final_score = text_score + freq_bonus
            scored.append((name, path, final_score))
    else:
        # --- FALLBACK difflib (plus lent) ---
        for name, path in apps.items():
            name_lower = _search_names_lower.get(name, name.lower())
            
            if name_lower == query_lower:
                text_score = 1.0
            elif name_lower.startswith(query_lower):
                text_score = 0.9
            elif query_lower in name_lower:
                text_score = 0.7
            else:
                text_score = SequenceMatcher(None, query_lower, name_lower).ratio()
            
            if text_score < 0.35:
                continue
            
            use_count = usage.get(name, 0)
            freq_bonus = min(use_count * 0.02, 0.15)
            
            final_score = text_score + freq_bonus
            scored.append((name, path, final_score))
    
    # Tri par score décroissant
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:max_results]

# ---------------------------------------------------------------------------
# SCAN EN ARRIÈRE-PLAN (Thread)
# ---------------------------------------------------------------------------

# Callback appelé quand un scan se termine (pour notifier l'UI)
_scan_callback = None
_scan_thread = None


def set_scan_callback(callback) -> None:
    """Définit la fonction à appeler quand un scan se termine."""
    global _scan_callback
    _scan_callback = callback


def is_scanning() -> bool:
    """Retourne True si un scan est en cours."""
    return _scan_thread is not None and _scan_thread.is_alive()


def start_scan_async(scan_type: str = "quick") -> None:
    """
    Lance un scan en arrière-plan (ne bloque pas l'UI).
    Le callback est appelé avec le résultat quand c'est terminé.
    """
    global _scan_thread
    
    if is_scanning():
        logger.info("Un scan est déjà en cours, requête ignorée.")
        return
    
    def _run():
        result = update_index(scan_type)
        if _scan_callback:
            _scan_callback(result, scan_type)
    
    _scan_thread = threading.Thread(target=_run, daemon=True)
    _scan_thread.start()
    logger.info(f"Scan {scan_type} lancé en arrière-plan.")
