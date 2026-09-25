"""
Vista principal (Dashboard) de MySqlAutoBkps.
Presenta tarjetas de métricas, controles rápidos, el árbol jerárquico de servidores y bases de datos,
y la consola de registros en tiempo real con indicador de progreso.
"""

import threading
from typing import Callable, List, Optional
import customtkinter as ctk
from src.core.config import config_manager
from src.core.logger import app_logger
from src.models.manifest import BackupType
from src.models.server import ServerConfig
from src.services.backup_service import BackupService
from src.ui.components.log_console import LogConsole
from src.ui.components.server_tree import ServerTree
from src.ui.components.stats_card import StatsCard
from src.ui.dialogs.server_dialog import ServerDialog
from src.ui.dialogs.workbench_dialog import WorkbenchDialog
from src.ui.theme import (
    ACCENT_PRIMARY, ACCENT_SUCCESS, ACCENT_WARNING,
    BG_CARD, BG_MAIN, BORDER_COLOR, FONT_BODY_BOLD,
    FONT_SMALL, FONT_SUBTITLE, TEXT_MAIN, TEXT_MUTED
)


class DashboardView(ctk.CTkFrame):
    """Vista de control y monitoreo de respaldos."""

    def __init__(self, master, backup_service: BackupService, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.backup_service = backup_service
        self.servers: List[ServerConfig] = []

        self._build_ui()
        self.reload_data()

    def _build_ui(self) -> None:
        """Construye los elementos de la vista."""
        # Barra superior: Título y Botón Principal
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(16, 12))

        title_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(title_frame, text="Panel de Control y Respaldos", font=FONT_SUBTITLE, text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Monitoreo en tiempo real, respaldos completos e incrementales.", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w")

        btn_bar = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_bar.pack(side="right")

        # Botón Respaldar Todo
        self.backup_all_btn = ctk.CTkButton(
            btn_bar,
            text="⚡ Respaldar Todo (Full)",
            width=160,
            height=34,
            font=FONT_SMALL,
            fg_color=ACCENT_SUCCESS,
            hover_color="#059669",
            command=self._on_backup_all_clicked
        )
        self.backup_all_btn.pack(side="left", padx=4)

        # Botón Importar Workbench
        self.import_wb_btn = ctk.CTkButton(
            btn_bar,
            text="🐬 Importar Workbench",
            width=160,
            height=34,
            font=FONT_SMALL,
            fg_color="#0D9488",
            hover_color="#0F766E",
            command=self._on_import_workbench_clicked
        )
        self.import_wb_btn.pack(side="left", padx=4)

        # Botón Añadir Servidor
        self.add_server_btn = ctk.CTkButton(
            btn_bar,
            text="+ Añadir Servidor",
            width=130,
            height=34,
            font=FONT_SMALL,
            fg_color=ACCENT_PRIMARY,
            hover_color="#1D4ED8",
            command=self._on_add_server_clicked
        )
        self.add_server_btn.pack(side="left", padx=4)

        # Barra de Tarjetas Métricas
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=16, pady=(0, 12))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.card_servers = StatsCard(stats_frame, title="Servidores Activos", value="0", subtitle="Configurados", accent_color=ACCENT_PRIMARY)
        self.card_servers.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.card_dbs = StatsCard(stats_frame, title="Bases de Datos", value="0", subtitle="Monitoreadas", accent_color="#3B82F6")
        self.card_dbs.grid(row=0, column=1, sticky="ew", padx=6)

        self.card_backups = StatsCard(stats_frame, title="Respaldos Guardados", value="0", subtitle="Archivos en disco", accent_color=ACCENT_SUCCESS)
        self.card_backups.grid(row=0, column=2, sticky="ew", padx=6)

        self.card_status = StatsCard(stats_frame, title="Último Estado", value="Listo", subtitle="Sistema preparado", accent_color="#10B981")
        self.card_status.grid(row=0, column=3, sticky="ew", padx=(6, 0))

        # Barra de Progreso Indeterminada / Determinada
        self.progress_bar = ctk.CTkProgressBar(self, height=4, fg_color="#1F232B", progress_color=ACCENT_SUCCESS)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 8))

        # Contenedor Principal Dividido: Árbol de Servidores y Consola
        split_container = ctk.CTkFrame(self, fg_color="transparent")
        split_container.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        split_container.grid_rowconfigure(0, weight=3)
        split_container.grid_rowconfigure(1, weight=2)
        split_container.grid_columnconfigure(0, weight=1)

        # 1. Árbol de Servidores y BDs
        self.server_tree = ServerTree(
            split_container,
            on_backup_db=self._on_backup_db,
            on_backup_server=self._on_backup_server,
            on_edit_server=self._on_edit_server,
            on_delete_server=self._on_delete_server,
            on_manage_dbs=self._on_manage_dbs
        )
        self.server_tree.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        # 2. Consola de Logs
        self.log_console = LogConsole(split_container)
        self.log_console.grid(row=1, column=0, sticky="nsew")

    def reload_data(self) -> None:
        """Recarga los servidores desde configuración y actualiza métricas."""
        servers_data = config_manager.load_servers()
        self.servers = [ServerConfig.from_dict(d) for d in servers_data]
        self.server_tree.set_servers(self.servers)

        # Actualizar métricas
        total_dbs = sum(len(s.databases) for s in self.servers)
        manifests = self.backup_service.load_manifests()

        self.card_servers.update_value(str(len(self.servers)), f"{len(self.servers)} registrados")
        self.card_dbs.update_value(str(total_dbs), f"{total_dbs} vinculadas")
        self.card_backups.update_value(str(len(manifests)), f"{len(manifests)} completados")

    def _save_servers(self) -> None:
        """Persiste la lista actual de servidores en la configuración cifrada."""
        config_manager.save_servers([s.to_dict() for s in self.servers])
        self.reload_data()

    def _on_import_workbench_clicked(self) -> None:
        """Abre el asistente de importación desde MySQL Workbench."""
        def on_imported(new_servers: List[ServerConfig]):
            count = 0
            for ns in new_servers:
                existing = next((s for s in self.servers if s.host == ns.host and s.port == ns.port and s.user == ns.user), None)
                if existing:
                    existing.name = ns.name
                    existing.encrypted_password = ns.encrypted_password
                    existing.ssl_enabled = ns.ssl_enabled
                    if ns.databases:
                        existing.databases = ns.databases
                else:
                    self.servers.append(ns)
                    count += 1
            self._save_servers()
            app_logger.success(f"Importación Workbench completada ({count} nuevos servidores).")

        WorkbenchDialog(self.winfo_toplevel(), on_imported_callback=on_imported)

    def _on_add_server_clicked(self) -> None:
        """Abre el diálogo para registrar un servidor nuevo."""
        def on_saved(new_server: ServerConfig):
            self.servers.append(new_server)
            self._save_servers()
            app_logger.success(f"Servidor [{new_server.name}] añadido correctamente.")

        ServerDialog(self.winfo_toplevel(), on_save_callback=on_saved)

    def _on_edit_server(self, server: ServerConfig) -> None:
        """Abre el diálogo para editar un servidor existente."""
        def on_saved(updated_server: ServerConfig):
            idx = next((i for i, s in enumerate(self.servers) if s.id == updated_server.id), None)
            if idx is not None:
                self.servers[idx] = updated_server
                self._save_servers()
                app_logger.success(f"Servidor [{updated_server.name}] actualizado.")

        ServerDialog(self.winfo_toplevel(), server=server, on_save_callback=on_saved)

    def _on_delete_server(self, server: ServerConfig) -> None:
        """Elimina un servidor de la configuración."""
        self.servers = [s for s in self.servers if s.id != server.id]
        self._save_servers()
        app_logger.info(f"Servidor [{server.name}] eliminado.")

    def _on_manage_dbs(self, server: ServerConfig) -> None:
        """Abre el editor para gestionar las bases de datos de un servidor."""
        self._on_edit_server(server)

    def _set_ui_busy(self, busy: bool) -> None:
        """Deshabilita o habilita controles mientras se ejecuta un respaldo."""
        state = "disabled" if busy else "normal"
        self.backup_all_btn.configure(state=state)
        self.add_server_btn.configure(state=state)
        if busy:
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            self.card_status.update_value("Respaldando...", "Operación en curso")
        else:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(0)
            self.card_status.update_value("Listo", "Sin tareas activas")

    def _on_backup_db(self, server: ServerConfig, database_name: str, backup_type_str: str) -> None:
        """Lanza el respaldo de una base de datos en un hilo de fondo."""
        b_type = BackupType.INCREMENTAL if backup_type_str == "INCREMENTAL" else BackupType.FULL

        def worker():
            self._set_ui_busy(True)
            try:
                self.backup_service.backup_database(server, database_name, b_type)
            except Exception as e:
                app_logger.error(f"Error al respaldar [{database_name}]: {e}")
            finally:
                self.after(0, lambda: self._set_ui_busy(False))
                self.after(0, self.reload_data)

        threading.Thread(target=worker, daemon=True).start()

    def _on_backup_server(self, server: ServerConfig, backup_type_str: str) -> None:
        """Lanza el respaldo de todas las BDs de un servidor en un hilo de fondo."""
        b_type = BackupType.INCREMENTAL if backup_type_str == "INCREMENTAL" else BackupType.FULL

        def worker():
            self._set_ui_busy(True)
            try:
                self.backup_service.backup_server(server, b_type)
            except Exception as e:
                app_logger.error(f"Error al respaldar servidor [{server.name}]: {e}")
            finally:
                self.after(0, lambda: self._set_ui_busy(False))
                self.after(0, self.reload_data)

        threading.Thread(target=worker, daemon=True).start()

    def _on_backup_all_clicked(self) -> None:
        """Lanza el respaldo completo de todos los servidores registrados."""
        if not self.servers:
            app_logger.warning("No hay servidores registrados para respaldar.")
            return

        def worker():
            self._set_ui_busy(True)
            app_logger.info("=== Iniciando Respaldo Global de Todos los Servidores ===")
            for s in self.servers:
                try:
                    self.backup_service.backup_server(s, BackupType.FULL)
                except Exception as e:
                    app_logger.error(f"Fallo en servidor [{s.name}]: {e}")
            app_logger.success("=== Respaldo Global Finalizado ===")
            self.after(0, lambda: self._set_ui_busy(False))
            self.after(0, self.reload_data)

        threading.Thread(target=worker, daemon=True).start()
