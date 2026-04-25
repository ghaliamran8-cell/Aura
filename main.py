# =============================================================================
# main.py — Point d'entrée d'AURA V3.1 (Furtif & Intelligent)
# =============================================================================
# V3.1: UI Siri-inspired, personnalisation complète, sécurité renforcée,
# traduction multi-langue, mode offline, admin access.
# =============================================================================

import sys
import threading
import time
from config import settings, t, logger
import traceback

def main():
    logger.info("=" * 50)
    logger.info("AURA V3.1 — Mode Discret & IA")
    logger.info("=" * 50)
    
    # ------------------------------------------------------------------
    # IMPORTS DIFFÉRÉS (pour UI fluide)
    # ------------------------------------------------------------------
    from scanner import get_index, start_scan_async
    from voice import (speak_key, speak, is_microphone_available, play_beep,
                       start_continuous_listening, set_command_callback, listen)
    from commands import execute_command, set_settings_callback
    from ui import AuraMainApp
    from settings_ui import open_settings
    import llm_brain
    
    # Init cerveau IA
    llm_brain._configure_gemini()
    
    # Scan index
    if len(get_index().get("apps", {})) == 0:
        start_scan_async("quick")
    
    has_mic = is_microphone_available()
    if not has_mic:
        logger.warning("Aucun microphone — AURA ne pourra pas vous entendre.")
    
    # ------------------------------------------------------------------
    # CALLBACKS VOCAL & CLAVIER
    # ------------------------------------------------------------------
    
    app = AuraMainApp()
    
    def on_voice_command(command_text: str):
        """Reçu du listener continu 'AURA'."""
        _execute_async(command_text)
    
    def _execute_async(text: str):
        def _run():
            try:
                execute_command(text)
            except Exception as e:
                logger.error(f"Erreur d'exécution: {traceback.format_exc()}")
        threading.Thread(target=_run, daemon=True).start()
    
    set_command_callback(on_voice_command)
    set_settings_callback(lambda: app.root.after(0, lambda: open_settings(app.root)))
    
    # --- HOTKEYS ---
    stealth_key = settings.get("stealth_hotkey", "f9")
    ui_key = "ctrl+space+a"
    settings_key = "ctrl+space+s"
    try:
        import keyboard
        _stealth_lock = threading.Lock()
        _current_stealth_key = stealth_key
        
        def _on_stealth_hotkey():
            if not _stealth_lock.acquire(blocking=False):
                return
            logger.info("Stealth Hotkey activée.")
            def _hk_listen():
                try:
                    play_beep()
                    txt = listen(timeout=5, phrase_time_limit=12)
                    if txt:
                        _execute_async(txt)
                except Exception as e:
                    logger.error(f"Erreur hotkey listen: {e}")
                finally:
                    _stealth_lock.release()
            threading.Thread(target=_hk_listen, daemon=True).start()
            
        def _on_ui_hotkey():
            logger.info("UI Hotkey activée.")
            app.root.after(0, app.toggle)
            
        def _on_settings_hotkey():
            logger.info("Settings Hotkey activée.")
            app.root.after(0, lambda: open_settings(app.root))
        
        def update_stealth_hotkey():
            """Re-register le hotkey furtif après changement dans les settings."""
            nonlocal _current_stealth_key
            new_key = settings.get("stealth_hotkey", "f9")
            if new_key and new_key != _current_stealth_key:
                try:
                    keyboard.remove_hotkey(_current_stealth_key)
                except:
                    pass
                keyboard.add_hotkey(new_key, _on_stealth_hotkey, suppress=True)
                _current_stealth_key = new_key
                logger.info(f"Stealth hotkey mise à jour: {new_key}")
            # Reconfigurer Gemini si la clé API a changé
            llm_brain._configure_gemini()
        
        def reload_theme():
            """Recharge le thème UI après changement dans les settings."""
            try:
                app.reload_theme()
                logger.info("Thème UI rechargé.")
            except Exception as e:
                logger.warning(f"Erreur rechargement thème: {e}")
        
        # Rendre accessible depuis settings_ui
        import builtins
        builtins._aura_update_stealth_hotkey = update_stealth_hotkey
        builtins._aura_reload_theme = reload_theme
        
        keyboard.add_hotkey(stealth_key, _on_stealth_hotkey, suppress=True)
        keyboard.add_hotkey(ui_key, _on_ui_hotkey, suppress=True)
        keyboard.add_hotkey(settings_key, _on_settings_hotkey, suppress=True)
        logger.info(f"Hotkeys prêtes: furtif({stealth_key}), UI({ui_key}), config({settings_key})")
    except Exception as e:
        logger.warning(f"Impossible d'attacher les hotkeys : {e}")

    # ------------------------------------------------------------------
    # DEMARRAGE
    # ------------------------------------------------------------------
    
    if has_mic:
        def _start_listening():
            time.sleep(1)
            start_continuous_listening()
            # Mode V3 : AURA ne parle au démarrage QUE si l'API n'est pas configurée
            # ou au tout premier lancement.
            if not settings.get("gemini_api_key"):
                time.sleep(1)
                speak("Bienvenue dans la version 3. Pour commencer à réfléchir, j'ai besoin de ma clé cerveau. Je vous ouvre les paramètres.")
                open_settings()
        
        threading.Thread(target=_start_listening, daemon=True).start()
    
    # Lancement UI discrète
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Arrêt demandé.")
    finally:
        try:
            from voice import stop_continuous_listening, stop_tts
            stop_continuous_listening()
            stop_tts()
            keyboard.unhook_all()
        except: pass
        logger.info("AURA V3.1 éteint.")


if __name__ == "__main__":
    main()
