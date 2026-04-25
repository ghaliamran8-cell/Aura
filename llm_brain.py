# =============================================================================
# llm_brain.py — Cerveau Intelligent d'AURA V3 (Google Gemini)
# =============================================================================
# Ce module permet à AURA de comprendre n'importe quelle commande
# ("Ferme Youtube", "Ouvre la corbeille", "C'est quoi un trou noir")
# en utilisant Google Gemini 1.5 Flash.
# Inclut : parsing multilingue, traduction multi-langue, sécurité LLM.
# =============================================================================

import json
import re
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

# --- SÉCURITÉ LLM ---
SAFETY_INSTRUCTIONS = """
RÈGLES DE SÉCURITÉ ABSOLUES :
- Tu ne dois JAMAIS suggérer de commandes qui suppriment des fichiers (del, rm, rmdir)
- Tu ne dois JAMAIS suggérer de modifier le registre Windows (reg add, reg delete)
- Tu ne dois JAMAIS suggérer de désactiver le pare-feu, l'antivirus ou la sécurité
- Tu ne dois JAMAIS donner de commandes qui formatent des disques
- Tu ne dois JAMAIS encourager l'exécution de scripts téléchargés d'internet
- Tu ne dois JAMAIS fournir de malware, virus, ou code malveillant
- Tu ne dois JAMAIS exécuter de commandes PowerShell encodées ou obfusquées
- Tu ne dois JAMAIS modifier les fichiers de démarrage du système (boot, MBR, GPT)
- En cas de doute sur la sécurité d'une action, REFUSE poliment.
"""

# Patterns dangereux à bloquer dans les réponses LLM
_DANGEROUS_PATTERNS = [
    r'(?i)del\s+/[sfq]',
    r'(?i)rmdir\s+/s',
    r'(?i)format\s+[a-z]:',
    r'(?i)reg\s+delete',
    r'(?i)reg\s+add',
    r'(?i)powershell\s+-e\w*\s+',
    r'(?i)powershell\s+-enc',
    r'(?i)cmd\s+/c\s+del',
    r'(?i)cmd\s+/c\s+format',
    r'(?i)rm\s+-rf',
    r'(?i)mkfs\.',
    r'(?i)dd\s+if=',
    r'(?i)bcdedit',
    r'(?i)diskpart',
    r'(?i)cipher\s+/w',
    r'(?i)net\s+stop\s+',
    r'(?i)sc\s+delete\s+',
    r'(?i)wmic\s+.*delete',
]

def _sanitize_llm_response(text: str) -> str:
    """Nettoie les réponses LLM pour enlever du contenu potentiellement dangereux."""
    for pattern in _DANGEROUS_PATTERNS:
        text = re.sub(pattern, '[commande bloquée pour sécurité]', text)
    return text


