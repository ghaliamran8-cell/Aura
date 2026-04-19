# =============================================================================
# ui.py — Interface Spotlight d'AURA (Restore V2 with V3 Stealth logic)
# =============================================================================
# Ce module gère :
# - La barre de recherche flottante, style Spotlight, invoquée spécifiquement
# - L'autocomplétion des suggestions en temps réel
# - L'affichage/masquage via Hotkey `ctrl+space+a`
# - Le system tray V3 (avec menu Settings)
# =============================================================================

import threading
import customtkinter as ctk
from config import settings, t, set_setting, logger
from scanner import search_apps, set_scan_callback, get_index, is_scanning
from commands import execute_command, set_ui_callback, set_exit_callback
from voice import speak, speak_key, listen, is_microphone_available
import settings_ui

COLORS = {
    "dark": {
        "bg": "#1A1A2E",           # Fond principal (bleu très foncé)
        "surface": "#16213E",      # Surface des widgets
        "input_bg": "#0F3460",     # Fond du champ de saisie
        "input_border": "#533483", # Bordure du champ
        "text": "#E8E8E8",         # Texte principal
        "text_dim": "#8B8B9E",     # Texte secondaire
        "accent": "#7C3AED",       # Accent violet
        "accent_hover": "#8B5CF6", # Accent hover
        "suggestion_hover": "#1E2A4A",
        "listening": "#EF4444",    # Rouge écoute
        "success": "#10B981"
    }
}

