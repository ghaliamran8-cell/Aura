# =============================================================================
# ui.py — Interface AURA V3.1 — Style Assistant Moderne (Siri-inspired)
# =============================================================================
# Ce module gère :
# - Orbe animé flottant avec gradient pulsant (style assistant vocal)
# - Barre de recherche extensible style Spotlight
# - Animations fluides (fade, pulse, glow, easing)
# - Suggestions autocomplete en temps réel
# - Personnalisation complète (couleur, taille, forme, position, transparence, police)
# - System tray V3 (avec menu Settings)
# =============================================================================

import threading
import math
import time
import customtkinter as ctk
from config import settings, t, set_setting, logger, ASSETS_DIR
from scanner import search_apps, set_scan_callback, get_index, is_scanning
from commands import execute_command, set_ui_callback, set_exit_callback
from voice import speak, speak_key, listen, is_microphone_available
import settings_ui

# ---------------------------------------------------------------------------
# THÈME & COULEURS — Palette premium dynamique basée sur l'accent choisi
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple:
    """Convertit un hex (#RRGGBB) en tuple RGB."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convertit RGB en hex."""
    return f"#{r:02x}{g:02x}{b:02x}"

def _darken(hex_color: str, factor: float = 0.3) -> str:
    """Assombrit une couleur."""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(int(r * (1 - factor)), int(g * (1 - factor)), int(b * (1 - factor)))

def _lighten(hex_color: str, factor: float = 0.3) -> str:
    """Éclaircit une couleur."""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(min(255, int(r + (255 - r) * factor)),
                       min(255, int(g + (255 - g) * factor)),
                       min(255, int(b + (255 - b) * factor)))

def _build_colors(accent: str) -> dict:
    """Génère la palette complète à partir de la couleur d'accent."""
    return {
        "bg": "#0D0D1A",
        "surface": "#141428",
        "surface_hover": "#1A1A35",
        "input_bg": "#1E1E3A",
        "input_border": _darken(accent, 0.2),
        "text": settings.get("ui_font_color", "#E8E8E8"),
        "text_dim": "#6B6B8A",
        "accent": accent,
        "accent_hover": _lighten(accent, 0.2),
        "accent_glow": _lighten(accent, 0.4),
        "suggestion_hover": "#1C1C38",
        "listening": "#EF4444",
        "listening_glow": "#FF6B6B",
        "success": "#10B981",
        "warning": "#F59E0B",
        "orb_inner": _lighten(accent, 0.1),
        "orb_outer": _darken(accent, 0.3),
    }

# ---------------------------------------------------------------------------
# TAILLES — Presets
# ---------------------------------------------------------------------------

SIZE_PRESETS = {
    "small":  {"width": 520, "height": 56, "font_base": 13, "orb_size": 44, "corner": 14},
    "medium": {"width": 680, "height": 66, "font_base": 15, "orb_size": 52, "corner": 16},
    "large":  {"width": 820, "height": 76, "font_base": 17, "orb_size": 60, "corner": 18},
}

# ---------------------------------------------------------------------------
# CLASSE PRINCIPALE
# ---------------------------------------------------------------------------

