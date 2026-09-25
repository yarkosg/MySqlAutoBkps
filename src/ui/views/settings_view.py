"""
Vista de Configuración General de MySqlAutoBkps.
Permite configurar rutas de binarios, carpeta de destino de respaldos,
políticas de retención automática y parámetros de compresión.
"""

import os
from tkinter import filedialog
import customtkinter as ctk
from src.core.config import config_manager
from src.core.logger import app_logger
from src.engine.detector import BinaryDetector
from src.ui.theme import (
    ACCENT_PRIMARY, ACCENT_SUCCESS, BG_CARD, BG_INPUT,
    BG_MAIN, BORDER_COLOR, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_SUBTITLE, TEXT_MAIN, TEXT_MUTED
)


class SettingsView(ctk.CTkFrame):
    """Panel de configuración de parámetros del sistema."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._build_ui()
        self.load_current_settings()

    def _build_ui(self) -> None:
        """Construye los controles de la vista."""
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(16, 12))

        title_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(title_frame, text="Configuración del Sistema", font=FONT_SUBTITLE, text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Ajusta los motores de volcado, carpetas de almacenamiento y compresión.", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w")

        right_bar = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_bar.pack(side="right")

        self.save_status_lbl = ctk.CTkLabel(right_bar, text="", font=FONT_SMALL, text_color=ACCENT_SUCCESS)
        self.save_status_lbl.pack(side="left", padx=(0, 10))

        # Botón Guardar
        save_btn = ctk.CTkButton(
            right_bar,
            text="💾 Guardar Cambios",
            width=140,
            height=34,
            font=FONT_SMALL,
            fg_color=ACCENT_SUCCESS,
            hover_color="#059669",
            command=self.save_settings
        )
        save_btn.pack(side="left")

        # Contenedor con Scroll de Configuración
        form = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # 1. Tarjeta: Ejecutables MySQL / MariaDB
        card_bins = ctk.CTkFrame(form, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        card_bins.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(card_bins, text="Motores de Extracción de Respaldo", font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(card_bins, text="Elige si deseas usar el motor nativo de Python (cero dependencias locales) o binarios externos.", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        # Selector de Motor
        ctk.CTkLabel(card_bins, text="Motor de Respaldo Predeterminado:", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 2))
        self.engine_mode_combo = ctk.CTkComboBox(
            card_bins,
            values=[
                "Nativo Puro Python (Recomendado - 100% autónomo, sin MySQL local)",
                "CLI mysqldump (Requiere MySQL instalado en la laptop)"
            ],
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR
        )
        self.engine_mode_combo.set("Nativo Puro Python (Recomendado - 100% autónomo, sin MySQL local)")
        self.engine_mode_combo.pack(fill="x", padx=16, pady=(0, 12))

        # mysqldump
        ctk.CTkLabel(card_bins, text="Ruta a mysqldump / mariadb-dump (Opcional si usas CLI):", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 2))
        row_dump = ctk.CTkFrame(card_bins, fg_color="transparent")
        row_dump.pack(fill="x", padx=16, pady=(0, 10))

        self.dump_entry = ctk.CTkEntry(row_dump, placeholder_text="Auto-detectado si se deja en blanco", fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.dump_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(row_dump, text="Examinar...", width=80, height=28, font=FONT_SMALL, fg_color="#2D333F", hover_color="#374151", command=self._browse_dump).pack(side="left", padx=2)
        ctk.CTkButton(row_dump, text="Auto-detectar", width=95, height=28, font=FONT_SMALL, fg_color=ACCENT_PRIMARY, hover_color="#1D4ED8", command=self._autodetect_dump).pack(side="left", padx=2)

        # mysqlbinlog
        ctk.CTkLabel(card_bins, text="Ruta a mysqlbinlog / mariadb-binlog (para respaldos incrementales):", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 2))
        row_binlog = ctk.CTkFrame(card_bins, fg_color="transparent")
        row_binlog.pack(fill="x", padx=16, pady=(0, 14))

        self.binlog_entry = ctk.CTkEntry(row_binlog, placeholder_text="Auto-detectado si se deja en blanco", fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.binlog_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(row_binlog, text="Examinar...", width=80, height=28, font=FONT_SMALL, fg_color="#2D333F", hover_color="#374151", command=self._browse_binlog).pack(side="left", padx=2)
        ctk.CTkButton(row_binlog, text="Auto-detectar", width=95, height=28, font=FONT_SMALL, fg_color=ACCENT_PRIMARY, hover_color="#1D4ED8", command=self._autodetect_binlog).pack(side="left", padx=2)

        # 2. Tarjeta: Almacenamiento y Carpetas
        card_storage = ctk.CTkFrame(form, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        card_storage.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(card_storage, text="Directorio de Almacenamiento de Respaldos", font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(card_storage, text="Ubicación local o unidad en red donde se guardarán los volcados generados.", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        row_dir = ctk.CTkFrame(card_storage, fg_color="transparent")
        row_dir.pack(fill="x", padx=16, pady=(0, 14))

        self.dir_entry = ctk.CTkEntry(row_dir, fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(row_dir, text="Examinar...", width=80, height=28, font=FONT_SMALL, fg_color="#2D333F", hover_color="#374151", command=self._browse_dir).pack(side="left")

        # 3. Tarjeta: Políticas de Retención
        card_retention = ctk.CTkFrame(form, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        card_retention.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(card_retention, text="Políticas de Retención Automática", font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(card_retention, text="Depura automáticamente archivos de respaldo obsoletos para ahorrar espacio en disco.", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        ret_grid = ctk.CTkFrame(card_retention, fg_color="transparent")
        ret_grid.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkLabel(ret_grid, text="Días máximos de antigüedad (0 para deshabilitar):", font=FONT_SMALL, text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.days_entry = ctk.CTkEntry(ret_grid, width=120, fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.days_entry.grid(row=1, column=0, sticky="w", pady=(0, 10))

        ctk.CTkLabel(ret_grid, text="Máximo de versiones a conservar por base de datos:", font=FONT_SMALL, text_color=TEXT_MUTED).grid(row=0, column=1, sticky="w", padx=(20, 0), pady=(0, 2))
        self.versions_entry = ctk.CTkEntry(ret_grid, width=120, fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.versions_entry.grid(row=1, column=1, sticky="w", padx=(20, 0), pady=(0, 10))

        # 4. Tarjeta: Compresión y Rendimiento
        card_comp = ctk.CTkFrame(form, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        card_comp.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(card_comp, text="Compresión de Archivos (.sql.gz)", font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(card_comp, text="Comprime los respaldos al vuelo durante el volcado (compatible de forma nativa con phpMyAdmin).", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        self.comp_switch = ctk.CTkSwitch(card_comp, text="Habilitar compresión Gzip en streaming (.sql.gz)", font=FONT_SMALL, fg_color=ACCENT_PRIMARY)
        self.comp_switch.select()
        self.comp_switch.pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkLabel(card_comp, text="Nivel de compresión (1 = Más rápido, 9 = Máxima compresión):", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 2))
        self.comp_slider = ctk.CTkSlider(card_comp, from_=1, to=9, number_of_steps=8, width=280)
        self.comp_slider.set(6)
        self.comp_slider.pack(anchor="w", padx=16, pady=(0, 14))

    def load_current_settings(self) -> None:
        """Carga las preferencias almacenadas y auto-detecta rutas si están vacías."""
        settings = config_manager.load_settings()

        dump_path = settings.get("mysqldump_path") or BinaryDetector.get_mysqldump_path() or ""
        self.dump_entry.delete(0, "end")
        self.dump_entry.insert(0, dump_path)

        binlog_path = settings.get("mysqlbinlog_path") or BinaryDetector.get_mysqlbinlog_path() or ""
        self.binlog_entry.delete(0, "end")
        self.binlog_entry.insert(0, binlog_path)

        backups_dir = settings.get("backups_dir") or os.path.abspath("backups")
        self.dir_entry.delete(0, "end")
        self.dir_entry.insert(0, backups_dir)

        days = str(settings.get("default_retention_days", 30))
        self.days_entry.delete(0, "end")
        self.days_entry.insert(0, days)

        versions = str(settings.get("default_max_versions", 10))
        self.versions_entry.delete(0, "end")
        self.versions_entry.insert(0, versions)

        mode = settings.get("dump_engine_mode", "native")
        if mode == "mysqldump":
            self.engine_mode_combo.set("CLI mysqldump (Requiere MySQL instalado en la laptop)")
        else:
            self.engine_mode_combo.set("Nativo Puro Python (Recomendado - 100% autónomo, sin MySQL local)")

        if settings.get("compression_enabled", True):
            self.comp_switch.select()
        else:
            self.comp_switch.deselect()

        comp_level = settings.get("compression_level", 6)
        self.comp_slider.set(comp_level)

    def save_settings(self) -> None:
        """Guarda los cambios ingresados por el usuario."""
        try:
            days = int(self.days_entry.get().strip() or "30")
        except ValueError:
            days = 30

        try:
            versions = int(self.versions_entry.get().strip() or "10")
        except ValueError:
            versions = 10

        chosen_mode = "mysqldump" if "mysqldump" in self.engine_mode_combo.get() else "native"

        new_settings = {
            "app_theme": "dark",
            "dump_engine_mode": chosen_mode,
            "mysqldump_path": self.dump_entry.get().strip(),
            "mysqlbinlog_path": self.binlog_entry.get().strip(),
            "backups_dir": self.dir_entry.get().strip(),
            "default_retention_days": days,
            "default_max_versions": versions,
            "compression_enabled": bool(self.comp_switch.get()),
            "compression_level": int(self.comp_slider.get()),
            "notifications_enabled": True,
            "auto_start_scheduler": False
        }

        config_manager.save_settings(new_settings)
        app_logger.success(f"Preferencias guardadas (Motor activo: {chosen_mode}).")
        self.save_status_lbl.configure(text="✓ Cambios guardados exitosamente")
        self.after(4000, lambda: self.save_status_lbl.configure(text=""))

    def _browse_dump(self) -> None:
        """Abre explorador para seleccionar mysqldump."""
        path = filedialog.askopenfilename(
            title="Seleccionar ejecutable mysqldump o mariadb-dump",
            filetypes=[("Ejecutables", "*.exe"), ("Todos los archivos", "*.*")]
        )
        if path:
            self.dump_entry.delete(0, "end")
            self.dump_entry.insert(0, path)

    def _autodetect_dump(self) -> None:
        """Fuerza auto-detección de mysqldump."""
        found = BinaryDetector.get_mysqldump_path()
        if found:
            self.dump_entry.delete(0, "end")
            self.dump_entry.insert(0, found)
            app_logger.success(f"mysqldump detectado en: {found}")
        else:
            app_logger.warning("No se pudo detectar mysqldump automáticamente.")

    def _browse_binlog(self) -> None:
        """Abre explorador para seleccionar mysqlbinlog."""
        path = filedialog.askopenfilename(
            title="Seleccionar ejecutable mysqlbinlog",
            filetypes=[("Ejecutables", "*.exe"), ("Todos los archivos", "*.*")]
        )
        if path:
            self.binlog_entry.delete(0, "end")
            self.binlog_entry.insert(0, path)

    def _autodetect_binlog(self) -> None:
        """Fuerza auto-detección de mysqlbinlog."""
        found = BinaryDetector.get_mysqlbinlog_path()
        if found:
            self.binlog_entry.delete(0, "end")
            self.binlog_entry.insert(0, found)
            app_logger.success(f"mysqlbinlog detectado en: {found}")
        else:
            app_logger.warning("No se pudo detectar mysqlbinlog automáticamente.")

    def _browse_dir(self) -> None:
        """Abre explorador para seleccionar directorio de respaldos."""
        folder = filedialog.askdirectory(title="Seleccionar Carpeta para Respaldos")
        if folder:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, folder)
