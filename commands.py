# =============================================================================
# commands.py — Système de Commandes + Cerveau IA d'AURA V3
# =============================================================================
# V3: Intégration de llm_brain pour déchiffrer tout ce que la personne dit.
# Si la commande "classique" échoue, on envoie à Gemini pour comprendre.
# Gère : Ouvre, Ferme (différencie Site vs App), Cherche, Discute,
#         Heure, Système, Traduction, Mode Offline.
# Sécurité : Blocklist de commandes dangereuses, validation des chemins.
# =============================================================================

import os
import re
import subprocess
import time
import socket
import webbrowser
import urllib.parse
from datetime import datetime
from difflib import SequenceMatcher
from config import settings, t, set_setting, add_to_history, logger
from scanner import search_apps, increment_usage, start_scan_async, is_scanning
from voice import speak, speak_key
import llm_brain
from settings_ui import open_settings

# --- COMMANDES DANGEREUSES BLOQUÉES ---
DANGEROUS_COMMANDS = [
    "del ", "rmdir", "rd ", "format ", "reg delete", "reg add",
    "shutdown", "taskkill /im svchost", "taskkill /im csrss",
    "taskkill /im winlogon", "taskkill /im lsass", "taskkill /im services",
    "net stop", "net user", "bcdedit", "diskpart", "cipher /w",
    "powershell -e", "powershell -enc", "cmd /c del", "cmd /c format",
    "rm -rf", "mkfs", "dd if=",
    # Nouvelles protections V3.1
    "wmic", "sc delete", "takeown", "icacls",
    "attrib -s -h", "reg save", "reg restore",
    "vssadmin delete", "wbadmin delete",
    "schtasks /delete", "net localgroup",
    "compact /u", "cipher /e",
]

DANGEROUS_APPS_TO_CLOSE = [
    "explorer", "svchost", "csrss", "winlogon", "lsass",
    "services", "smss", "wininit", "system", "dwm",
    "conhost", "ntoskrnl", "audiodg", "fontdrvhost",
    "registry", "memory compression", "secure system",
]

def _is_dangerous_command(text: str) -> bool:
    """Vérifie si une commande est dangereuse pour le système."""
    text_lower = text.lower().strip()
    if any(cmd in text_lower for cmd in DANGEROUS_COMMANDS):
        return True
    # Vérifier les patterns de traversée de chemin
    if "..\\" in text_lower or "../" in text_lower:
        return True
    # Vérifier les encodages suspects
    if re.search(r'(?i)(base64|encoded|obfuscated)', text_lower):
        return True
    return False

def _is_safe_to_close(app_name: str) -> bool:
    """Vérifie qu'on ne tente pas de fermer un processus système critique."""
    return app_name.lower().strip() not in DANGEROUS_APPS_TO_CLOSE

# --- VÉRIFICATION RÉSEAU ---
_online_cache = None
_online_cache_time = 0

def is_online() -> bool:
    """Vérifie si l'ordinateur a accès à Internet (avec cache de 10s)."""
    global _online_cache, _online_cache_time
    now = time.time()
    if _online_cache is not None and (now - _online_cache_time) < 10:
        return _online_cache
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        _online_cache = True
    except OSError:
        _online_cache = False
    _online_cache_time = now
    return _online_cache

# --- SITES WEB ET NAVIGATEURS CONNUS ---
KNOWN_WEBSITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com",
    "gmail": "https://mail.google.com", "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com", "twitter": "https://twitter.com",
    "x": "https://twitter.com", "reddit": "https://www.reddit.com",
    "twitch": "https://www.twitch.com", "discord": "https://discord.com/app",
    "whatsapp": "https://web.whatsapp.com", "tiktok": "https://www.tiktok.com",
    "netflix": "https://www.netflix.com", "spotify": "https://open.spotify.com",
    "amazon": "https://www.amazon.fr", "wikipedia": "https://fr.wikipedia.org",
    "chatgpt": "https://chat.openai.com", "github": "https://github.com",
    "steam": "https://store.steampowered.com", "epic": "https://store.epicgames.com",
    "linkedin": "https://www.linkedin.com", "pinterest": "https://www.pinterest.com",
    "snapchat": "https://web.snapchat.com", "zoom": "https://zoom.us",
    "notion": "https://www.notion.so", "figma": "https://www.figma.com",
}

