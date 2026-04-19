# =============================================================================
# build.py — Script de création de l'exécutable autonome (AURA.exe)
# =============================================================================
# Ce script utilise PyInstaller pour compiler l'application de façon à
# ce qu'elle puisse être partagée facilement (ex: clé USB, Discord) sans
# nécessiter l'installation de Python sur l'ordinateur de destination.
# =============================================================================

import sys
import subprocess
import os
import shutil

def build_executable():
    print("=" * 60)
    print("🛠️ LANCEMENT DE LA COMPILATION D'AURA V3 🛠️")
    print("=" * 60)
    
    # Vérification que customtkiner, pygame, pyttsx3 sont trouvables par pyinstaller
    # Normalement pyinstaller s'en sort (surtout avec --collect-all customtkinter)
    
    # 1. Nettoyer les anciens builds
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            print(f"[*] Suppression de l'ancien dossier '{folder}/'...")
            shutil.rmtree(folder)
            
    # 2. Sécurité : on s'assure que settings.json n'est pas inclus en dur dans l'exe 
    # pour que l'ami ait sa propre config ! (PyInstaller ne packagera pas settings.json 
    # par dessus, config.py s'occupe de le créer dans AppData ou dossier local)

    # 3. Lancer PyInstaller
    # --noconfirm : écrase sans faire de pause
    # --noconsole : lance AURA de manière "invisible" sans la boite noire DOS
    # --collect-all customtkinter : crucial pour que l'UI fonctionne dans le .exe
    print("\n[*] Démarrage de Pyinstaller... cela peut prendre quelques minutes.")
    
    try:
        subprocess.run([
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--noconsole",
            "--name=AURA",
            "--collect-all", "customtkinter",
            "--collect-all", "google.generativeai",
            "--hidden-import", "plyer.platforms.win.notification",
            "main.py"
        ], check=True)
        
        print("\n" + "=" * 60)
        print("✅ COMPILATION TERMINÉE AVEC SUCCÈS ✅")
        print("=" * 60)
        print("\nTon application se trouve maintenant dans le dossier :")
        print("-> dist\\AURA\\")
        print("\nComment l'envoyer à un ami ?")
        print("1. Fais un 'Clic-Droit' sur le dossier 'AURA' situé dans 'dist/'.")
        print("2. Fais 'Compresser en fichier ZIP'.")
        print("3. Envoie ce fichier ZIP à ton ami. Il lui suffira de l'extraire et de double-cliquer sur AURA.exe !")
        print("\nNote: Ne lui partage pas ton propre fichier settings.json s'il contient ta clé API,")
        print("chacun doit avoir sa propre clé pour que le service reste gratuit et rapide.\n")

    except subprocess.CalledProcessError as e:
        print("\n❌ Une erreur est survenue lors de la compilation.")
        print(f"Détails : {e}")

if __name__ == "__main__":
    # S'assurer qu'on est au bon endroit
    if not os.path.exists("main.py") or not os.path.exists("config.py"):
        print("Erreur: Ce script doit être exécuté dans le même dossier que main.py")
        sys.exit(1)
        
    build_executable()
