"""
Vista de Historial y Restauración para MySqlAutoBkps.
Permite explorar los respaldos almacenados, consultar guías paso a paso para phpMyAdmin,
verificar la integridad SHA-256 y abrir la carpeta física de respaldos.
"""

import os
import subprocess
import sys
from typing import List
import customtkinter as ctk
from src.core.logger import app_logger
from src.engine.compressor import StreamCompressor
from src.models.manifest import BackupManifest, BackupType
from src.services.backup_service import BackupService
from src.ui.dialogs.restore_dialog import RestoreDialog
from src.ui.theme import (
    ACCENT_DANGER, ACCENT_PRIMARY, ACCENT_SUCCESS, ACCENT_WARNING,
    BG_CARD, BG_INPUT, BG_MAIN, BORDER_COLOR, FONT_BODY, FONT_BODY_BOLD,
    FONT_MONO, FONT_SMALL, FONT_SUBTITLE, TEXT_DIMMED, TEXT_MAIN, TEXT_MUTED
)


class HistoryView(ctk.CTkFrame):
    """Panel para visualización de historial de respaldos y asistente de restauración."""

    def __init__(self, master, backup_service: BackupService, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.backup_service = backup_service
        self.manifests: List[BackupManifest] = []

        self._build_ui()
        self.reload_manifests()

    def _build_ui(self) -> None:
        """Construye los controles de la vista."""
        # Barra Superior
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(16, 12))

        title_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(title_frame, text="Historial de Respaldos y Restauración", font=FONT_SUBTITLE, text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Inspecciona archivos generados, valida integridad SHA-256 y consulta instrucciones para phpMyAdmin.", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w")

        btn_bar = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_bar.pack(side="right")

        open_folder_btn = ctk.CTkButton(
            btn_bar,
            text="📂 Abrir Carpeta",
            width=130,
            height=34,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=self._open_backups_folder
        )
        open_folder_btn.pack(side="left", padx=4)

        refresh_btn = ctk.CTkButton(
            btn_bar,
            text="🔄 Actualizar",
            width=100,
            height=34,
            font=FONT_SMALL,
            fg_color=ACCENT_PRIMARY,
            hover_color="#1D4ED8",
            command=self.reload_manifests
        )
        refresh_btn.pack(side="left", padx=4)

        # Barra de Filtro / Búsqueda
        filter_bar = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        filter_bar.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(filter_bar, text="🔍", font=FONT_BODY, text_color=TEXT_MUTED).pack(side="left", padx=(12, 6))

        self.search_entry = ctk.CTkEntry(
            filter_bar,
            placeholder_text="Filtrar por servidor, base de datos o nombre de archivo...",
            fg_color="transparent",
            border_width=0,
            font=FONT_BODY
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=4, pady=6)
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_manifests())

        # Contenedor con Scroll de Respaldo
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def reload_manifests(self) -> None:
        """Carga los manifiestos ordenados del más reciente al más antiguo."""
        self.manifests = self.backup_service.load_manifests()
        self.manifests.sort(key=lambda m: m.created_at, reverse=True)
        self._filter_manifests()

    def _filter_manifests(self) -> None:
        """Aplica el filtro de búsqueda sobre los manifiestos."""
        query = self.search_entry.get().strip().lower()
        if not query:
            filtered = self.manifests
        else:
            filtered = [
                m for m in self.manifests
                if query in m.server_name.lower()
                or query in m.database_name.lower()
                or query in m.file_name.lower()
            ]

        self._render_list(filtered)

    def _render_list(self, items: List[BackupManifest]) -> None:
        """Renderiza los elementos filtrados."""
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        if not items:
            empty = ctk.CTkFrame(self.scroll_frame, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
            empty.pack(fill="x", padx=10, pady=20)
            ctk.CTkLabel(empty, text="No se encontraron respaldos registrados", font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(pady=(18, 4))
            ctk.CTkLabel(empty, text="Los respaldos que generes se listarán aquí con sus metadatos.", font=FONT_SMALL, text_color=TEXT_MUTED).pack(pady=(0, 18))
            return

        for manifest in items:
            self._render_manifest_card(manifest)

    def _render_manifest_card(self, manifest: BackupManifest) -> None:
        """Renderiza una tarjeta individual de respaldo."""
        card = ctk.CTkFrame(self.scroll_frame, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="x", padx=6, pady=5)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=10)

        # Badge de Tipo (FULL / INCREMENTAL)
        is_full = manifest.backup_type == BackupType.FULL
        badge_bg = "#064E3B" if is_full else "#78350F"
        badge_fg = ACCENT_SUCCESS if is_full else ACCENT_WARNING
        badge_text = "FULL" if is_full else f"INCR #{manifest.chain_index}"

        badge = ctk.CTkLabel(
            header,
            text=f" {badge_text} ",
            font=("Segoe UI", 10, "bold"),
            fg_color=badge_bg,
            text_color=badge_fg,
            corner_radius=4
        )
        badge.pack(side="left", padx=(0, 10))

        # Información Central
        info = ctk.CTkFrame(header, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(info, text=manifest.file_name, font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(anchor="w")

        size_str = StreamCompressor.format_size(manifest.file_size_bytes)
        sub_text = f"Servidor: {manifest.server_name}  |  BD: {manifest.database_name}  |  Tamaño: {size_str}  |  Fecha: {manifest.created_at}"
        ctk.CTkLabel(info, text=sub_text, font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w")

        # Botones de Acción
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        # Botón Guía phpMyAdmin
        guide_btn = ctk.CTkButton(
            actions,
            text="📖 phpMyAdmin Guía",
            width=135,
            height=28,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=lambda m=manifest: self._open_restore_dialog(m)
        )
        guide_btn.pack(side="left", padx=4)

        # Botón Eliminar
        del_btn = ctk.CTkButton(
            actions,
            text="✕",
            width=28,
            height=28,
            font=FONT_SMALL,
            fg_color="#3B1D22",
            hover_color=ACCENT_DANGER,
            command=lambda m=manifest: self._delete_manifest(m)
        )
        del_btn.pack(side="left", padx=(4, 0))

    def _open_restore_dialog(self, manifest: BackupManifest) -> None:
        """Abre la ventana de detalles y restauración del respaldo."""
        RestoreDialog(self.winfo_toplevel(), manifest=manifest)

    def _delete_manifest(self, manifest: BackupManifest) -> None:
        """Elimina el respaldo físico y su registro."""
        if os.path.exists(manifest.file_path):
            try:
                os.remove(manifest.file_path)
            except Exception as e:
                app_logger.warning(f"No se pudo eliminar el archivo de disco: {e}")

        all_m = self.backup_service.load_manifests()
        remaining = [m for m in all_m if m.backup_id != manifest.backup_id]
        self.backup_service.save_manifests(remaining)

        app_logger.info(f"Respaldo [{manifest.file_name}] eliminado del historial.")
        self.reload_manifests()

    def _open_backups_folder(self) -> None:
        """Abre el directorio de respaldos en el explorador de Windows."""
        folder = os.path.abspath(self.backup_service.backups_dir)
        os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])
