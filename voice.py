# =============================================================================
# voice.py — Module Vocal d'AURA V2 (TTS Neuronal + STT Permanent)
# =============================================================================
# Ce module gère :
# - TTS via edge_tts (voix Microsoft neuronale, très humaine)
# - STT via SpeechRecognition + Google API
# - Mode d'écoute PERMANENTE avec mot-clé "AURA" (wake word)
# - Bip sonore + feedback visuel pour l'écoute
# - Adaptation bilingue FR/EN automatique
# =============================================================================

import threading
import queue
import asyncio
import tempfile
import os
import winsound
from config import settings, t, logger

# ---------------------------------------------------------------------------
# TTS — Synthèse Vocale Neuronale (edge_tts)
# ---------------------------------------------------------------------------
# edge_tts utilise les voix Microsoft Edge (neuronales, très naturelles).
# Pas besoin de clé API — c'est gratuit et la qualité est excellente.
# On génère un fichier audio temporaire puis on le joue avec winsound/PlaySound.

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False
    logger.warning("edge_tts non installé — fallback sur pyttsx3.")

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

# Voix neuronales recommandées (très humaines)
NEURAL_VOICES = {
    "fr": "fr-FR-VivienneMultilingualNeural",   # Voix française féminine naturelle
    "en": "en-US-JennyNeural"                    # Voix anglaise féminine naturelle
}

# File d'attente TTS
_tts_queue = queue.Queue()
_tts_thread = None
_tts_running = False
_tts_lock = threading.Lock()


def _get_neural_voice() -> str:
    """Retourne le nom de la voix neuronale selon la langue."""
    lang = settings.get("language", "fr")
    return NEURAL_VOICES.get(lang, NEURAL_VOICES["fr"])


async def _edge_tts_speak(text: str) -> None:
    """
    Génère l'audio avec edge_tts et le joue.
    Edge_tts produit des voix neuronales Microsoft, quasi-humaines.
    """
    try:
        voice = _get_neural_voice()
        communicate = edge_tts.Communicate(text, voice)
        
        # Fichier temporaire pour l'audio
        temp_file = os.path.join(tempfile.gettempdir(), "aura_tts.mp3")
        await communicate.save(temp_file)
        
        # Jouer le fichier audio avec pygame ou playsound
        _play_audio_file(temp_file)
        
        # Nettoyer
        try:
            os.remove(temp_file)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Erreur edge_tts : {e}")
        # Fallback sur pyttsx3 si edge_tts échoue
        _pyttsx3_speak(text)


def _play_audio_file(filepath: str) -> None:
    """Joue un fichier audio MP3/WAV."""
    try:
        # Utiliser pygame.mixer pour jouer le MP3
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(50)
    except ImportError:
        # Fallback : convertir en WAV et jouer avec winsound (Windows natif)
        try:
            from pydub import AudioSegment
            wav_path = filepath.replace(".mp3", ".wav")
            audio = AudioSegment.from_mp3(filepath)
            audio.export(wav_path, format="wav")
            winsound.PlaySound(wav_path, winsound.SND_FILENAME)
            os.remove(wav_path)
        except ImportError:
            # Dernier fallback : pyttsx3
            logger.warning("Ni pygame ni pydub disponibles — fallback pyttsx3")
            _pyttsx3_speak("...")


def _pyttsx3_speak(text: str) -> None:
    """Fallback TTS avec pyttsx3 (voix robotique mais fiable)."""
    if not HAS_PYTTSX3:
        return
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", settings.get("voice_speed", 180))
        engine.setProperty("volume", settings.get("voice_volume", 0.9))
        
        # Sélection voix FR/EN
        lang = settings.get("language", "fr")
        lang_map = {"fr": ["french", "fr-fr"], "en": ["english", "en-us"]}
        targets = lang_map.get(lang, ["french"])
        
        for voice in engine.getProperty("voices"):
            for target in targets:
                if target in voice.id.lower() or target in voice.name.lower():
                    engine.setProperty("voice", voice.id)
                    break
        
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        logger.error(f"Erreur pyttsx3 : {e}")


def _tts_worker():
    """Thread worker pour la file d'attente TTS."""
    global _tts_running
    _tts_running = True
    
    # Créer une boucle asyncio dédiée pour edge_tts
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while _tts_running:
        try:
            text = _tts_queue.get(timeout=1.0)
            if text is None:
                break
            
            if HAS_EDGE_TTS:
                loop.run_until_complete(_edge_tts_speak(text))
            else:
                _pyttsx3_speak(text)
            
            _tts_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Erreur TTS worker : {e}")
    
    loop.close()
    _tts_running = False


