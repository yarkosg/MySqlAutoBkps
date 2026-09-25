"""
Componente de tarjeta métrica para resumen de estado en el panel principal.
"""

import customtkinter as ctk
from src.ui.theme import (
    BORDER_COLOR, BG_CARD, FONT_SMALL, FONT_TITLE,
    FONT_BODY_BOLD, TEXT_MAIN, TEXT_MUTED
)


class StatsCard(ctk.CTkFrame):
    """Tarjeta individual que muestra una métrica clave del sistema."""

    def __init__(self, master, title: str, value: str = "0", subtitle: str = "", accent_color: str = "#2563EB", **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR, **kwargs)

        self.title_label = ctk.CTkLabel(
            self,
            text=title.upper(),
            font=("Segoe UI", 10, "bold"),
            text_color=TEXT_MUTED
        )
        self.title_label.pack(anchor="w", padx=14, pady=(12, 2))

        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=FONT_TITLE,
            text_color=accent_color
        )
        self.value_label.pack(anchor="w", padx=14, pady=(0, 2))

        if subtitle:
            self.subtitle_label = ctk.CTkLabel(
                self,
                text=subtitle,
                font=FONT_SMALL,
                text_color=TEXT_MUTED
            )
            self.subtitle_label.pack(anchor="w", padx=14, pady=(0, 10))

    def update_value(self, new_value: str, subtitle: str = "") -> None:
        """Actualiza el valor numérico y subtítulo de la tarjeta."""
        self.value_label.configure(text=new_value)
        if subtitle and hasattr(self, "subtitle_label"):
            self.subtitle_label.configure(text=subtitle)
