"""
Componente de consola de registros en vivo para la interfaz gráfica.
Muestra eventos en tiempo real con colores diferenciados por nivel de severidad.
"""

import tkinter as tk
import customtkinter as ctk
from src.core.logger import app_logger
from src.ui.theme import (
    BORDER_COLOR, FONT_MONO, FONT_SMALL, LOG_BG,
    LOG_TEXT_DEBUG, LOG_TEXT_ERROR, LOG_TEXT_INFO,
    LOG_TEXT_SUCCESS, LOG_TEXT_WARNING, TEXT_MUTED
)


class LogConsole(ctk.CTkFrame):
    """Consola visual de registro en tiempo real multilínea."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=LOG_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR, **kwargs)

        # Header de la consola
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(8, 4))

        title = ctk.CTkLabel(
            header_frame,
            text=" Consola de Operaciones en Vivo",
            font=("Segoe UI", 12, "bold"),
            text_color=TEXT_MUTED
        )
        title.pack(side="left")

        clear_btn = ctk.CTkButton(
            header_frame,
            text="Limpiar Consola",
            width=90,
            height=24,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=self.clear_logs
        )
        clear_btn.pack(side="right")

        # Área de texto con scroll
        self.text_area = ctk.CTkTextbox(
            self,
            font=FONT_MONO,
            fg_color="transparent",
            text_color=LOG_TEXT_INFO,
            wrap="word",
            activate_scrollbars=True
        )
        self.text_area.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Configuración de tags de color en el widget nativo subyacente
        self._setup_tags()

        # Registrar este componente en el sistema central de logs
        app_logger.add_listener(self._on_log_received)

    def _setup_tags(self) -> None:
        """Configura los estilos de texto en el widget Tkinter nativo."""
        try:
            tb = self.text_area._textbox
            tb.tag_config("TIME", foreground="#6B7280")
            tb.tag_config("INFO", foreground=LOG_TEXT_INFO)
            tb.tag_config("SUCCESS", foreground=LOG_TEXT_SUCCESS)
            tb.tag_config("WARNING", foreground=LOG_TEXT_WARNING)
            tb.tag_config("ERROR", foreground=LOG_TEXT_ERROR)
            tb.tag_config("DEBUG", foreground=LOG_TEXT_DEBUG)
        except Exception:
            pass

    def _on_log_received(self, timestamp: str, level: str, message: str) -> None:
        """Callback ejecutado cuando se emite un nuevo log desde cualquier hilo."""
        # Se programa la actualización en el hilo principal de Tkinter
        self.after(0, self._append_log, timestamp, level, message)

    def _append_log(self, timestamp: str, level: str, message: str) -> None:
        """Inserta la línea de log formateada en el área de texto."""
        try:
            tb = self.text_area._textbox
            tb.configure(state="normal")
            tb.insert(tk.END, f"[{timestamp}] ", "TIME")
            tb.insert(tk.END, f"[{level:<7}] ", level)
            tb.insert(tk.END, f"{message}\n", level)
            tb.see(tk.END)
            tb.configure(state="disabled")
        except Exception:
            pass

    def clear_logs(self) -> None:
        """Limpia todo el texto de la consola."""
        try:
            tb = self.text_area._textbox
            tb.configure(state="normal")
            tb.delete("1.0", tk.END)
            tb.configure(state="disabled")
        except Exception:
            pass
