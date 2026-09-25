"""
Ventana principal de la aplicación MySqlAutoBkps con navegación por barra lateral moderna.
Coordina las vistas de Dashboard, Programador, Historial y Configuración.
"""

from typing import Dict
import customtkinter as ctk
from src.core.config import config_manager
from src.core.logger import app_logger
from src.services.backup_service import BackupService
from src.services.scheduler_service import SchedulerService
from src.ui.theme import (
    ACCENT_PRIMARY, BG_CARD, BG_MAIN, BG_SIDEBAR, BORDER_COLOR,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_SUBTITLE,
    FONT_TITLE, TEXT_DIMMED, TEXT_MAIN, TEXT_MUTED
)
from src.ui.views.dashboard_view import DashboardView
from src.ui.views.history_view import HistoryView
from src.ui.views.scheduler_view import SchedulerView
from src.ui.views.settings_view import SettingsView


class MainWindow(ctk.CTk):
    """Ventana principal de la aplicación de escritorio."""

    def __init__(self):
        super().__init__()

        # Configuración de CustomTkinter
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("MySqlAutoBkps - Auto Backuper para MySQL & MariaDB")
        self.geometry("1180x760")
        self.minsize(980, 620)
        self.configure(fg_color=BG_MAIN)

        # Servicios Centrales
        self.backup_service = BackupService()
        self.scheduler_service = SchedulerService()

        # Iniciar scheduler en background
        self.scheduler_service.start()

        # Control de Navegación
        self.views: Dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}

        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        app_logger.info("MySqlAutoBkps iniciado y listo.")

    def _build_layout(self) -> None:
        """Construye la barra lateral de navegación y el contenedor dinámico de vistas."""
        # Contenedor raíz dividido
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 1. Barra Lateral (Sidebar)
        self.sidebar = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, width=240, corner_radius=0, border_width=1, border_color=BORDER_COLOR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Branding / Logo
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=18, pady=(24, 20))

        logo_title = ctk.CTkLabel(
            brand_frame,
            text="🗄️ MySqlAutoBkps",
            font=("Segoe UI", 18, "bold"),
            text_color=TEXT_MAIN
        )
        logo_title.pack(anchor="w")

        version_label = ctk.CTkLabel(
            brand_frame,
            text="v1.0.0 • phpMyAdmin Ready",
            font=FONT_SMALL,
            text_color="#10B981"
        )
        version_label.pack(anchor="w")

        # Separador
        sep = ctk.CTkFrame(self.sidebar, fg_color=BORDER_COLOR, height=1)
        sep.pack(fill="x", padx=16, pady=(0, 16))

        # Botones de Navegación
        self._add_nav_button("dashboard", "📊  Panel de Control", self._show_dashboard)
        self._add_nav_button("scheduler", "⏰  Programador", self._show_scheduler)
        self._add_nav_button("history", "📜  Historial & Restaurar", self._show_history)
        self._add_nav_button("settings", "⚙️  Configuración", self._show_settings)

        # Footer de Sidebar con estado del motor
        sidebar_footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_footer.pack(side="bottom", fill="x", padx=16, pady=16)

        self.engine_status_dot = ctk.CTkLabel(
            sidebar_footer,
            text="● Motor Activo",
            font=FONT_SMALL,
            text_color="#10B981"
        )
        self.engine_status_dot.pack(anchor="w")

        # 2. Contenedor de Vistas (Área Principal)
        self.content_area = ctk.CTkFrame(self, fg_color=BG_MAIN, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")

        # Inicializar vistas
        self.views["dashboard"] = DashboardView(self.content_area, backup_service=self.backup_service)
        self.views["scheduler"] = SchedulerView(self.content_area, scheduler_service=self.scheduler_service)
        self.views["history"] = HistoryView(self.content_area, backup_service=self.backup_service)
        self.views["settings"] = SettingsView(self.content_area)

        # Mostrar por defecto el Dashboard
        self._show_dashboard()

    def _add_nav_button(self, key: str, text: str, command) -> None:
        """Crea un botón estilizado en la barra lateral."""
        btn = ctk.CTkButton(
            self.sidebar,
            text=text,
            anchor="w",
            height=40,
            font=FONT_BODY,
            fg_color="transparent",
            text_color=TEXT_MUTED,
            hover_color="#262C36",
            command=command
        )
        btn.pack(fill="x", padx=12, pady=4)
        self.nav_buttons[key] = btn

    def _set_active_view(self, key: str) -> None:
        """Cambia la vista activa y resalta el botón correspondiente en la sidebar."""
        for v in self.views.values():
            v.pack_forget()

        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color="#2563EB", text_color=TEXT_MAIN, font=FONT_BODY_BOLD)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_MUTED, font=FONT_BODY)

        self.views[key].pack(fill="both", expand=True)

    def _show_dashboard(self) -> None:
        self._set_active_view("dashboard")
        self.views["dashboard"].reload_data()

    def _show_scheduler(self) -> None:
        self._set_active_view("scheduler")
        self.views["scheduler"].reload_jobs()

    def _show_history(self) -> None:
        self._set_active_view("history")
        self.views["history"].reload_manifests()

    def _show_settings(self) -> None:
        self._set_active_view("settings")
        self.views["settings"].load_current_settings()

    def _on_closing(self) -> None:
        """Cierra ordenadamente los hilos de fondo y el planificador."""
        try:
            self.scheduler_service.stop()
        except Exception:
            pass
        self.destroy()
