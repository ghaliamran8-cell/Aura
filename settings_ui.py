# =============================================================================
# settings_ui.py — Interface de configuration d'AURA V3
# =============================================================================
# Gère les paramètres :
# - Langue (FR/EN)
# - Clé API Gemini (sauvegardée de manière sécurisée)
# - Thème (Sombre, Clair)
# - Touche Furtive (Stealth Hotkey)
# =============================================================================

import os
import webbrowser
import customtkinter as ctk
from config import settings, t, set_setting, save_settings, set_autostart, logger

class SettingsWindow:
    def __init__(self, parent_root=None):
        # Création de la fenêtre
        if parent_root:
            self.root = ctk.CTkToplevel(parent_root)
        else:
            self.root = ctk.CTk()
            
        self.root.title("AURA - Paramètres")
        self.root.geometry("500x480")
        self.root.resizable(False, False)
        
        # Centrer
        self._center_window()
        
        # On-Top pour ne pas la perdre
        self.root.attributes("-topmost", True)
        
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        
        # --- Variables ---
        self.var_language = ctk.StringVar(value=settings.get("language", "fr").upper())
        self.var_theme = ctk.StringVar(value=settings.get("theme", "dark").capitalize())
        self.var_stealth = ctk.StringVar(value=settings.get("stealth_hotkey", "f9").upper())
        self.var_apikey = ctk.StringVar(value=settings.get("gemini_api_key", ""))
        self.var_autostart = ctk.BooleanVar(value=settings.get("autostart", False))
        
        self._build_ui()
        
    def _center_window(self):
        self.root.update_idletasks()
        w = 500
        h = 480
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.root.geometry('%dx%d+%d+%d' % (w, h, x, y))

    def _build_ui(self):
        # Titre principal
        lbl_title = ctk.CTkLabel(self.root, text="Configuration d'AURA", font=("Segoe UI", 24, "bold"))
        lbl_title.pack(pady=(20, 20))
        
        # --- ONGLET 1 : GÉNÉRAL ---
        frame_general = ctk.CTkFrame(self.root, corner_radius=10)
        frame_general.pack(fill="x", padx=20, pady=10)
        
        lbl_gen = ctk.CTkLabel(frame_general, text="Général", font=("Segoe UI", 16, "bold"))
        lbl_gen.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Langue
        row1 = ctk.CTkFrame(frame_general, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row1, text="Langue de l'interface :").pack(side="left")
        ctk.CTkOptionMenu(row1, variable=self.var_language, values=["FR", "EN"], width=100).pack(side="right")
        
        # Thème
        row2 = ctk.CTkFrame(frame_general, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row2, text="Thème (Défaut: Sombre) :").pack(side="left")
        ctk.CTkOptionMenu(row2, variable=self.var_theme, values=["Dark", "Light", "System"], width=100).pack(side="right")
        
        # Touche furtive
        row3 = ctk.CTkFrame(frame_general, fg_color="transparent")
        row3.pack(fill="x", padx=15, pady=(5, 5))
        ctk.CTkLabel(row3, text="Touche Furtive (tapez le texte, ex: f9) :").pack(side="left")
        ctk.CTkEntry(row3, textvariable=self.var_stealth, width=150).pack(side="right")
        
        # Lancement avec Windows
        row4 = ctk.CTkFrame(frame_general, fg_color="transparent")
        row4.pack(fill="x", padx=15, pady=(5, 15))
        ctk.CTkLabel(row4, text="Lancer AURA au démarrage de Windows :").pack(side="left")
        ctk.CTkSwitch(row4, text="", variable=self.var_autostart, onvalue=True, offvalue=False).pack(side="right")

        # --- ONGLET 2 : INTELLIGENCE ARTIFICIELLE ---
        frame_ia = ctk.CTkFrame(self.root, corner_radius=10)
        frame_ia.pack(fill="x", padx=20, pady=10)
        
        lbl_ia = ctk.CTkLabel(frame_ia, text="Cerveau IA (Gemini)", font=("Segoe UI", 16, "bold"))
        lbl_ia.pack(anchor="w", padx=15, pady=(10, 5))
        
        lbl_info = ctk.CTkLabel(frame_ia, text="AURA a besoin d'une clé API gratuite pour réfléchir.", font=("Segoe UI", 12), text_color="gray")
        lbl_info.pack(anchor="w", padx=15)
        
        # Lien pour générer
        btn_link = ctk.CTkButton(frame_ia, text="🔗 Créer ma clé Google Gemini (Gratuit)", 
                                 fg_color="transparent", hover_color="#2b2b2b", text_color="#3b82f6",
                                 command=lambda: webbrowser.open("https://aistudio.google.com/app/apikey"))
        btn_link.pack(anchor="w", padx=10, pady=(0, 5))
        
        # Champ API Key
        row_key = ctk.CTkFrame(frame_ia, fg_color="transparent")
        row_key.pack(fill="x", padx=15, pady=(5, 15))
        ctk.CTkLabel(row_key, text="Clé API :").pack(side="left")
        entry_key = ctk.CTkEntry(row_key, textvariable=self.var_apikey, width=280)
        entry_key.pack(side="right")

        # --- BOUTONS ---
        frame_btns = ctk.CTkFrame(self.root, fg_color="transparent")
        frame_btns.pack(fill="x", padx=20, pady=20)
        
        btn_save = ctk.CTkButton(frame_btns, text="Enregistrer & Quitter", command=self.save_and_close)
        btn_save.pack(side="right", padx=10)
        
        btn_cancel = ctk.CTkButton(frame_btns, text="Annuler", fg_color="gray", command=self.close)
        btn_cancel.pack(side="right")

    def save_and_close(self):
        """Sauvegarde les paramètres et ferme."""
        logger.info("Sauvegarde des paramètres via SettingsUI...")
        
        # Mettre à jour les variables dans settings
        settings["language"] = self.var_language.get().lower()
        settings["theme"] = self.var_theme.get().lower()
        settings["stealth_hotkey"] = self.var_stealth.get().lower()
        settings["gemini_api_key"] = self.var_apikey.get().strip()
        settings["autostart"] = self.var_autostart.get()
        
        # Configurer le registre Windows !
        set_autostart(settings["autostart"])
        
        # Sauvegarde disque
        save_settings()
        
        # Application immédiate du thème
        ctk.set_appearance_mode(settings["theme"])
        
        # Notifier main.py pour re-register hotkey + reconfigurer Gemini
        try:
            import builtins
            if hasattr(builtins, '_aura_update_stealth_hotkey'):
                builtins._aura_update_stealth_hotkey()
        except Exception as e:
            logger.info(f"Callback post-save: {e}")
        
        self.close()

    def close(self):
        """Ferme la fenêtre sans forcer l'arrêt total."""
        self.root.destroy()

def open_settings(parent=None):
    """Fonction utilitaire pour ouvrir les paramètres."""
    app = SettingsWindow(parent)
    if not parent:
        app.root.mainloop()

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    open_settings()