KNOWN_BROWSERS = {
    "opera": ["opera.exe", "opera", "opera gx"],
    "chrome": ["chrome.exe", "google chrome"],
    "firefox": ["firefox.exe", "mozilla firefox"],
    "edge": ["msedge.exe", "microsoft edge"],
    "brave": ["brave.exe", "brave"],
}

# --- PATTERNS STANDARDS (Fallback rapide si clair) ---
# Supporte maintenant FRANÇAIS ET ANGLAIS
COMMAND_PATTERNS = {
    "open": {"triggers": ["ouvre", "lance", "démarre", "va sur", "open", "start", "run", "go to", "launch"], "needs_arg": True},
    "close": {"triggers": ["ferme", "kill", "arrête", "quitte", "close", "stop", "quit", "exit app"], "needs_arg": True},
    "search": {"triggers": ["cherche", "recherche", "search", "look up", "find"], "needs_arg": True},
    "translate": {"triggers": ["traduis", "traduit", "traduction", "translate"], "needs_arg": True},
    "time": {"triggers": ["heure", "quelle heure", "time", "what time"], "needs_arg": False},
    "system_info": {"triggers": ["système", "system info", "état du pc", "pc status", "batterie", "battery", "mémoire", "ram", "cpu", "disque", "disk"], "needs_arg": False},
    "help": {"triggers": ["aide", "help", "qu'est-ce que tu sais faire", "what can you do"], "needs_arg": False},
    "settings": {"triggers": ["paramètres", "settings", "options", "configuration", "config"], "needs_arg": False},
    "exit": {"triggers": ["exit", "tais-toi", "dors", "au revoir", "goodbye", "sleep", "shut up"], "needs_arg": False},
}

# --- PARSING & LLM ---
def _fuzzy_match(text: str, trigger: str) -> bool:
    if text.startswith(trigger): return True
    if len(trigger) > 3 and SequenceMatcher(None, text[:len(trigger)+2], trigger).ratio() > 0.75:
        return True
    return False

def parse_command(user_input: str) -> tuple[str, str | None]:
    """Analyse D'ABORD via regex simple, SINON via LLM pour être sûr."""
    text = user_input.strip().lower()
    if not text: return ("unknown", None)
    
    # 0. Sécurité : bloquer les commandes dangereuses
    if _is_dangerous_command(text):
        logger.warning(f"Commande dangereuse bloquée : {text}")
        return ("blocked", text)
    
    # 1. Règles strictes prioritaires (ex: "heure", "paramètres")
    for cmd_name, cmd_info in COMMAND_PATTERNS.items():
        for trigger in sorted(cmd_info["triggers"], key=len, reverse=True):
            if _fuzzy_match(text, trigger):
                arg = text[len(trigger):].strip() if cmd_info["needs_arg"] else None
                # Nettoyage classique
                if arg:
                    for prefix in ["le ", "la ", "l'", "un ", "une ", "sur ", "the ", "a ", "my ", "mon ", "ma ", "mes "]:
                        if arg.startswith(prefix): arg = arg[len(prefix):]
                # Si c'est "ouvre", on vérifie s'il y a un conflit App vs Site
                if cmd_name == "open" and not arg: return ("unknown", text)
                if cmd_name == "close" and not arg: return ("unknown", text)
                
                return (cmd_name, arg)
                
    # 2. Si non reconnu, on utilise le LLM pour déchiffrer TOUT le reste
    # On vérifie si la clé API existe, sinon on passe direct en ChatBot standard
    api_key = settings.get("gemini_api_key", "").strip()
    if api_key and is_online():
        logger.info("Parsing via Gemini intent...")
        try:
            llm_intent = llm_brain.parse_with_llm(text)
            intent = llm_intent.get("intent", "UNKNOWN")
            target = llm_intent.get("target", text)
            
            if intent == "SYSTEM_OPEN": return ("open", target)
            if intent == "SYSTEM_CLOSE": return ("close", target)
            if intent == "WEB_SEARCH": return ("search", target)
            if intent == "ASK_AI": return ("discuss", text) # discussion pro/complexe
            if intent == "WEB_CLOSE_ERROR": return ("close_site_error", target)
            if intent == "TRANSLATE": return ("translate", target)
        except Exception as e:
            logger.error(f"Erreur LLM parsing: {e}")
    
    # 3. Fallback ultime 
    if len(text) > 8: return ("discuss", text)
    return ("unknown", text)

