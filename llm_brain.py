# =============================================================================
# llm_brain.py — Cerveau Intelligent d'AURA V3 (Google Gemini)
# =============================================================================
# Ce module permet à AURA de comprendre n'importe quelle commande
# ("Ferme Youtube", "Ouvre la corbeille", "C'est quoi un trou noir")
# en utilisant Google Gemini 1.5 Flash.
# =============================================================================

import json
from config import settings, t, logger
from voice import speak

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    logger.warning("google-generativeai non installé.")

# Initialisation différée (attend que la clé API soit configurée via l'UI)
_is_configured = False
_model_json = None
_model_chat = None

def _configure_gemini():
    """Configure Gemini si la clé API est présente."""
    global _is_configured, _model_json, _model_chat
    
    api_key = settings.get("gemini_api_key", "").strip()
    if not HAS_GEMINI or not api_key:
        _is_configured = False
        return False
        
    try:
        genai.configure(api_key=api_key)
        
        # Modèle 1 : Pour l'analyse syntaxique (JSON)
        _model_json = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Modèle 2 : Pour la discussion et la recherche d'informations (Text)
        _model_chat = genai.GenerativeModel('gemini-1.5-flash')
        
        _is_configured = True
        return True
    except Exception as e:
        logger.error(f"Erreur config Gemini : {e}")
        _is_configured = False
        return False

def parse_with_llm(user_input: str) -> dict:
    """
    Analyse l'intention de l'utilisateur. Retourne un dictionnaire strict :
    {"intent": "SYSTEM_OPEN"|"SYSTEM_CLOSE"|"WEB_SEARCH"|"ASK_AI"|"UNKNOWN", "target": "chrome"}
    """
    if not _is_configured and not _configure_gemini():
        return {"intent": "NO_API_KEY", "target": None}
        
    prompt = f"""
    Tu es le cerveau d'un ordinateur. L'utilisateur te donne un ordre vocal : "{user_input}".
    
    Catégorise strictement cet ordre dans l'une des intentions suivantes :
    1. "SYSTEM_OPEN" : Ouvre une application locale ou lance un site (ex: "ouvre chrome", "lance un jeu", "va sur youtube").
    2. "SYSTEM_CLOSE" : Arrête ou ferme une application logicielle (ex: "ferme discord", "tue le jeu"). Attention: on ne peut pas fermer "youtube" si on ne dit pas de fermer le navigateur entier. Si l'utilisateur demande de fermer un site web, l'intention est "WEB_CLOSE_ERROR".
    3. "WEB_SEARCH" : Recherche d'une information simple sur internet (ex: "cherche une recette", "comment faire x").
    4. "ASK_AI" : Question générale, discussion, explication complexe (ex: "c'est quoi un trou noir", "écris moi un code python", "bonjour tu vas bien").
    5. "UNKNOWN" : Si incompréhensible.
    
    Renvoie UNIQUEMENT un JSON valide :
    {{
        "intent": "le_nom_de_lintention",
        "target": "la cible de l'action (le nom du logiciel, du site, ou le sujet de la question)"
    }}
    """
    
    try:
        response = _model_json.generate_content(prompt)
        result = json.loads(response.text)
        logger.info(f"LLM Parse: {result}")
        return result
    except Exception as e:
        logger.error(f"Erreur LLM Parsing : {e}")
        return {"intent": "ERROR", "target": None}

def discuss_with_llm(user_input: str) -> str:
    """Demande à Gemini une explication conversationnelle (Mode Chat/Pro)."""
    if not _is_configured and not _configure_gemini():
        vocal_error = "Je n'ai pas de clé API configurée dans mes paramètres. Veuillez en ajouter une."
        speak(vocal_error)
        return vocal_error
        
    # Le prompt système force des réponses extrêmement concises (idéal pour la voix)
    system_instruction = (
        "Tu es AURA, une assistante IA vocale omnisciente intégrée à Windows. "
        "Tes réponses sont lues à haute voix, tu DOIS donc être courte, concise, sans markdown (*, ** etc), "
        "sauf si on te demande un code (auquel cas tu dis 'voici le code' et tu le mets). "
        "Sois professionnelle mais chaleureuse."
    )
    
    try:
        response = _model_chat.generate_content(system_instruction + "\n\nQuestion: " + user_input)
        cleaned_text = response.text.replace("*", "").replace("#", "")
        # Limite de lecture vocale pour ne pas être interminable
        if len(cleaned_text) > 800:
            speak_text = cleaned_text[:800] + "... Je m'arrête là car la réponse est longue."
        else:
            speak_text = cleaned_text
            
        speak(speak_text)
        return cleaned_text
        
    except Exception as e:
        logger.error(f"Erreur LLM Discuss : {e}")
        err = "Désolé, je suis incapable de me connecter à mon cerveau pour le moment."
        speak(err)
        return err

def needs_api_key_vocal_alert():
    """Prévient l'utilisateur via edge_tts qu'il faut une clé API."""
    speak("Pour activer toutes mes capacités, merci de configurer la clé API dans les paramètres.")
