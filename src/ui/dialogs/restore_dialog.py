"""
Diálogo modal para inspección de respaldos y guía de restauración para phpMyAdmin.
Incluye verificación de integridad SHA-256 en vivo y apertura de la carpeta en el explorador.
"""

import hashlib
import os
import subprocess
import sys
import customtkinter as ctk
from src.engine.compressor import StreamCompressor
from src.models.manifest import BackupManifest, BackupType
from src.services.backup_service import BackupService
from src.ui.theme import (
    ACCENT_PRIMARY, ACCENT_SUCCESS, BG_CARD, BG_INPUT,
    BG_MAIN, BORDER_COLOR, FONT_BODY, FONT_BODY_BOLD,
    FONT_MONO, FONT_SMALL, FONT_SUBTITLE, TEXT_MAIN, TEXT_MUTED
)


class RestoreDialog(ctk.CTkToplevel):
    """Modal de inspección y guía de restauración."""

    def __init__(self, master, manifest: BackupManifest):
        super().__init__(master)
        self.manifest = manifest

        self.title(f"Detalles de Respaldo - {manifest.file_name}")
        self.geometry("680x640")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)
        self.grab_set()

        self._build_ui()

    def _build_ui(self) -> None:
        """Construye la vista de detalles y restauración."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))

        badge_color = ACCENT_SUCCESS if self.manifest.backup_type == BackupType.FULL else "#F59E0B"
        ctk.CTkLabel(
            header,
            text=f"📦 {self.manifest.file_name}",
            font=FONT_SUBTITLE,
            text_color=TEXT_MAIN
        ).pack(anchor="w")

        sub_info = f"Tipo: {self.manifest.backup_type.value}  |  Servidor: {self.manifest.server_name}  |  BD: {self.manifest.database_name}  |  Fecha: {self.manifest.created_at}"
        ctk.CTkLabel(header, text=sub_info, font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w")

        # Metadatos Card
        meta_card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        meta_card.pack(fill="x", padx=24, pady=10)

        size_str = StreamCompressor.format_size(self.manifest.file_size_bytes)
        row1 = f"Tamaño: {size_str}  |  Compresión: {self.manifest.compression}  |  Duración de volcado: {self.manifest.execution_duration_sec}s"
        ctk.CTkLabel(meta_card, text=row1, font=FONT_SMALL, text_color=TEXT_MAIN).pack(anchor="w", padx=16, pady=(10, 4))

        hash_text = f"Hash SHA-256: {self.manifest.checksum_sha256}"
        ctk.CTkLabel(meta_card, text=hash_text, font=FONT_MONO, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 6))

        # Botones de verificación de hash y explorador
        actions_bar = ctk.CTkFrame(meta_card, fg_color="transparent")
        actions_bar.pack(fill="x", padx=16, pady=(0, 10))

        verify_btn = ctk.CTkButton(
            actions_bar,
            text="🛡️ Verificar Integridad SHA-256",
            width=180,
            height=28,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=self._verify_sha256
        )
        verify_btn.pack(side="left", padx=(0, 8))

        open_folder_btn = ctk.CTkButton(
            actions_bar,
            text="📂 Abrir en Explorador",
            width=150,
            height=28,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=self._open_in_explorer
        )
        open_folder_btn.pack(side="left")

        self.verify_result_lbl = ctk.CTkLabel(meta_card, text="", font=FONT_SMALL)
        self.verify_result_lbl.pack(anchor="w", padx=16, pady=(0, 8))

        # Guía para phpMyAdmin
        guide_label = ctk.CTkLabel(self, text="Instrucciones paso a paso para restaurar en phpMyAdmin:", font=FONT_BODY_BOLD, text_color=TEXT_MAIN)
        guide_label.pack(anchor="w", padx=24, pady=(6, 2))

        instructions_box = ctk.CTkTextbox(
            self,
            font=FONT_MONO,
            fg_color=BG_INPUT,
            border_width=1,
            border_color=BORDER_COLOR,
            wrap="word"
        )
        instructions_box.pack(fill="both", expand=True, padx=24, pady=(0, 14))

        instructions_text = BackupService.generate_phpmyadmin_restore_instructions(self.manifest)
        instructions_box.insert("1.0", instructions_text)
        instructions_box.configure(state="disabled")

        # Botón Cerrar
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(0, 20))

        close_btn = ctk.CTkButton(
            footer,
            text="Cerrar",
            width=100,
            height=36,
            fg_color=ACCENT_PRIMARY,
            hover_color="#1D4ED8",
            command=self.destroy
        )
        close_btn.pack(side="right")

    def _verify_sha256(self) -> None:
        """Verifica en vivo que el archivo no haya sido corrompido ni modificado."""
        if not os.path.exists(self.manifest.file_path):
            self.verify_result_lbl.configure(text="✕ El archivo físico no existe en disco.", text_color="#EF4444")
            return

        self.verify_result_lbl.configure(text="Calculando hash...", text_color=TEXT_MUTED)
        self.update_idletasks()

        hasher = hashlib.sha256()
        with open(self.manifest.file_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                hasher.update(chunk)

        computed = hasher.hexdigest()
        if computed == self.manifest.checksum_sha256:
            self.verify_result_lbl.configure(text="✓ Integridad verificada al 100%: El archivo coincide exactamente con el hash original.", text_color=ACCENT_SUCCESS)
        else:
            self.verify_result_lbl.configure(text="✕ Alerta: El hash no coincide. El archivo pudo haber sido modificado o dañado.", text_color="#EF4444")

    def _open_in_explorer(self) -> None:
        """Abre la carpeta del archivo en el explorador de Windows."""
        if os.path.exists(self.manifest.file_path):
            if sys.platform == "win32":
                subprocess.Popen(f'explorer /select,"{os.path.abspath(self.manifest.file_path)}"')
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(self.manifest.file_path)])