# --- EXECUTION ---
_ui_callback = None
_exit_callback = None
_settings_callback = None

def set_ui_callback(callback): global _ui_callback; _ui_callback = callback
def set_exit_callback(callback): global _exit_callback; _exit_callback = callback
def set_settings_callback(callback): global _settings_callback; _settings_callback = callback
def _notify_ui(text: str):
    if _ui_callback: _ui_callback(text)

def execute_command(user_input: str) -> str | None:
    cmd, arg = parse_command(user_input)
    add_to_history(user_input)
    logger.info(f"Execution -> CMD: {cmd} | ARG: {arg}")
    
    # Sécurité : commande bloquée
    if cmd == "blocked":
        msg = "Cette commande est bloquée pour la sécurité de votre système."
        speak(msg)
        return msg
    
    handlers = {
        "open": lambda: _cmd_open(arg),
        "close": lambda: _cmd_close(arg),
        "close_site_error": lambda: _cmd_close_site_error(arg),
        "search": lambda: _cmd_search(arg),
        "translate": lambda: _cmd_translate(arg),
        "discuss": lambda: _cmd_discuss(arg),
        "time": _cmd_time,
        "system_info": _cmd_system_info,
        "help": _cmd_help,
        "settings": _cmd_settings,
        "exit": _cmd_exit,
    }
    
    handler = handlers.get(cmd)
    if handler: return handler()
    
    # Mode offline: si pas de réseau, informer l'utilisateur au lieu de crash
    if not is_online():
        msg = "Je suis hors-ligne. Je ne peux répondre qu'aux commandes locales (ouvrir, fermer, heure, système)."
        speak(msg)
        return msg
    
    return _cmd_discuss(user_input)

# --- ACTIONS ---
def _cmd_discuss(user_input: str) -> str:
    """Discute comme un être humain (résout requete professionnelle)."""
    if not is_online():
        msg = "Je suis actuellement hors-ligne. Je ne peux répondre qu'aux commandes locales (ouvrir, fermer, heure, système)."
        speak(msg)
        return msg
    
    api = settings.get("gemini_api_key", "").strip()
    if not api:
        llm_brain.needs_api_key_vocal_alert()
        return "Clé API non trouvée. Veuillez aller dans les paramètres."
    
    _notify_ui("AURA réfléchit...")
    try:
        ans = llm_brain.discuss_with_llm(user_input)
        return ans
    except Exception as e:
        logger.error(f"Erreur discussion: {e}")
        msg = "Désolé, une erreur est survenue pendant la réflexion."
        speak(msg)
        return msg

def _cmd_translate(arg: str | None) -> str:
    """Traduit du texte via Gemini. Supporte toutes les langues."""
    if not arg:
        msg = "Que voulez-vous que je traduise ?"
        speak(msg)
        return msg
    
    if not is_online():
        msg = "Je suis hors-ligne, je ne peux pas traduire pour le moment."
        speak(msg)
        return msg
    
    api = settings.get("gemini_api_key", "").strip()
    if not api:
        llm_brain.needs_api_key_vocal_alert()
        return "Clé API non trouvée."
    
    _notify_ui("AURA traduit...")
    try:
        result = llm_brain.translate_with_llm(arg)
        return result
    except Exception as e:
        logger.error(f"Erreur traduction: {e}")
        msg = "Désolé, la traduction a échoué."
        speak(msg)
        return msg

