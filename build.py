# =============================================================================
# build.py — Script de création de l'exécutable autonome (AURA.exe)
# =============================================================================
# Ce script utilise PyInstaller pour compiler l'application de façon à
# ce qu'elle puisse être partagée facilement (ex: clé USB, Discord) sans
# nécessiter l'installation de Python sur l'ordinateur de destination.
# V3.1: Ajout admin UAC, icône custom, assets embarqués.
# =============================================================================

import sys
import subprocess
import os
import shutil

def build_executable():
    print("=" * 60)
    print("🛠️ LANCEMENT DE LA COMPILATION D'AURA V3.1 🛠️")
    print("=" * 60)
    
    # 1. Nettoyer les anciens builds
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            print(f"[*] Suppression de l'ancien dossier '{folder}/'...")
            shutil.rmtree(folder)
            
    # 2. Sécurité : on s'assure que settings.json n'est pas inclus en dur dans l'exe 
    # pour que l'ami ait sa propre config ! (PyInstaller ne packagera pas settings.json 
    # par dessus, config.py s'occupe de le créer dans AppData ou dossier local)

    # 3. Détecter l'icône
    icon_path = os.path.join("assets", "icon.png")
    icon_ico = os.path.join("assets", "icon.ico")
    icon_flag = []
    
    if os.path.exists(icon_ico):
        icon_flag = ["--icon", icon_ico]
        print(f"[*] Icône trouvée: {icon_ico}")
    elif os.path.exists(icon_path):
        # Tenter de convertir PNG -> ICO avec Pillow
        try:
            from PIL import Image
            img = Image.open(icon_path)
            img.save(icon_ico, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
            icon_flag = ["--icon", icon_ico]
            print(f"[*] Icône convertie: {icon_path} -> {icon_ico}")
        except Exception as e:
            print(f"[!] Impossible de convertir l'icône: {e}")
    
    # 4. Lancer PyInstaller
    print("\n[*] Démarrage de Pyinstaller... cela peut prendre quelques minutes.")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--noconsole",
        "--name=AURA",
        "--uac-admin",  # Demander les droits administrateur (UAC)
        "--collect-all", "customtkinter",
        "--collect-all", "google.generativeai",
        "--hidden-import", "plyer.platforms.win.notification",
        "--add-data", "translations.json;.",
        "--add-data", "assets;assets",
    ] + icon_flag + ["main.py"]
    
    try:
        subprocess.run(cmd, check=True)
        
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
        print("⚠️ L'application demandera les droits administrateur au lancement (UAC).\n")

    except subprocess.CalledProcessError as e:
        print("\n❌ Une erreur est survenue lors de la compilation.")
        print(f"Détails : {e}")

if __name__ == "__main__":
    # S'assurer qu'on est au bon endroit
    if not os.path.exists("main.py") or not os.path.exists("config.py"):
        print("Erreur: Ce script doit être exécuté dans le même dossier que main.py")
        sys.exit(1)
        
    build_executable()