class AuraMainApp:
    def __init__(self):
        self.colors = COLORS["dark"]
        self.is_visible = False
        self.is_listening = False
        self._building = False
        
        ctk.set_appearance_mode(settings.get("theme", "dark"))
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("AURA")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.0)
        
        self.width = 680
        self.height = 70
        self._center_window()
        self.root.configure(fg_color=self.colors["bg"])
        
        self._build_ui()
        
        set_ui_callback(self._show_result)
        set_exit_callback(self._quit)
        set_scan_callback(self._on_scan_complete)
        
        self.root.withdraw()
        
        self.root.bind("<Escape>", lambda e: self.hide())
        self.root.bind("<Return>", lambda e: self._on_submit())
        
    def _build_ui(self):
        self.main_frame = ctk.CTkFrame(self.root, fg_color=self.colors["bg"], corner_radius=16)
        self.main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.search_frame = ctk.CTkFrame(self.main_frame, fg_color=self.colors["surface"], corner_radius=14, height=56)
        self.search_frame.pack(fill="x", padx=8, pady=(8, 4))
        self.search_frame.pack_propagate(False)
        
        self.status_indicator = ctk.CTkLabel(self.search_frame, text="●", font=("Segoe UI", 18), text_color=self.colors["accent"], width=30)
        self.status_indicator.pack(side="left", padx=(12, 4))
        
        self.search_entry = ctk.CTkEntry(
            self.search_frame, placeholder_text=t("search_placeholder"),
            font=("Segoe UI", 16), fg_color="transparent", border_width=0,
            text_color=self.colors["text"], placeholder_text_color=self.colors["text_dim"], height=40
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(4, 8))
        
        self.mic_button = ctk.CTkButton(
            self.search_frame, text="🎤", width=40, height=40, corner_radius=10,
            font=("Segoe UI", 16), fg_color=self.colors["input_bg"],
            hover_color=self.colors["accent"], command=self._on_mic_click
        )
        self.mic_button.pack(side="right", padx=(4, 8))
        
        self.suggestions_frame = ctk.CTkFrame(self.main_frame, fg_color=self.colors["surface"], corner_radius=12)
        
        self.result_label = ctk.CTkLabel(self.main_frame, text="", font=("Segoe UI", 13),
                                         text_color=self.colors["text_dim"], anchor="w", justify="left", wraplength=640)
        
        self.search_entry.bind("<KeyRelease>", self._on_key_release)
        self._suggestion_widgets = []
        self._selected_index = -1
        self.search_entry.bind("<Up>", self._on_arrow_up)
        self.search_entry.bind("<Down>", self._on_arrow_down)
        
    def _center_window(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - self.width) // 2
        y = int(screen_h * 0.3)
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
    def _resize_window(self, new_height: int):
        self.height = new_height
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - self.width) // 2
        y = int(screen_h * 0.3)
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
    def show(self):
        if self.is_visible: return
        self.is_visible = True
        self.root.deiconify()
        self._center_window()
        self.search_entry.delete(0, "end")
        self._clear_suggestions()
        self._hide_result()
        self._resize_window(70)
        self._fade_in(0.0)
        self.root.after(100, lambda: self.search_entry.focus_force())
        
    def hide(self):
        if not self.is_visible: return
        self.is_visible = False
        self._fade_out(1.0)
        
    def toggle(self):
        if self.is_visible: self.hide()
        else: self.show()
        
    def _fade_in(self, alpha: float):
        if alpha < 0.95:
            alpha += 0.1
            self.root.attributes("-alpha", alpha)
            self.root.after(15, lambda: self._fade_in(alpha))
        else:
            self.root.attributes("-alpha", 0.95)
            
    def _fade_out(self, alpha: float):
        if alpha > 0.05:
            alpha -= 0.1
            self.root.attributes("-alpha", alpha)
            self.root.after(15, lambda: self._fade_out(alpha))
        else:
            self.root.attributes("-alpha", 0.0)
            self.root.withdraw()
            
    def _on_key_release(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        query = self.search_entry.get().strip()
        if len(query) < 1:
            self._clear_suggestions()
            self._resize_window(70)
            return
        results = search_apps(query)
        self._update_suggestions(results)
        
    def _update_suggestions(self, results: list):
        self._clear_suggestions()
        if not results:
            self._resize_window(70)
            return
        self.suggestions_frame.pack(fill="x", padx=8, pady=(0, 4))
        self._selected_index = -1
        for i, (name, path, score) in enumerate(results):
            frame = ctk.CTkFrame(self.suggestions_frame, fg_color="transparent", corner_radius=8, height=36)
            frame.pack(fill="x", padx=4, pady=1)
            frame.pack_propagate(False)
            icon = "⭐" if score > 0.85 else "📁"
            label = ctk.CTkLabel(frame, text=f"  {icon}  {name}", font=("Segoe UI", 14), text_color=self.colors["text"], anchor="w")
            label.pack(side="left", fill="x", expand=True, padx=4)
            app_name = name
            frame.bind("<Button-1>", lambda e, n=app_name: self._select_suggestion(n))
            label.bind("<Button-1>", lambda e, n=app_name: self._select_suggestion(n))
            frame.bind("<Enter>", lambda e, f=frame: f.configure(fg_color=self.colors["suggestion_hover"]))
            frame.bind("<Leave>", lambda e, f=frame: f.configure(fg_color="transparent"))
            self._suggestion_widgets.append(frame)
        new_height = 70 + 4 + (len(results) * 38) + 12
        self._resize_window(min(new_height, 400))
        
    def _clear_suggestions(self):
        for widget in self._suggestion_widgets: widget.destroy()
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
            widget.configure(fg_color=self.colors["suggestion_hover"] if i == self._selected_index else "transparent")
            
    def _on_submit(self):
        if self._selected_index >= 0 and self._suggestion_widgets:
            widget = self._suggestion_widgets[self._selected_index]
            children = widget.winfo_children()
            if children:
                text = children[0].cget("text").strip()
                for icon in ["⭐  ", "📁  ", "  "]: text = text.replace(icon, "")
                self.search_entry.delete(0, "end")
                self.search_entry.insert(0, f"ouvre {text.strip()}")
        query = self.search_entry.get().strip()
        if not query: return
        self._clear_suggestions()
        def _run():
            result = execute_command(query)
            if result and self.is_visible:
                self.root.after(0, lambda: self._show_result(result))
        threading.Thread(target=_run, daemon=True).start()
        
    def _show_result(self, text: str):
        # Affiche le texte UNIQUEMENT si l'UI Spotlight est actuellement ouverte
        if not self.is_visible:
            return
            
        self._clear_suggestions()
        self.result_label.configure(text=text)
        self.result_label.pack(fill="x", padx=16, pady=(4, 8))
        lines = text.count("\n") + 1
        new_height = 70 + (lines * 22) + 20
        self._resize_window(min(new_height, 400))
        self.root.after(4000, self._auto_hide_result)
        
    def _hide_result(self):
        self.result_label.pack_forget()
        
    def _auto_hide_result(self):
        self._hide_result()
        if not self.search_entry.get().strip():
            self.hide()
            
    def _on_mic_click(self):
        if self.is_listening: return
        self._start_listening()
        
    def _start_listening(self):
        if not is_microphone_available():
            speak_key("error_mic")
            self._show_result(t("error_mic"))
            return
        self.is_listening = True
        self.status_indicator.configure(text_color=self.colors["listening"])
        self.mic_button.configure(fg_color=self.colors["listening"])
        self.search_entry.configure(placeholder_text=t("listening"))
        def _listen_thread():
            text = listen()
            self.root.after(0, lambda: self._on_listen_complete(text))
        threading.Thread(target=_listen_thread, daemon=True).start()
        
    def _on_listen_complete(self, text: str | None):
        self.is_listening = False
        self.status_indicator.configure(text_color=self.colors["accent"])
        self.mic_button.configure(fg_color=self.colors["input_bg"])
        self.search_entry.configure(placeholder_text=t("search_placeholder"))
        if text:
            self.search_entry.delete(0, "end")
            self.search_entry.insert(0, text)
            self._on_submit()
            
    def _on_scan_complete(self, result: dict, scan_type: str):
        count = len(result.get("apps", {}))
        msg = t("scan_deep_done", count=count) if scan_type == "deep" else t("scan_quick_done", count=count)
        speak(msg)
        if self.is_visible:
            self.root.after(0, lambda: self._show_result(msg))
            
    def _create_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
            img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse([4, 4, 60, 60], fill="#7C3AED")
            d.text((25, 20), "A", fill="white")
            menu = pystray.Menu(
                pystray.MenuItem("Ouvrir Paramètres (Settings)", lambda: self.root.after(0, lambda: settings_ui.open_settings(self.root))),
                pystray.MenuItem("Afficher Barre de Recherche", lambda: self.root.after(0, self.show)),
                pystray.MenuItem("Quitter AURA", self._quit)
            )
            self.tray = pystray.Icon("AURA", img, "AURA V3", menu)
            threading.Thread(target=self.tray.run, daemon=True).start()
        except:
            pass
            
    def run(self):
        self._create_tray()
        self.root.mainloop()
        
    def _quit(self):
        logger.info("Fermeture totale AURA.")
        try: self.tray.stop()
        except: pass
        from voice import stop_continuous_listening, stop_tts
        stop_continuous_listening()
        stop_tts()
        import sys
        sys.exit(0)