def parse_with_llm(user_input: str) -> dict:
    """
    Analyse l'intention de l'utilisateur. Retourne un dictionnaire strict :
    {"intent": "SYSTEM_OPEN"|"SYSTEM_CLOSE"|"WEB_SEARCH"|"ASK_AI"|"TRANSLATE"|"UNKNOWN", "target": "chrome"}
    
    Supporte le français, l'anglais et les langues mixtes.
    """
    if not _is_configured and not _configure_gemini():
        return {"intent": "NO_API_KEY", "target": None}
        
    prompt = f"""
    Tu es le cerveau d'un ordinateur. L'utilisateur te donne un ordre vocal : "{user_input}".
    L'utilisateur peut parler en FRANÇAIS, ANGLAIS ou MÉLANGER les deux langues.
    
    {SAFETY_INSTRUCTIONS}
    
    Catégorise strictement cet ordre dans l'une des intentions suivantes :
    1. "SYSTEM_OPEN" : Ouvre une application locale ou lance un site (ex: "ouvre chrome", "lance un jeu", "va sur youtube", "open spotify", "start discord").
    2. "SYSTEM_CLOSE" : Arrête ou ferme une application logicielle (ex: "ferme discord", "tue le jeu", "close chrome", "kill the game"). Attention: on ne peut pas fermer "youtube" si on ne dit pas de fermer le navigateur entier. Si l'utilisateur demande de fermer un site web, l'intention est "WEB_CLOSE_ERROR".
    3. "WEB_SEARCH" : Recherche d'une information simple sur internet (ex: "cherche une recette", "comment faire x", "search for python tutorials").
    4. "TRANSLATE" : Demande de traduction (ex: "traduis bonjour en anglais", "translate hello in french", "comment on dit chat en espagnol", "dis-moi comment dire merci en japonais").
    5. "ASK_AI" : Question générale, discussion, explication complexe (ex: "c'est quoi un trou noir", "écris moi un code python", "bonjour tu vas bien", "what is quantum physics").
    6. "UNKNOWN" : Si incompréhensible.
    
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
        "Sois professionnelle mais chaleureuse. "
        "Tu comprends le français, l'anglais, l'espagnol, l'arabe, l'allemand, le japonais, "
        "le chinois, le portugais, l'italien, le russe et toutes les autres langues. "
        "Réponds TOUJOURS dans la langue dans laquelle l'utilisateur te parle. "
        f"\n{SAFETY_INSTRUCTIONS}"
    )
    
    try:
        response = _model_chat.generate_content(system_instruction + "\n\nQuestion: " + user_input)
        cleaned_text = response.text.replace("*", "").replace("#", "")
        cleaned_text = _sanitize_llm_response(cleaned_text)
        
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

def translate_with_llm(user_input: str) -> str:
    """
    Traduit du texte via Gemini.
    Détecte automatiquement la langue source et traduit vers la langue cible.
    Supporte TOUTES les langues (pas seulement FR/EN).
    
    Exemples :
        "bonjour en anglais" → "hello"
        "hello in french" → "bonjour"
        "chat en espagnol" → "gato"
        "merci en japonais" → "ありがとう (arigatō)"
        "I love you en arabe" → "أحبك (uhibbuk)"
    """
    if not _is_configured and not _configure_gemini():
        vocal_error = "Je n'ai pas de clé API pour traduire."
        speak(vocal_error)
        return vocal_error
    
    system_instruction = (
        "Tu es un traducteur expert multilingue professionnel. "
        "Tu maîtrises TOUTES les langues du monde : français, anglais, espagnol, arabe, "
        "allemand, italien, portugais, russe, japonais, chinois (mandarin), coréen, "
        "hindi, turc, néerlandais, polonais, suédois, et toute autre langue. "
        "L'utilisateur va te donner un texte à traduire. "
        "Détecte automatiquement la langue source et la langue cible demandée. "
        "Si aucune langue cible n'est précisée, traduis vers l'anglais si le texte est en français, "
        "ou vers le français si le texte est en anglais, ou vers le français par défaut. "
        "Réponds uniquement avec la traduction, suivie d'une courte explication entre parenthèses. "
        "Si la langue cible utilise un alphabet non-latin, ajoute la translittération. "
        "Exemple : 'Hello (anglais → français : Bonjour)' "
        "Exemple : 'ありがとう / arigatō (français → japonais : Merci)'"
    )
    
    try:
        response = _model_chat.generate_content(system_instruction + "\n\nTexte à traduire : " + user_input)
        result = response.text.replace("*", "").replace("#", "")
        result = _sanitize_llm_response(result)
        speak(result)
        return result
    except Exception as e:
        logger.error(f"Erreur LLM Translate : {e}")
        err = "Désolé, je n'ai pas pu traduire."
        speak(err)
        return err

def needs_api_key_vocal_alert():
    """Prévient l'utilisateur via edge_tts qu'il faut une clé API."""
    speak("Pour activer toutes mes capacités, merci de configurer la clé API dans les paramètres.")