def _ensure_tts_thread():
    """Démarre le thread TTS s'il n'est pas actif."""
    global _tts_thread
    with _tts_lock:
        if _tts_thread is None or not _tts_thread.is_alive():
            _tts_thread = threading.Thread(target=_tts_worker, daemon=True)
            _tts_thread.start()


def speak(text: str) -> None:
    """
    Prononce un texte avec une voix neuronale humaine.
    Asynchrone via file d'attente — ne bloque pas le thread appelant.
    """
    _ensure_tts_thread()
    _tts_queue.put(text)
    logger.debug(f"TTS : {text}")


def speak_key(key: str, **kwargs) -> None:
    """Prononce un texte de traduction. Ex: speak_key('welcome')"""
    text = t(key, **kwargs)
    speak(text)


def stop_tts() -> None:
    """Arrête le thread TTS."""
    global _tts_running
    _tts_running = False
    
    # Vide la file d'attente existante
    with _tts_queue.mutex:
        _tts_queue.queue.clear()
        
    _tts_queue.put(None)

# ---------------------------------------------------------------------------
# STT — Reconnaissance Vocale (SpeechRecognition + Google)
# ---------------------------------------------------------------------------

import speech_recognition as sr

_recognizer = sr.Recognizer()
_recognizer.dynamic_energy_threshold = True
_recognizer.energy_threshold = 250     # Seuil bas pour capter plus de sons
_recognizer.pause_threshold = 0.8      # Moins de pause avant fin de capture
_recognizer.non_speaking_duration = 0.5


def _get_stt_locale() -> str:
    """Retourne le code de langue pour le STT Google."""
    lang = settings.get("language", "fr")
    return {"fr": "fr-FR", "en": "en-US"}.get(lang, "fr-FR")


def play_beep() -> None:
    """Bip court pour signaler l'écoute."""
    try:
        winsound.Beep(1200, 150)
    except Exception:
        pass


def listen(timeout: int = 5, phrase_time_limit: int = 15) -> str | None:
    """
    Écoute unique : capture le micro → texte.
    Note: le bip est joué par l'appelant, pas ici.
    """
    locale = _get_stt_locale()
    logger.info(f"Écoute active ({locale})...")
    
    try:
        with sr.Microphone() as source:
            _recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = _recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_time_limit
            )
        
        # Google STT — essaye de comprendre même si la prononciation est mauvaise
        # show_all=True donne toutes les alternatives possibles
        results = _recognizer.recognize_google(audio, language=locale, show_all=True)
        
        if results and isinstance(results, dict):
            alternatives = results.get("alternative", [])
            if alternatives:
                # Prendre la meilleure transcription
                best = alternatives[0].get("transcript", "")
                confidence = alternatives[0].get("confidence", 0)
                logger.info(f"STT : '{best}' (confiance: {confidence:.0%})")
                return best.lower()
        elif isinstance(results, str):
            return results.lower()
        
        return None
    
    except sr.WaitTimeoutError:
        logger.info("STT : Aucune parole détectée.")
        return None
    except sr.UnknownValueError:
        logger.info("STT : Parole non reconnue.")
        return None
    except sr.RequestError as e:
        logger.error(f"STT : Erreur API — {e}")
        return None
    except OSError as e:
        logger.error(f"STT : Erreur micro — {e}")
        return None


def is_microphone_available() -> bool:
    """Vérifie si un micro est disponible."""
    try:
        with sr.Microphone() as source:
            return True
    except (OSError, AttributeError):
        return False

# ---------------------------------------------------------------------------
# ÉCOUTE PERMANENTE — Mode "Always-On" avec Wake Word "AURA"
# ---------------------------------------------------------------------------
# AURA écoute en permanence en arrière-plan. Quand elle détecte le mot
# "AURA" (ou "aura", "ora", etc.), elle active le mode commande et
# écoute la phrase complète pour l'exécuter.

_continuous_running = False
_continuous_thread = None
_command_callback = None

# Variantes du wake word (pour tolérer les erreurs de reconnaissance)
WAKE_WORDS = [
    "aura", "ora", "aura", "aurora", "or a",
    "hey aura", "ok aura", "dis aura", "salut aura"
]


