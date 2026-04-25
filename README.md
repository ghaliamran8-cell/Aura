<p align="center">
  <img src="assets/logo.png" alt="AURA Logo" width="200"/>
</p>

<h1 align="center">✦ AURA</h1>
<p align="center"><strong>Your Intelligent Desktop Companion</strong></p>
<p align="center">
  <em>Assistant IA vocal furtif pour Windows — Inspiré par Siri, conçu pour être libre.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" />
  <img src="https://img.shields.io/badge/AI-Gemini%201.5-8E44AD?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" />
</p>

---

## 🎯 Qu'est-ce qu'AURA ?

AURA est un **assistant intelligent vocal** intégré à Windows. Il fonctionne en arrière-plan, écoute votre voix, et exécute vos commandes naturellement — comme Siri, mais pour votre PC.

### ✨ Fonctionnalités principales

| Fonctionnalité | Description |
|---|---|
| 🎤 **Commande vocale** | Dites "AURA" suivi de votre commande |
| 🚀 **Lancement d'apps** | "Ouvre Chrome", "Lance Discord", "Va sur YouTube" |
| 🔒 **Fermeture sécurisée** | "Ferme Spotify" — bloque les processus système critiques |
| 🌐 **Recherche web** | "Cherche une recette de crêpes" |
| 🌍 **Traduction universelle** | "Traduis bonjour en japonais" — toutes les langues |
| 🧠 **IA conversationnelle** | Questions libres via Google Gemini 1.5 Flash |
| ⌨️ **Mode furtif** | Touche F9 → écoute instantanée sans UI |
| 🎨 **UI personnalisable** | Couleur, taille, forme, position, transparence, police |
| 📡 **Mode offline** | Fonctionne sans Internet (commandes locales + TTS offline) |
| 🔐 **Sécurité renforcée** | Blocklist de commandes dangereuses, sanitisation LLM |

### 🎙️ Compréhension linguistique

- 🇫🇷 Français natif (commandes et réponses)
- 🇬🇧 Anglais natif
- 🌐 Mélange FR/EN compris automatiquement
- 🌍 Traduction vers/depuis n'importe quelle langue

---

## 🚀 Installation

### Prérequis
- Python 3.10+
- Windows 10/11
- Microphone (optionnel mais recommandé)

### Étapes

```bash
# 1. Cloner le repo
git clone https://github.com/ghaliamran8-cell/Aura.git
cd Aura

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer AURA
python main.py
```

### 🔑 Configuration de l'IA

1. Au premier lancement, AURA vous demandera une **clé API Gemini** (gratuite)
2. Allez sur [Google AI Studio](https://aistudio.google.com/app/apikey)
3. Créez une clé → collez-la dans les paramètres AURA

---

## ⌨️ Raccourcis clavier

| Raccourci | Action |
|---|---|
| `F9` | Mode furtif (écoute vocale instantanée) |
| `Ctrl+Espace+A` | Ouvrir/fermer la barre de recherche |
| `Ctrl+Espace+S` | Ouvrir les paramètres |

---

## 🏗️ Compiler en .exe

Pour partager AURA sans installer Python :

```bash
python build.py
```

L'exécutable sera dans `dist/AURA/`. Zippez le dossier et envoyez-le !

> ⚠️ Ne partagez pas votre `settings.json` — chacun doit avoir sa propre clé API.

---

## 📁 Architecture

```
AURA/
├── main.py          # Point d'entrée
├── config.py        # Configuration & i18n
├── ui.py            # Interface Siri-inspired
├── settings_ui.py   # Panneau de paramètres
├── commands.py      # Exécution des commandes
├── scanner.py       # Scan & recherche d'apps
├── voice.py         # TTS neuronal + STT
├── llm_brain.py     # Cerveau IA (Gemini)
├── translations.json
├── requirements.txt
├── build.py         # Compilateur .exe
└── assets/
    ├── logo.png
    ├── icon.png
    └── background.png
```

---

## 🛡️ Sécurité

AURA est conçu pour être **sûr** :
- ❌ Ne peut pas supprimer de fichiers
- ❌ Ne peut pas modifier le registre Windows
- ❌ Ne peut pas fermer les processus système (explorer, svchost, etc.)
- ❌ Les réponses IA sont nettoyées de toute commande dangereuse
- ❌ Pas d'exécution de scripts externes
- ✅ Toutes les données restent locales (AppData)
- ✅ Clé API stockée localement uniquement

---

## 📝 Licence

MIT — Libre d'utilisation, modification et distribution.

---

<p align="center">
  <strong>✦ AURA V3.1</strong> — Fait avec ❤️ 
</p>
