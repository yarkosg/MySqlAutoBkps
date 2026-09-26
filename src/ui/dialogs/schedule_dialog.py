"""
Diálogo modal para programar tareas automáticas de respaldo (BackupJob).
Permite configurar frecuencia por intervalos o expresiones cron, tipo Full o Incremental.
"""

from typing import Callable, List, Optional
import customtkinter as ctk
from src.models.backup_job import BackupJob
from src.models.manifest import BackupType
from src.models.server import ServerConfig
from src.services.windows_scheduler_service import WindowsSchedulerService
from src.ui.theme import (
    ACCENT_PRIMARY, ACCENT_SUCCESS, BG_CARD, BG_INPUT,
    BG_MAIN, BORDER_COLOR, FONT_BODY_BOLD, FONT_SMALL,
    FONT_SUBTITLE, TEXT_MAIN, TEXT_MUTED
)


class ScheduleDialog(ctk.CTkToplevel):
    """Modal para programar una nueva tarea recurrente."""

    def __init__(
        self,
        master,
        servers: List[ServerConfig],
        job: Optional[BackupJob] = None,
        on_save_callback: Optional[Callable[[BackupJob], None]] = None
    ):
        super().__init__(master)
        self.servers = servers
        self.job = job
        self.on_save_callback = on_save_callback

        self.title("Programar Tarea Automática" if not job else "Editar Tarea Programada")
        self.geometry("540x580")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)
        self.grab_set()

        self._build_ui()
        if job:
            self._populate_fields(job)

    def _build_ui(self) -> None:
        """Construye los controles de programación."""
        # 1. PIE DE VENTANA ANCLADO PRIMERO
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=24, pady=(10, 16))

        cancel_btn = ctk.CTkButton(footer, text="Cancelar", width=100, height=36, fg_color="#2D333F", hover_color="#374151", command=self.destroy)
        cancel_btn.pack(side="right", padx=(10, 0))

        save_btn = ctk.CTkButton(footer, text="💾 Guardar Tarea", width=140, height=36, font=FONT_BODY_BOLD, fg_color=ACCENT_SUCCESS, hover_color="#059669", command=self._save)
        save_btn.pack(side="right")

        # 2. ENCABEZADO
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=24, pady=(20, 10))

        title_text = " Editar Tarea Programada" if self.job else " Nueva Tarea de Respaldo Automático"
        ctk.CTkLabel(header, text=title_text, font=FONT_SUBTITLE, text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Configura la periodicidad y tipo de copia para ejecución en segundo plano.",
            font=FONT_SMALL,
            text_color=TEXT_MUTED
        ).pack(anchor="w")

        # 3. FORMULARIO CON SCROLL
        form_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form_scroll.pack(side="top", fill="both", expand=True, padx=24, pady=(0, 10))

        form = ctk.CTkFrame(form_scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        form.pack(fill="both", expand=True)

        # Nombre de la Tarea
        ctk.CTkLabel(form, text="Nombre Descriptivo de la Tarea:", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(14, 2))
        self.name_entry = ctk.CTkEntry(form, placeholder_text="Ej: Respaldo Nocturno Diario", fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.name_entry.pack(fill="x", padx=16, pady=(0, 10))

        # Selección de Servidor
        ctk.CTkLabel(form, text="Servidor Destino:", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 2))
        server_names = [f"{s.name} ({s.host})" for s in self.servers] if self.servers else ["No hay servidores"]
        self.server_combo = ctk.CTkComboBox(form, values=server_names, fg_color=BG_INPUT, border_color=BORDER_COLOR, command=self._on_server_selected)
        self.server_combo.pack(fill="x", padx=16, pady=(0, 10))

        # Selección de Base de Datos
        ctk.CTkLabel(form, text="Base de Datos:", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 2))
        self.db_combo = ctk.CTkComboBox(form, values=["[Todas las bases de datos]"], fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.db_combo.pack(fill="x", padx=16, pady=(0, 10))

        # Tipo de Respaldo
        ctk.CTkLabel(form, text="Tipo de Respaldo:", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 2))
        self.type_combo = ctk.CTkComboBox(form, values=["FULL (Completo 100%)", "INCREMENTAL (Solo cambios)"], fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.type_combo.pack(fill="x", padx=16, pady=(0, 10))

        # Frecuencia
        ctk.CTkLabel(form, text="Frecuencia de Ejecución:", font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 2))
        self.freq_combo = ctk.CTkComboBox(
            form,
            values=[
                "Cada 6 Horas",
                "Cada 12 Horas",
                "Diario (Cada 24 Horas)",
                "Semanal (Cada 7 Días)",
                "Personalizado (Minutos)",
                "Expresión Cron Personalizada"
            ],
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            command=self._on_freq_selected
        )
        self.freq_combo.set("Diario (Cada 24 Horas)")
        self.freq_combo.pack(fill="x", padx=16, pady=(0, 10))

        # Campo personalizado (minutos o cron)
        self.custom_entry = ctk.CTkEntry(form, placeholder_text="Minutos o expresión cron", fg_color=BG_INPUT, border_color=BORDER_COLOR)

        # Hora de ejecución fija
        self.time_row = ctk.CTkFrame(form, fg_color="transparent")
        self.time_row.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(self.time_row, text="Hora programada (Formato 24h ej: 02:00, 23:30):", font=FONT_SMALL, text_color=TEXT_MUTED).pack(side="left")
        self.time_entry = ctk.CTkEntry(self.time_row, width=90, placeholder_text="02:00", fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.time_entry.insert(0, "02:00")
        self.time_entry.pack(side="right")

        # Integración con Windows Task Scheduler
        self.windows_task_chk = ctk.CTkCheckBox(
            form,
            text="🪟 Instalar como Tarea de Windows (Windows Task Scheduler)\n    Se ejecutará automáticamente en segundo plano aunque este programa esté cerrado",
            font=FONT_SMALL,
            fg_color="#10B981"
        )
        self.windows_task_chk.select()
        self.windows_task_chk.pack(anchor="w", padx=16, pady=(4, 10))

        # Activar/Desactivar
        self.active_check = ctk.CTkCheckBox(form, text="Tarea Activa y Habilitada", font=FONT_SMALL, fg_color=ACCENT_PRIMARY)
        self.active_check.select()
        self.active_check.pack(anchor="w", padx=16, pady=(4, 14))

        if self.servers:
            self._update_db_choices(self.servers[0])

    def _on_server_selected(self, choice: str) -> None:
        """Actualiza la lista de BDs al cambiar el servidor."""
        selected_server = self._get_selected_server()
        if selected_server:
            self._update_db_choices(selected_server)

    def _get_selected_server(self) -> Optional[ServerConfig]:
        """Obtiene el ServerConfig correspondiente a la selección del combo."""
        val = self.server_combo.get()
        for s in self.servers:
            if f"{s.name} ({s.host})" == val:
                return s
        return self.servers[0] if self.servers else None

    def _update_db_choices(self, server: ServerConfig) -> None:
        """Llena el combo de bases de datos según el servidor elegido."""
        db_names = ["[Todas las bases de datos]"] + [db.name for db in server.databases]
        self.db_combo.configure(values=db_names)
        self.db_combo.set("[Todas las bases de datos]")

    def _on_freq_selected(self, choice: str) -> None:
        """Muestra u oculta el campo personalizado según la selección."""
        if "Personalizado" in choice or "Cron" in choice:
            self.custom_entry.pack(fill="x", padx=16, pady=(0, 10))
            if "Cron" in choice:
                self.custom_entry.configure(placeholder_text="Ej: 0 2 * * * (Todos los días a las 02:00 AM)")
            else:
                self.custom_entry.configure(placeholder_text="Intervalo en minutos (ej: 120)")
        else:
            self.custom_entry.pack_forget()

    def _populate_fields(self, job: BackupJob) -> None:
        """Carga datos de un trabajo existente."""
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, job.name)

        # Buscar y setear servidor
        for s in self.servers:
            if s.id == job.server_id:
                self.server_combo.set(f"{s.name} ({s.host})")
                self._update_db_choices(s)
                break

        if job.database_name == "__ALL__":
            self.db_combo.set("[Todas las bases de datos]")
        else:
            self.db_combo.set(job.database_name)

        if job.backup_type == BackupType.INCREMENTAL:
            self.type_combo.set("INCREMENTAL (Solo cambios)")
        else:
            self.type_combo.set("FULL (Completo 100%)")

        if job.start_time_str:
            self.time_entry.delete(0, "end")
            self.time_entry.insert(0, job.start_time_str)

        if job.windows_task_installed or WindowsSchedulerService.is_task_installed(job.id):
            self.windows_task_chk.select()
        else:
            self.windows_task_chk.deselect()

        if not job.is_active:
            self.active_check.deselect()

    def _save(self) -> None:
        """Guarda la tarea programada y la registra en Windows Task Scheduler si corresponde."""
        server = self._get_selected_server()
        if not server:
            return

        name = self.name_entry.get().strip() or "Tarea de Respaldo"
        selected_db = self.db_combo.get()
        db_name = "__ALL__" if selected_db == "[Todas las bases de datos]" else selected_db

        raw_type = self.type_combo.get()
        b_type = BackupType.INCREMENTAL if "INCREMENTAL" in raw_type else BackupType.FULL

        freq = self.freq_combo.get()
        interval_min = 1440
        cron_expr = None

        if "6 Horas" in freq:
            interval_min = 360
        elif "12 Horas" in freq:
            interval_min = 720
        elif "Diario" in freq:
            interval_min = 1440
        elif "Semanal" in freq:
            interval_min = 10080
        elif "Personalizado" in freq:
            try:
                interval_min = int(self.custom_entry.get().strip())
            except ValueError:
                interval_min = 60
        elif "Cron" in freq:
            cron_expr = self.custom_entry.get().strip() or "0 2 * * *"

        is_active = bool(self.active_check.get())
        start_time = self.time_entry.get().strip() or "02:00"
        should_install_windows = bool(self.windows_task_chk.get())

        job_id = self.job.id if self.job else None
        job = BackupJob(
            name=name,
            server_id=server.id,
            database_name=db_name,
            backup_type=b_type,
            interval_minutes=interval_min,
            cron_expression=cron_expr,
            is_active=is_active,
            windows_task_installed=should_install_windows,
            start_time_str=start_time
        )
        if job_id:
            job.id = job_id

        # Gestionar instalación/desinstalación en Windows Task Scheduler
        if should_install_windows and job.is_active:
            ok, msg = WindowsSchedulerService.install_job(job)
            if not ok:
                app_logger.warning(f"Aviso al instalar en Windows: {msg}")
        else:
            if self.job and (self.job.windows_task_installed or WindowsSchedulerService.is_task_installed(self.job.id)):
                WindowsSchedulerService.uninstall_job(job.id)

        if self.on_save_callback:
            self.on_save_callback(job)

        self.destroy()
