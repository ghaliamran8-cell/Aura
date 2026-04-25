# =============================================================================
# settings_ui.py — Interface de configuration d'AURA V3.1
# =============================================================================
# Gère les paramètres :
# - Langue (FR/EN)
# - Clé API Gemini (sauvegardée de manière sécurisée)
# - Thème (Sombre, Clair)
# - Touche Furtive (Stealth Hotkey)
# - Personnalisation UI (couleur, taille, forme, position, transparence, police)
# =============================================================================

import os
import webbrowser
import customtkinter as ctk
from config import settings, t, set_setting, save_settings, set_autostart, logger

# Couleurs de l'interface de configuration
_CFG_COLORS = {
    "bg": "#0D0D1A",
    "surface": "#141428",
    "accent": "#7C3AED",
    "text": "#E8E8E8",
    "text_dim": "#6B6B8A",
    "section_bg": "#1A1A35",
}

class SettingsWindow:
    def __init__(self, parent_root=None):
        # Création de la fenêtre
        if parent_root:
            self.root = ctk.CTkToplevel(parent_root)
        else:
            self.root = ctk.CTk()
            
        self.root.title("AURA — Paramètres")
        self.root.geometry("560x780")
        self.root.resizable(False, False)
        self.root.configure(fg_color=_CFG_COLORS["bg"])
        
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
        
        # Variables UI Customization
        self.var_accent = ctk.StringVar(value=settings.get("ui_accent_color", "#7C3AED"))
        self.var_size = ctk.StringVar(value=settings.get("ui_size", "medium").capitalize())
        self.var_shape = ctk.StringVar(value=settings.get("ui_shape", "pill").capitalize())
        self.var_position = ctk.StringVar(value=settings.get("ui_position", "center").capitalize())
        self.var_transparency = ctk.DoubleVar(value=settings.get("ui_transparency", 0.92))
        self.var_font_family = ctk.StringVar(value=settings.get("ui_font_family", "Segoe UI"))
        self.var_font_size = ctk.IntVar(value=settings.get("ui_font_size", 15))
        self.var_font_color = ctk.StringVar(value=settings.get("ui_font_color", "#E8E8E8"))
        self.var_font_style = ctk.StringVar(value=settings.get("ui_font_style", "normal").capitalize())
        
        self._build_ui()
        
    def _center_window(self):
        self.root.update_idletasks()
        w = 560
        h = 780
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.root.geometry('%dx%d+%d+%d' % (w, h, x, y))

    def _make_section(self, parent, title: str) -> ctk.CTkFrame:
        """Crée une section avec titre et cadre stylé."""
        frame = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CFG_COLORS["section_bg"],
                            border_width=1, border_color="#2A2A4A")
        frame.pack(fill="x", padx=20, pady=(0, 10))
        
        lbl = ctk.CTkLabel(frame, text=title, font=("Segoe UI", 14, "bold"),
                          text_color=_CFG_COLORS["accent"])
        lbl.pack(anchor="w", padx=15, pady=(10, 6))
        return frame
    
    def _make_row(self, parent, label_text: str) -> ctk.CTkFrame:
        """Crée une ligne label + widget."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(row, text=label_text, font=("Segoe UI", 12),
                    text_color=_CFG_COLORS["text"]).pack(side="left")
        return row

    def _build_ui(self):
        # === SCROLLABLE FRAME ===
        scroll = ctk.CTkScrollableFrame(
            self.root,
            fg_color=_CFG_COLORS["bg"],
            scrollbar_button_color=_CFG_COLORS["accent"],
            scrollbar_button_hover_color="#9B6AFF"
        )
        scroll.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Titre principal
        lbl_title = ctk.CTkLabel(scroll, text="✦ AURA — Configuration",
                                font=("Segoe UI", 22, "bold"),
                                text_color=_CFG_COLORS["text"])
        lbl_title.pack(pady=(16, 4))
        
        subtitle = ctk.CTkLabel(scroll, text="Personnalisez votre assistant intelligent",
                               font=("Segoe UI", 11),
                               text_color=_CFG_COLORS["text_dim"])
        subtitle.pack(pady=(0, 14))
        
        # ===== SECTION GÉNÉRAL =====
        frame_gen = self._make_section(scroll, "⚙️ Général")
        
        row = self._make_row(frame_gen, "Langue de l'interface :")
        ctk.CTkOptionMenu(row, variable=self.var_language, values=["FR", "EN"],
                         width=110, fg_color=_CFG_COLORS["surface"],
                         button_color=_CFG_COLORS["accent"]).pack(side="right")
        
        row = self._make_row(frame_gen, "Thème :")
        ctk.CTkOptionMenu(row, variable=self.var_theme, values=["Dark", "Light", "System"],
                         width=110, fg_color=_CFG_COLORS["surface"],
                         button_color=_CFG_COLORS["accent"]).pack(side="right")
        
        row = self._make_row(frame_gen, "Touche Furtive (ex: F9) :")
        ctk.CTkEntry(row, textvariable=self.var_stealth, width=110,
                    fg_color=_CFG_COLORS["surface"]).pack(side="right")
        
        row = self._make_row(frame_gen, "Lancer au démarrage de Windows :")
        ctk.CTkSwitch(row, text="", variable=self.var_autostart,
                     onvalue=True, offvalue=False,
                     progress_color=_CFG_COLORS["accent"]).pack(side="right")
        
        # Petit padding en bas de section
        ctk.CTkLabel(frame_gen, text="", height=4).pack()
        
        # ===== SECTION IA =====
        frame_ia = self._make_section(scroll, "🧠 Intelligence Artificielle (Gemini)")
        
        lbl_info = ctk.CTkLabel(frame_ia,
                               text="AURA a besoin d'une clé API gratuite pour réfléchir.",
                               font=("Segoe UI", 11), text_color=_CFG_COLORS["text_dim"])
        lbl_info.pack(anchor="w", padx=15)
        
        btn_link = ctk.CTkButton(frame_ia, text="🔗 Créer ma clé Google Gemini (Gratuit)",
                                fg_color="transparent", hover_color="#1A1A35",
                                text_color="#3B82F6", font=("Segoe UI", 11),
                                anchor="w", height=28,
                                command=lambda: webbrowser.open("https://aistudio.google.com/app/apikey"))
        btn_link.pack(anchor="w", padx=10, pady=(2, 4))
        
        row = self._make_row(frame_ia, "Clé API :")
        ctk.CTkEntry(row, textvariable=self.var_apikey, width=300,
                    fg_color=_CFG_COLORS["surface"], show="•").pack(side="right")
        
        ctk.CTkLabel(frame_ia, text="", height=4).pack()
        
        # ===== SECTION APPARENCE =====
        frame_ui = self._make_section(scroll, "🎨 Apparence de l'interface")
        
        # Couleur d'accent
        row = self._make_row(frame_ui, "Couleur d'accent :")
        accent_frame = ctk.CTkFrame(row, fg_color="transparent")
        accent_frame.pack(side="right")
        
        # Palette de couleurs prédéfinies
        preset_colors = ["#7C3AED", "#3B82F6", "#06B6D4", "#10B981",
                         "#F59E0B", "#EF4444", "#EC4899", "#8B5CF6"]
        for color in preset_colors:
            btn = ctk.CTkButton(
                accent_frame, text="", width=24, height=24,
                corner_radius=12, fg_color=color,
                hover_color=color, border_width=2,
                border_color=_CFG_COLORS["bg"],
                command=lambda c=color: self.var_accent.set(c)
            )
            btn.pack(side="left", padx=1)
        
        # Champ hex custom
        row = self._make_row(frame_ui, "Hex personnalisé :")
        ctk.CTkEntry(row, textvariable=self.var_accent, width=110,
                    fg_color=_CFG_COLORS["surface"]).pack(side="right")
        
        # Taille
        row = self._make_row(frame_ui, "Taille de la barre :")
        ctk.CTkOptionMenu(row, variable=self.var_size, values=["Small", "Medium", "Large"],
                         width=110, fg_color=_CFG_COLORS["surface"],
                         button_color=_CFG_COLORS["accent"]).pack(side="right")
        
        # Forme
        row = self._make_row(frame_ui, "Forme :")
        ctk.CTkOptionMenu(row, variable=self.var_shape, values=["Pill", "Rectangle", "Orb"],
                         width=110, fg_color=_CFG_COLORS["surface"],
                         button_color=_CFG_COLORS["accent"]).pack(side="right")
        
        # Position
        row = self._make_row(frame_ui, "Position à l'écran :")
        ctk.CTkOptionMenu(row, variable=self.var_position,
                         values=["Center", "Bottom", "Top-right", "Top-left"],
                         width=130, fg_color=_CFG_COLORS["surface"],
                         button_color=_CFG_COLORS["accent"]).pack(side="right")
        
        # Transparence
        row = self._make_row(frame_ui, f"Transparence :")
        self.transparency_slider = ctk.CTkSlider(
            row, from_=0.3, to=1.0, variable=self.var_transparency,
            width=160, progress_color=_CFG_COLORS["accent"],
            button_color=_CFG_COLORS["accent"],
            button_hover_color="#9B6AFF"
        )
        self.transparency_slider.pack(side="right")
        
        ctk.CTkLabel(frame_ui, text="", height=4).pack()
        
        # ===== SECTION TYPOGRAPHIE =====
        frame_font = self._make_section(scroll, "🔤 Typographie")
        
        row = self._make_row(frame_font, "Police :")
        ctk.CTkOptionMenu(row, variable=self.var_font_family,
                         values=["Segoe UI", "Cascadia Code", "Consolas",
                                "Arial", "Verdana", "Tahoma",
                                "Trebuchet MS", "Calibri", "Georgia"],
                         width=160, fg_color=_CFG_COLORS["surface"],
                         button_color=_CFG_COLORS["accent"]).pack(side="right")
        
        row = self._make_row(frame_font, "Taille de police :")
        ctk.CTkOptionMenu(row, variable=self.var_font_size,
                         values=[11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
                         width=110, fg_color=_CFG_COLORS["surface"],
                         button_color=_CFG_COLORS["accent"]).pack(side="right")
        
        row = self._make_row(frame_font, "Couleur du texte :")
        font_colors = {"Blanc": "#E8E8E8", "Gris clair": "#B0B0C0",
                       "Cyan": "#06B6D4", "Vert": "#10B981", "Or": "#F59E0B"}
        ctk.CTkOptionMenu(row, variable=self.var_font_color,
                         values=list(font_colors.values()),
                         width=110, fg_color=_CFG_COLORS["surface"],
                         button_color=_CFG_COLORS["accent"]).pack(side="right")
        
        row = self._make_row(frame_font, "Style :")
        ctk.CTkOptionMenu(row, variable=self.var_font_style,
                         values=["Normal", "Bold", "Italic"],
                         width=110, fg_color=_CFG_COLORS["surface"],
                         button_color=_CFG_COLORS["accent"]).pack(side="right")
        
        ctk.CTkLabel(frame_font, text="", height=4).pack()
        
        # ===== BOUTONS =====
        frame_btns = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_btns.pack(fill="x", padx=20, pady=(10, 20))
        
        btn_save = ctk.CTkButton(
            frame_btns, text="✓  Enregistrer & Quitter",
            font=("Segoe UI", 13, "bold"),
            fg_color=_CFG_COLORS["accent"],
            hover_color="#9B6AFF",
            height=40, corner_radius=10,
            command=self.save_and_close
        )
        btn_save.pack(side="right", padx=10)
        
        btn_cancel = ctk.CTkButton(
            frame_btns, text="Annuler",
            font=("Segoe UI", 13),
            fg_color="#2A2A4A",
            hover_color="#3A3A5A",
            height=40, corner_radius=10,
            command=self.close
        )
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
        
        # UI Customization
        settings["ui_accent_color"] = self.var_accent.get()
        settings["ui_size"] = self.var_size.get().lower()
        settings["ui_shape"] = self.var_shape.get().lower()
        settings["ui_position"] = self.var_position.get().lower()
        settings["ui_transparency"] = round(self.var_transparency.get(), 2)
        settings["ui_font_family"] = self.var_font_family.get()
        # Handle font_size which might come as string from OptionMenu
        try:
            settings["ui_font_size"] = int(self.var_font_size.get())
        except (ValueError, TypeError):
            settings["ui_font_size"] = 15
        settings["ui_font_color"] = self.var_font_color.get()
        settings["ui_font_style"] = self.var_font_style.get().lower()
        
        # Configurer le registre Windows !
        set_autostart(settings["autostart"])
        
        # Sauvegarde disque
        save_settings()
        
        # Application immédiate du thème
        ctk.set_appearance_mode(settings["theme"])
        
        # Notifier main.py pour re-register hotkey + reconfigurer Gemini + recharger UI
        try:
            import builtins
            if hasattr(builtins, '_aura_update_stealth_hotkey'):
                builtins._aura_update_stealth_hotkey()
            if hasattr(builtins, '_aura_reload_theme'):
                builtins._aura_reload_theme()
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