def _cmd_open(arg: str | None) -> str:
    if not arg: return "Rien à ouvrir."
    # 1. Tester s'il force un navigateur "site sur navigateur"
    if " sur " in arg or " on " in arg:
        separator = " sur " if " sur " in arg else " on "
        site_str, nav_str = arg.split(separator, 1)
        for browser, exes in KNOWN_BROWSERS.items():
            if nav_str in browser or nav_str in exes:
                for s, url in KNOWN_WEBSITES.items():
                    if s in site_str:
                        browser_res = search_apps(browser, 1)
                        if browser_res:
                            try:
                                subprocess.Popen([browser_res[0][1], url])
                                speak(f"J'ouvre {s} sur {browser}.")
                                return f"Ouverture {s} sur {browser}"
                            except Exception as e:
                                logger.error(f"Erreur ouverture navigateur: {e}")
    
    # 2. Chercher D'ABORD une application locale (ex: "Spotify" installé physiquement)
    results = search_apps(arg, max_results=2)
    if results and results[0][2] > 0.6:
        best_name, best_path, score = results[0]
        try:
            # Vérifier que le chemin existe avant de lancer
            if not os.path.isfile(best_path):
                logger.warning(f"Chemin introuvable: {best_path}")
            else:
                os.startfile(best_path)
                increment_usage(best_name)
                msg = f"Je lance {best_name}."
                speak(msg)
                return msg
        except OSError as e:
            logger.error(f"Erreur lancement OS: {e}")
            return f"Erreur lancement: {e}"
        except Exception as e:
            logger.error(f"Erreur lancement: {e}")
            return f"Erreur lancement: {e}"
            
    # 3. Si non trouvé en local, est-ce un site connu ? (ex: "Spotify" web)
    for site, url in KNOWN_WEBSITES.items():
        # Utiliser une regex pour chercher le mot exact (évite que "x" match "netflix")
        if re.search(r'\b' + re.escape(site) + r'\b', arg):
            if not is_online():
                msg = f"Je suis hors-ligne et {site} n'est pas installé sur le PC."
                speak(msg)
                return msg
            # Fallback sur Opera s'il est dispo, sinon navigateur par défaut
            browser_res = search_apps("opera", 1)
            if browser_res:
                try:
                    subprocess.Popen([browser_res[0][1], url])
                    speak(f"Je n'ai pas trouvé {site} sur le PC. Je l'ouvre sur Opera.")
                    return f"Site {site} ouvert via Opera."
                except Exception as e:
                    logger.error(f"Erreur ouverture Opera: {e}")
            
            try:
                webbrowser.open(url)
                speak(f"Je n'ai pas trouvé {site} sur le PC. Je l'ouvre dans votre navigateur.")
                return f"Site {site} ouvert."
            except Exception as e:
                logger.error(f"Erreur ouverture navigateur: {e}")
                return f"Erreur: {e}"
            
    # 4. Inconnu local et web, fallback sur le navigateur (recherche Google)
    return _cmd_search(arg)