class AuraMainApp:
    def __init__(self):
        self._load_theme_settings()
        self.is_visible = False
        self.is_listening = False
        self._building = False
        self._pulse_running = False
        self._pulse_phase = 0.0
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("AURA")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.0)
        
        # Taille initiale
        self._apply_size()
        self._position_window()
        self.root.configure(fg_color=self.colors["bg"])
        
        self._build_ui()
        
        set_ui_callback(self._show_result)
        set_exit_callback(self._quit)
        set_scan_callback(self._on_scan_complete)
        
        self.root.withdraw()
        
        self.root.bind("<Escape>", lambda e: self.hide())
        self.root.bind("<Return>", lambda e: self._on_submit())
        
        # Démarrer le pulse de l'orbe
        self._start_pulse()
        
    def _load_theme_settings(self):
        """Charge toutes les préférences UI depuis les settings."""
        accent = settings.get("ui_accent_color", "#7C3AED")
        self.colors = _build_colors(accent)
        
        size_key = settings.get("ui_size", "medium")
        self.size_preset = SIZE_PRESETS.get(size_key, SIZE_PRESETS["medium"])
        
        self.shape = settings.get("ui_shape", "pill")
        self.position = settings.get("ui_position", "center")
        self.transparency = settings.get("ui_transparency", 0.92)
        
        self.font_family = settings.get("ui_font_family", "Segoe UI")
        self.font_size = settings.get("ui_font_size", self.size_preset["font_base"])
        self.font_color = settings.get("ui_font_color", "#E8E8E8")
        font_style = settings.get("ui_font_style", "normal")
        self.font_weight = "bold" if font_style == "bold" else "normal"
        
    def _apply_size(self):
        """Applique la taille depuis le preset."""
        self.width = self.size_preset["width"]
        self.height = self.size_preset["height"]
        
    def _position_window(self):
        """Positionne la fenêtre selon la préférence."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        
        positions = {
            "center":     (screen_w // 2 - self.width // 2, int(screen_h * 0.30)),
            "bottom":     (screen_w // 2 - self.width // 2, int(screen_h * 0.75)),
            "top-right":  (screen_w - self.width - 30, 60),
            "top-left":   (30, 60),
        }
        x, y = positions.get(self.position, positions["center"])
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
    def _resize_window(self, new_height: int):
        self.height = new_height
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        
        positions = {
            "center":     (screen_w // 2 - self.width // 2, int(screen_h * 0.30)),
            "bottom":     (screen_w // 2 - self.width // 2, int(screen_h * 0.75) - new_height + self.size_preset["height"]),
            "top-right":  (screen_w - self.width - 30, 60),
            "top-left":   (30, 60),
        }
        x, y = positions.get(self.position, positions["center"])
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

    # -----------------------------------------------------------------------
    # BUILD UI — Construction de l'interface
    # -----------------------------------------------------------------------
        
    def _build_ui(self):
        corner = self.size_preset["corner"]
        orb_size = self.size_preset["orb_size"]
        
        # === CADRE PRINCIPAL avec bordure glow ===
        self.outer_frame = ctk.CTkFrame(
            self.root,
            fg_color=self.colors["bg"],
            corner_radius=corner + 2,
            border_width=1,
            border_color=self.colors["accent"]
        )
        self.outer_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        # === BARRE DE RECHERCHE ===
        self.search_frame = ctk.CTkFrame(
            self.outer_frame,
            fg_color=self.colors["surface"],
            corner_radius=corner,
            height=self.size_preset["height"] - 10
        )
        self.search_frame.pack(fill="x", padx=6, pady=6)
        self.search_frame.pack_propagate(False)
        
        # --- ORB INDICATEUR (style assistant vocal) ---
        self.orb_frame = ctk.CTkFrame(
            self.search_frame,
            fg_color="transparent",
            width=orb_size + 8,
            height=orb_size + 8
        )
        self.orb_frame.pack(side="left", padx=(10, 4))
        self.orb_frame.pack_propagate(False)
        
        self.orb_outer = ctk.CTkLabel(
            self.orb_frame,
            text="",
            width=orb_size + 4,
            height=orb_size + 4,
            corner_radius=orb_size // 2 + 2,
            fg_color=self.colors["orb_outer"]
        )
        self.orb_outer.place(relx=0.5, rely=0.5, anchor="center")
        
        self.orb_inner = ctk.CTkLabel(
            self.orb_frame,
            text="✦",
            width=orb_size - 4,
            height=orb_size - 4,
            corner_radius=(orb_size - 4) // 2,
            fg_color=self.colors["accent"],
            text_color="#FFFFFF",
            font=(self.font_family, orb_size // 3, "bold")
        )
        self.orb_inner.place(relx=0.5, rely=0.5, anchor="center")
        
        # --- CHAMP DE SAISIE ---
        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text=t("search_placeholder"),
            font=(self.font_family, self.font_size, self.font_weight),
            fg_color="transparent",
            border_width=0,
            text_color=self.colors["text"],
            placeholder_text_color=self.colors["text_dim"],
            height=40
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(4, 8))
        
        # --- BOUTON MIC ---
        self.mic_button = ctk.CTkButton(
            self.search_frame,
            text="🎤",
            width=42,
            height=42,
            corner_radius=21,
            font=(self.font_family, 16),
            fg_color=self.colors["input_bg"],
            hover_color=self.colors["accent"],
            border_width=1,
            border_color=self.colors["accent"],
            command=self._on_mic_click
        )
        self.mic_button.pack(side="right", padx=(4, 10))
        
        # === ZONE SUGGESTIONS ===
        self.suggestions_frame = ctk.CTkFrame(
            self.outer_frame,
            fg_color=self.colors["surface"],
            corner_radius=corner - 2
        )
        
        # === LABEL RÉSULTAT ===
        self.result_label = ctk.CTkLabel(
            self.outer_frame,
            text="",
            font=(self.font_family, self.font_size - 1),
            text_color=self.colors["text_dim"],
            anchor="w",
            justify="left",
            wraplength=self.width - 40
        )
        
        # --- BINDINGS ---
        self.search_entry.bind("<KeyRelease>", self._on_key_release)
        self._suggestion_widgets = []
        self._selected_index = -1
        self.search_entry.bind("<Up>", self._on_arrow_up)
        self.search_entry.bind("<Down>", self._on_arrow_down)

    # -----------------------------------------------------------------------
    # ANIMATIONS
    # -----------------------------------------------------------------------
    
    def _start_pulse(self):
        """Démarre l'animation pulsante de l'orbe."""
        if self._pulse_running:
            return
        self._pulse_running = True
        self._animate_pulse()
    
    def _animate_pulse(self):
        """Animation pulse douce de l'orbe — respiration vivante."""
        if not self._pulse_running:
            return
        
        self._pulse_phase += 0.08
        if self._pulse_phase > 2 * math.pi:
            self._pulse_phase -= 2 * math.pi
        
        # Pulse doux entre deux teintes
        pulse = (math.sin(self._pulse_phase) + 1) / 2  # 0.0 → 1.0
        
        accent = self.colors["accent"]
        r1, g1, b1 = _hex_to_rgb(accent)
        r2, g2, b2 = _hex_to_rgb(self.colors["accent_glow"])
        
        r = int(r1 + (r2 - r1) * pulse)
        g = int(g1 + (g2 - g1) * pulse)
        b = int(b1 + (b2 - b1) * pulse)
        
        current_color = _rgb_to_hex(min(255, r), min(255, g), min(255, b))
        
        try:
            if self.is_listening:
                # Mode écoute : pulse rouge rapide
                lr, lg, lb = _hex_to_rgb(self.colors["listening"])
                lr2, lg2, lb2 = _hex_to_rgb(self.colors["listening_glow"])
                cr = int(lr + (lr2 - lr) * pulse)
                cg = int(lg + (lg2 - lg) * pulse)
                cb = int(lb + (lb2 - lb) * pulse)
                current_color = _rgb_to_hex(min(255, cr), min(255, cg), min(255, cb))
                
            self.orb_inner.configure(fg_color=current_color)
            
            # Outer glow pulse léger
            outer_alpha = 0.3 + 0.15 * pulse
            outer_r = int(r1 * outer_alpha)
            outer_g = int(g1 * outer_alpha)
            outer_b = int(b1 * outer_alpha)
            self.orb_outer.configure(fg_color=_rgb_to_hex(
                min(255, outer_r), min(255, outer_g), min(255, outer_b)
            ))
        except Exception:
            pass
        
        interval = 40 if self.is_listening else 60
        self.root.after(interval, self._animate_pulse)
    
    # -----------------------------------------------------------------------
    # SHOW / HIDE avec animations
    # -----------------------------------------------------------------------
    
    def show(self):
        if self.is_visible:
            return
        self.is_visible = True
        self.root.deiconify()
        self._apply_size()
        self._position_window()
        self.search_entry.delete(0, "end")
        self._clear_suggestions()
        self._hide_result()
        self._resize_window(self.size_preset["height"] + 14)
        self._fade_in(0.0)
        self.root.after(100, lambda: self.search_entry.focus_force())
        
    def hide(self):
        if not self.is_visible:
            return
        self.is_visible = False
        self._fade_out(self.transparency)
        
    def toggle(self):
        if self.is_visible:
            self.hide()
        else:
            self.show()
        
    def _fade_in(self, alpha: float):
        target = self.transparency
        if alpha < target - 0.05:
            # Easing: accélère au début, ralentit à la fin
            step = max(0.04, (target - alpha) * 0.2)
            alpha = min(target, alpha + step)
            self.root.attributes("-alpha", alpha)
            self.root.after(12, lambda: self._fade_in(alpha))
        else:
            self.root.attributes("-alpha", target)
            
    def _fade_out(self, alpha: float):
        if alpha > 0.05:
            step = max(0.04, alpha * 0.2)
            alpha = max(0, alpha - step)
            self.root.attributes("-alpha", alpha)
            self.root.after(12, lambda: self._fade_out(alpha))
        else:
            self.root.attributes("-alpha", 0.0)
            self.root.withdraw()

    # -----------------------------------------------------------------------
    # RECHERCHE & SUGGESTIONS
    # -----------------------------------------------------------------------
            
    def _on_key_release(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        query = self.search_entry.get().strip()
        if len(query) < 1:
            self._clear_suggestions()
            self._resize_window(self.size_preset["height"] + 14)
            return
        results = search_apps(query)
        self._update_suggestions(results)
        
    def _update_suggestions(self, results: list):
        self._clear_suggestions()
        if not results:
            self._resize_window(self.size_preset["height"] + 14)
            return
        self.suggestions_frame.pack(fill="x", padx=8, pady=(0, 6))
        self._selected_index = -1
        
        for i, (name, path, score) in enumerate(results):
            frame = ctk.CTkFrame(
                self.suggestions_frame,
                fg_color="transparent",
                corner_radius=8,
                height=38
            )
            frame.pack(fill="x", padx=4, pady=1)
            frame.pack_propagate(False)
            
            # Icône basée sur le score
            if score > 0.85:
                icon = "⭐"
            elif score > 0.6:
                icon = "📁"
            else:
                icon = "🔍"
            
            label = ctk.CTkLabel(
                frame,
                text=f"  {icon}  {name}",
                font=(self.font_family, self.font_size - 1),
                text_color=self.colors["text"],
                anchor="w"
            )
            label.pack(side="left", fill="x", expand=True, padx=4)
            
            # Score badge
            score_text = f"{int(score * 100)}%"
            score_label = ctk.CTkLabel(
                frame,
                text=score_text,
                font=(self.font_family, 10),
                text_color=self.colors["text_dim"],
                width=40
            )
            score_label.pack(side="right", padx=8)
            
            app_name = name
            frame.bind("<Button-1>", lambda e, n=app_name: self._select_suggestion(n))
            label.bind("<Button-1>", lambda e, n=app_name: self._select_suggestion(n))
            frame.bind("<Enter>", lambda e, f=frame: f.configure(fg_color=self.colors["suggestion_hover"]))
            frame.bind("<Leave>", lambda e, f=frame: f.configure(fg_color="transparent"))
            self._suggestion_widgets.append(frame)
        
        new_height = self.size_preset["height"] + 14 + (len(results) * 40) + 16
        self._resize_window(min(new_height, 450))
        
    def _clear_suggestions(self):
        for widget in self._suggestion_widgets:
            widget.destroy()
        self._suggestion_widgets.clear()
        self.suggestions_frame.pack_forget()
        self._selected_index = -1
        
    def _select_suggestion(self, app_name: str):
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, f"ouvre {app_name}")
        self._on_submit()
        
    def _on_arrow_up(self, event):
        if self._suggestion_widgets:
            self._selected_index = max(0, self._selected_index - 1)
            self._highlight_suggestion()
            
    def _on_arrow_down(self, event):
        if self._suggestion_widgets:
            self._selected_index = min(len(self._suggestion_widgets) - 1, self._selected_index + 1)
            self._highlight_suggestion()
            
    def _highlight_suggestion(self):
        for i, widget in enumerate(self._suggestion_widgets):
            if i == self._selected_index:
                widget.configure(fg_color=self.colors["suggestion_hover"])
            else:
                widget.configure(fg_color="transparent")

    # -----------------------------------------------------------------------
    # SUBMIT & RESULTS
    # -----------------------------------------------------------------------
                
    def _on_submit(self):
        if self._selected_index >= 0 and self._suggestion_widgets:
            widget = self._suggestion_widgets[self._selected_index]
            children = widget.winfo_children()
            if children:
                text = children[0].cget("text").strip()
                for icon in ["⭐  ", "📁  ", "🔍  ", "  "]:
                    text = text.replace(icon, "")
                self.search_entry.delete(0, "end")
                self.search_entry.insert(0, f"ouvre {text.strip()}")
        query = self.search_entry.get().strip()
        if not query:
            return
        self._clear_suggestions()
        
        # Afficher un indicateur "thinking"
        self._show_thinking()
        
        def _run():
            result = execute_command(query)
            if result and self.is_visible:
                self.root.after(0, lambda: self._show_result(result))
        threading.Thread(target=_run, daemon=True).start()
    
    def _show_thinking(self):
        """Affiche l'indicateur de réflexion."""
        self.orb_inner.configure(text="⋯")
        
    def _show_result(self, text: str):
        # Affiche le texte UNIQUEMENT si l'UI Spotlight est actuellement ouverte
        if not self.is_visible:
            return
        
        self.orb_inner.configure(text="✦")
        self._clear_suggestions()
        self.result_label.configure(text=text, text_color=self.colors["text"])
        self.result_label.pack(fill="x", padx=16, pady=(4, 10))
        lines = text.count("\n") + 1
        new_height = self.size_preset["height"] + 14 + (lines * 22) + 28
        self._resize_window(min(new_height, 450))
        self.root.after(5000, self._auto_hide_result)
        
    def _hide_result(self):
        self.result_label.pack_forget()
        
    def _auto_hide_result(self):
        self._hide_result()
        if not self.search_entry.get().strip():
            self.hide()

    # -----------------------------------------------------------------------
    # MICROPHONE
    # -----------------------------------------------------------------------
            
    def _on_mic_click(self):
        if self.is_listening:
            return
        self._start_listening()
        
    def _start_listening(self):
        if not is_microphone_available():
            speak_key("error_mic")
            self._show_result(t("error_mic"))
            return
        self.is_listening = True
        self.mic_button.configure(
            fg_color=self.colors["listening"],
            border_color=self.colors["listening"]
        )
        self.orb_inner.configure(text="🎤")
        self.search_entry.configure(placeholder_text=t("listening"))
        
        def _listen_thread():
            text = listen()
            self.root.after(0, lambda: self._on_listen_complete(text))
        threading.Thread(target=_listen_thread, daemon=True).start()
        
    def _on_listen_complete(self, text: str | None):
        self.is_listening = False
        self.mic_button.configure(
            fg_color=self.colors["input_bg"],
            border_color=self.colors["accent"]
        )
        self.orb_inner.configure(text="✦")
        self.search_entry.configure(placeholder_text=t("search_placeholder"))
        if text:
            self.search_entry.delete(0, "end")
            self.search_entry.insert(0, text)
            self._on_submit()

    # -----------------------------------------------------------------------
    # CALLBACKS
    # -----------------------------------------------------------------------
            
    def _on_scan_complete(self, result: dict, scan_type: str):
        count = len(result.get("apps", {}))
        msg = t("scan_deep_done", count=count) if scan_type == "deep" else t("scan_quick_done", count=count)
        speak(msg)
        if self.is_visible:
            self.root.after(0, lambda: self._show_result(msg))
    
    def reload_theme(self):
        """Recharge le thème dynamiquement (appelé après changement dans settings)."""
        self._load_theme_settings()
        # Mettre à jour les couleurs
        try:
            self.outer_frame.configure(
                fg_color=self.colors["bg"],
                border_color=self.colors["accent"]
            )
            self.search_frame.configure(fg_color=self.colors["surface"])
            self.orb_inner.configure(fg_color=self.colors["accent"])
            self.orb_outer.configure(fg_color=self.colors["orb_outer"])
            self.search_entry.configure(
                text_color=self.colors["text"],
                font=(self.font_family, self.font_size, self.font_weight)
            )
            self.mic_button.configure(
                fg_color=self.colors["input_bg"],
                border_color=self.colors["accent"]
            )
            self.result_label.configure(
                font=(self.font_family, self.font_size - 1),
                text_color=self.colors["text_dim"]
            )
        except Exception as e:
            logger.warning(f"Erreur rechargement thème: {e}")

    # -----------------------------------------------------------------------
    # SYSTEM TRAY
    # -----------------------------------------------------------------------
            
    def _create_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw, ImageFont
            
            # Essayer de charger l'icône custom
            icon_path = ASSETS_DIR / "icon.png"
            if icon_path.exists():
                img = Image.open(str(icon_path)).resize((64, 64))
            else:
                # Fallback: générer un icône programmatiquement
                img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)
                # Cercle gradient simulé
                for i in range(30, 0, -1):
                    alpha = int(255 * (i / 30))
                    r, g, b = _hex_to_rgb(self.colors["accent"])
                    color = (min(255, r + (30 - i) * 3), min(255, g + (30 - i) * 2), b, alpha)
                    d.ellipse([32 - i, 32 - i, 32 + i, 32 + i], fill=color)
                d.text((25, 20), "A", fill="white")
            
            menu = pystray.Menu(
                pystray.MenuItem("🔍 Ouvrir AURA", lambda: self.root.after(0, self.show)),
                pystray.MenuItem("⚙️ Paramètres", lambda: self.root.after(0, lambda: settings_ui.open_settings(self.root))),
                pystray.MenuItem("❌ Quitter", self._quit)
            )
            self.tray = pystray.Icon("AURA", img, "AURA — Assistant Intelligent", menu)
            threading.Thread(target=self.tray.run, daemon=True).start()
        except Exception as e:
            logger.warning(f"Erreur création tray: {e}")

    # -----------------------------------------------------------------------
    # LIFECYCLE
    # -----------------------------------------------------------------------
            
    def run(self):
        self._create_tray()
        self.root.mainloop()
        
    def _quit(self):
        logger.info("Fermeture totale AURA.")
        self._pulse_running = False
        try:
            self.tray.stop()
        except:
            pass
        from voice import stop_continuous_listening, stop_tts
        stop_continuous_listening()
        stop_tts()
        import sys
        sys.exit(0)