def set_command_callback(callback) -> None:
    """
    Définit la fonction appelée quand AURA détecte une commande vocale.
    Le callback reçoit le texte de la commande (sans le wake word).
    """
    global _command_callback
    _command_callback = callback


def _extract_command_after_wake_word(text: str) -> str | None:
    """
    Extrait la commande après le mot-clé "AURA" dans le texte.
    Ex: "aura ouvre chrome" → "ouvre chrome"
        "aura quelle heure il est" → "quelle heure il est"
    """
    text_lower = text.lower().strip()
    
    for wake in WAKE_WORDS:
        if text_lower.startswith(wake):
            command = text_lower[len(wake):].strip()
            # Nettoyer les connecteurs courants
            for prefix in [",", ".", "!", "?", " "]:
                command = command.lstrip(prefix)
            if command:
                return command
    
    return None


def _continuous_listen_worker():
    """
    Boucle d'écoute permanente en arrière-plan.
    
    Processus :
    1. Écoute le micro en continu (pas de bip, silencieux)
    2. Transcrit tout ce qu'elle capte
    3. Si le texte contient "AURA" → extrait la commande
    4. Si la commande suit directement "AURA" dans la même phrase → l'exécute
    5. Sinon, joue un bip et attend une commande dédiée
    """
    global _continuous_running
    _continuous_running = True
    locale = _get_stt_locale()
    
    logger.info("Mode écoute permanente activé. Dites 'AURA' pour donner une commande.")
    
    while _continuous_running:
        try:
            with sr.Microphone() as source:
                _recognizer.adjust_for_ambient_noise(source, duration=0.3)
                
                # Écoute passive (timeout long, très patient)
                try:
                    audio = _recognizer.listen(source, timeout=None, phrase_time_limit=12)
                except sr.WaitTimeoutError:
                    continue
            
            # Transcription
            try:
                results = _recognizer.recognize_google(
                    audio, language=locale, show_all=True
                )
                
                text = ""
                if results and isinstance(results, dict):
                    alts = results.get("alternative", [])
                    if alts:
                        text = alts[0].get("transcript", "")
                elif isinstance(results, str):
                    text = results
                
                if not text:
                    continue
                
                text_lower = text.lower().strip()
                logger.debug(f"Écoute passive : '{text_lower}'")
                
                # Vérifie si le wake word est présent
                has_wake_word = any(text_lower.startswith(w) or w in text_lower 
                                   for w in WAKE_WORDS)
                
                if has_wake_word:
                    # Extraire la commande directement après le wake word
                    command = _extract_command_after_wake_word(text)
                    
                    if command:
                        # Commande incluse dans la phrase !
                        # Ex: "Aura ouvre Chrome"
                        logger.info(f"Wake word + commande : '{command}'")
                        play_beep()
                        if _command_callback:
                            _command_callback(command)
                    else:
                        # Juste "Aura" → on attend la suite
                        logger.info("Wake word détecté — en attente de commande...")
                        play_beep()
                        
                        # Écoute dédiée pour la commande
                        follow_up = listen(timeout=5, phrase_time_limit=15)
                        if follow_up and _command_callback:
                            _command_callback(follow_up)
                
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                logger.error(f"Écoute permanente — erreur API : {e}")
                # Pause pour ne pas spam l'API en cas d'erreur
                import time
                time.sleep(3)
                
        except OSError:
            # Micro déconnecté ou problème matériel
            import time
            time.sleep(2)
        except Exception as e:
            logger.error(f"Écoute permanente — erreur : {e}")
            import time
            time.sleep(1)


def start_continuous_listening() -> None:
    """Lance l'écoute permanente en arrière-plan."""
    global _continuous_thread
    
    if _continuous_thread and _continuous_thread.is_alive():
        logger.info("Écoute permanente déjà active.")
        return
    
    if not is_microphone_available():
        logger.warning("Pas de microphone — écoute permanente impossible.")
        return
    
    _continuous_thread = threading.Thread(target=_continuous_listen_worker, daemon=True)
    _continuous_thread.start()
    logger.info("Thread d'écoute permanente démarré.")


def stop_continuous_listening() -> None:
    """Arrête l'écoute permanente."""
    global _continuous_running
    _continuous_running = False
    logger.info("Écoute permanente arrêtée.")