def _cmd_close(app_name: str | None) -> str:
    if not app_name: return "Quel programme dois-je fermer ?"
    
    # Sécurité: vérifier que ce n'est pas un processus critique
    app_low = app_name.lower().strip()
    
    if not _is_safe_to_close(app_low):
        msg = f"Je ne peux pas fermer {app_name} — c'est un processus système critique."
        speak(msg)
        return msg
    
    # Sécurité: prévenir qu'on ne peut pas fermer un onglet Youtube comme une App
    if app_low in KNOWN_WEBSITES:
        return _cmd_close_site_error(app_name)
        
    results = search_apps(app_low, max_results=3)
    k_exe = []
    
    if results:
        for name, path, score in results:
            exe_name = os.path.basename(path)
            k_exe.append(exe_name)
    
    # Try kill exact and variants
    for exe in k_exe + [f"{app_low}.exe", app_low]:
        try:
            res = subprocess.run(
                ["taskkill", "/IM", exe, "/F"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if res.returncode == 0:
                msg = f"J'ai fermé {app_name}."
                speak(msg)
                return msg
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout lors de la fermeture de {exe}")
        except Exception as e:
            logger.warning(f"Erreur fermeture {exe}: {e}")
        
    msg = f"Impossible de fermer {app_name}. L'application n'est peut-être pas ouverte."
    speak(msg)
    return msg

def _cmd_close_site_error(site: str) -> str:
    speak(f"Je ne peux pas fermer spécifiquement l'onglet {site}. Voulez-vous que je ferme tout le navigateur ?")
    return "Fermeture d'onglet non supportée par le système."

def _cmd_search(query: str | None) -> str:
    """Ouvre une page web pour chercher."""
    if not query: return "Que dois-je chercher ?"
    if not is_online():
        msg = "Je suis hors-ligne, impossible de faire une recherche internet."
        speak(msg)
        return msg
    search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    speak(f"Voici ce que j'ai trouvé sur Internet pour {query}.")
    try:
        webbrowser.open(search_url)
    except Exception as e:
        logger.error(f"Erreur ouverture recherche: {e}")
    return "Recherche effectuée."

def _cmd_settings() -> str:
    speak("J'ouvre vos paramètres AURA.")
    if _settings_callback:
        _settings_callback()
    else:
        try:
            open_settings()
        except Exception as e:
            logger.error(f"Erreur ouverture paramètres: {e}")
    return "Paramètres ouverts."

def _cmd_time() -> str:
    now = datetime.now()
    time_str = now.strftime("%H heures %M") if settings.get("language") == "fr" else now.strftime("%I:%M %p")
    speak(f"Il est actuellement {time_str}.")
    return f"Heure : {time_str}"

def _cmd_system_info() -> str:
    """Affiche les informations système (batterie, CPU, RAM, disque)."""
    import platform
    info_lines = [f"💻 Système : {platform.system()} {platform.release()}"]
    
    try:
        import psutil
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.5)
        info_lines.append(f"⚡ CPU : {cpu_percent}%")
        
        # RAM
        ram = psutil.virtual_memory()
        ram_used = ram.used / (1024**3)
        ram_total = ram.total / (1024**3)
        info_lines.append(f"🧠 RAM : {ram_used:.1f} / {ram_total:.1f} Go ({ram.percent}%)")
        
        # Disque
        disk = psutil.disk_usage("C:\\")
        disk_free = disk.free / (1024**3)
        disk_total = disk.total / (1024**3)
        info_lines.append(f"💾 Disque C: {disk_free:.0f} Go libres sur {disk_total:.0f} Go")
        
        # Batterie
        battery = psutil.sensors_battery()
        if battery:
            plug = "branché" if battery.power_plugged else "sur batterie"
            info_lines.append(f"🔋 Batterie : {battery.percent}% ({plug})")
        
    except ImportError:
        info_lines.append("(Installez psutil pour plus de détails)")
    except Exception as e:
        logger.error(f"Erreur système info: {e}")
        info_lines.append(f"(Erreur: {e})")
    
    result = "\n".join(info_lines)
    # Version vocale simplifiée
    speak_text = f"Voici l'état de votre système. " + ". ".join(info_lines[:3])
    speak(speak_text)
    return result

def _cmd_help() -> str:
    """Affiche la liste des commandes disponibles."""
    help_text = """📋 Commandes AURA :
• "Ouvre [app/site]" — Lance une application ou un site
• "Ferme [app]" — Ferme une application
• "Cherche [sujet]" — Recherche sur Internet
• "Traduis [texte] en [langue]" — Traduit dans n'importe quelle langue
• "Heure" — Annonce l'heure actuelle
• "Système" — Affiche l'état du PC (CPU, RAM, Batterie)
• "Paramètres" — Ouvre les réglages
• "Aide" — Affiche cette aide
• "[Question libre]" — Pose une question à l'IA

💡 Raccourcis : F9 (mode furtif), Ctrl+Espace+A (barre), Ctrl+Espace+S (paramètres)"""
    speak("Voici ce que je peux faire. Ouvrir des applications, fermer des programmes, chercher sur internet, traduire dans n'importe quelle langue, donner l'heure, afficher l'état du PC, et répondre à toutes vos questions.")
    return help_text

def _cmd_exit() -> str:
    speak("Compris, je retourne en veille. Appelez-moi si besoin.")
    if _exit_callback: _exit_callback()
    return "Mise en veille."
