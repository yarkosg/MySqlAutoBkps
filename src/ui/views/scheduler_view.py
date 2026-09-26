"""
Vista de Gestión del Planificador de Tareas Automáticas (Scheduler) para MySqlAutoBkps.
Permite programar copias recurrentes desatendidas, monitorear próximas ejecuciones,
activar/desactivar jobs y administrarlas tanto en la app como en el Programador de Tareas de Windows.
"""

import threading
from typing import List
import customtkinter as ctk
from src.core.config import config_manager
from src.core.logger import app_logger
from src.models.backup_job import BackupJob
from src.models.server import ServerConfig
from src.services.scheduler_service import SchedulerService
from src.services.windows_scheduler_service import WindowsSchedulerService
from src.ui.dialogs.schedule_dialog import ScheduleDialog
from src.ui.theme import (
    ACCENT_DANGER, ACCENT_PRIMARY, ACCENT_SUCCESS, ACCENT_WARNING,
    BG_CARD, BG_MAIN, BORDER_COLOR, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_SUBTITLE, TEXT_DIMMED, TEXT_MAIN, TEXT_MUTED
)


class SchedulerView(ctk.CTkFrame):
    """Panel de administración de tareas periódicas desatendidas y tareas del sistema Windows."""

    def __init__(self, master, scheduler_service: SchedulerService, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.scheduler_service = scheduler_service
        self.jobs: List[BackupJob] = []

        self._build_ui()
        self.reload_jobs()

    def _build_ui(self) -> None:
        """Construye la interfaz de la vista."""
        # Barra Superior
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(16, 12))

        title_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(title_frame, text="Planificador de Respaldos Automáticos", font=FONT_SUBTITLE, text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(
            title_frame,
            text="Automatiza copias periódicas. Funciona en Windows incluso con la app cerrada.",
            font=FONT_SMALL,
            text_color=TEXT_MUTED
        ).pack(anchor="w")

        btn_bar = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_bar.pack(side="right")

        # Botón Sincronizar con Windows
        self.sync_win_btn = ctk.CTkButton(
            btn_bar,
            text="🪟 Sincronizar Windows",
            width=150,
            height=34,
            font=FONT_SMALL,
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._sync_with_windows
        )
        self.sync_win_btn.pack(side="left", padx=4)

        # Botón de Estado del Motor en App (Iniciar / Detener)
        self.toggle_engine_btn = ctk.CTkButton(
            btn_bar,
            text="⏸️ Detener Motor",
            width=135,
            height=34,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=self._toggle_engine
        )
        self.toggle_engine_btn.pack(side="left", padx=4)

        # Botón Nueva Tarea
        self.add_job_btn = ctk.CTkButton(
            btn_bar,
            text="+ Programar Tarea",
            width=145,
            height=34,
            font=FONT_SMALL,
            fg_color=ACCENT_PRIMARY,
            hover_color="#1D4ED8",
            command=self._on_add_job_clicked
        )
        self.add_job_btn.pack(side="left", padx=4)

        # Contenedor de Lista de Tareas
        self.jobs_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.jobs_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def reload_jobs(self) -> None:
        """Carga las tareas desde disco, sincroniza con Windows y las renderiza."""
        self.jobs = self.scheduler_service.load_jobs()
        # Verificar estado real de Windows Task Scheduler
        WindowsSchedulerService.sync_jobs_with_windows(self.jobs)
        self._update_engine_button_state()
        self._render_jobs_list()

    def _sync_with_windows(self) -> None:
        """Fuerza la sincronización con las tareas registradas en Windows Task Scheduler."""
        WindowsSchedulerService.sync_jobs_with_windows(self.jobs)
        # Guardar estados actualizados
        for job in self.jobs:
            self.scheduler_service.add_or_update_job(job)
        self._render_jobs_list()
        app_logger.success("Estado de tareas sincronizado con el Programador de Tareas de Windows.")

    def _update_engine_button_state(self) -> None:
        """Actualiza el texto y color del botón del motor del planificador."""
        if self.scheduler_service.is_running():
            self.toggle_engine_btn.configure(
                text="⏸️ Motor App Activo",
                fg_color="#374151",
                hover_color="#4B5563"
            )
        else:
            self.toggle_engine_btn.configure(
                text="▶️ Iniciar Motor App",
                fg_color=ACCENT_SUCCESS,
                hover_color="#059669"
            )

    def _toggle_engine(self) -> None:
        """Inicia o detiene el planificador interno de la aplicación."""
        if self.scheduler_service.is_running():
            self.scheduler_service.stop()
        else:
            self.scheduler_service.start()
        self._update_engine_button_state()

    def _on_add_job_clicked(self) -> None:
        """Abre el diálogo para crear una tarea nueva."""
        servers = self._get_registered_servers()
        if not servers:
            app_logger.warning("Primero debes registrar al menos un servidor para poder programar respaldos.")
            return

        def on_saved(new_job: BackupJob):
            self.scheduler_service.add_or_update_job(new_job)
            app_logger.success(f"Tarea programada [{new_job.name}] guardada exitosamente.")
            self.reload_jobs()

        ScheduleDialog(self.winfo_toplevel(), servers=servers, on_save_callback=on_saved)

    def _on_edit_job_clicked(self, job: BackupJob) -> None:
        """Abre el diálogo para modificar una tarea existente."""
        servers = self._get_registered_servers()
        if not servers:
            app_logger.warning("No hay servidores configurados.")
            return

        def on_saved(updated_job: BackupJob):
            self.scheduler_service.add_or_update_job(updated_job)
            app_logger.success(f"Tarea [{updated_job.name}] modificada exitosamente.")
            self.reload_jobs()

        ScheduleDialog(self.winfo_toplevel(), servers=servers, job=job, on_save_callback=on_saved)

    def _get_registered_servers(self) -> List[ServerConfig]:
        """Recupera la lista de servidores configurados."""
        servers_data = config_manager.load_servers()
        return [ServerConfig.from_dict(d) for d in servers_data]

    def _render_jobs_list(self) -> None:
        """Dibuja las tarjetas de tareas en el scroll."""
        for widget in self.jobs_scroll.winfo_children():
            widget.destroy()

        if not self.jobs:
            empty = ctk.CTkFrame(self.jobs_scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
            empty.pack(fill="x", padx=10, pady=20)
            ctk.CTkLabel(empty, text="No hay tareas programadas actualmente", font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(pady=(18, 4))
            ctk.CTkLabel(
                empty,
                text="Usa el botón '+ Programar Tarea' para crear copias automáticas (pueden ejecutarse aunque cierres la app).",
                font=FONT_SMALL,
                text_color=TEXT_MUTED
            ).pack(pady=(0, 18))
            return

        for job in self.jobs:
            self._render_job_card(job)

    def _render_job_card(self, job: BackupJob) -> None:
        """Renderiza una tarjeta individual de tarea programada con estado de Windows y acciones."""
        card = ctk.CTkFrame(self.jobs_scroll, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="x", padx=6, pady=6)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=10)

        # Switch de activación
        switch = ctk.CTkSwitch(
            header,
            text="",
            width=40,
            command=lambda j=job: self._toggle_job_active(j)
        )
        if job.is_active:
            switch.select()
        switch.pack(side="left", padx=(0, 10))

        # Información central
        info = ctk.CTkFrame(header, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        # Fila superior de título y badges
        title_row = ctk.CTkFrame(info, fg_color="transparent")
        title_row.pack(fill="x", anchor="w")

        ctk.CTkLabel(title_row, text=job.name, font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(side="left")

        # Badge Tipo (FULL / INCREMENTAL)
        type_color = ACCENT_SUCCESS if job.backup_type.value == "FULL" else ACCENT_WARNING
        type_badge = ctk.CTkLabel(
            title_row,
            text=f" {job.backup_type.value} ",
            font=("Consolas", 10, "bold"),
            text_color=type_color,
            fg_color="#1E293B",
            corner_radius=4
        )
        type_badge.pack(side="left", padx=8)

        # Badge Windows Task Scheduler
        is_win = job.windows_task_installed or WindowsSchedulerService.is_task_installed(job.id)
        if is_win:
            win_badge_text = " 🪟 Windows: Activa (Sin app) " if job.is_active else " 🪟 Windows: En pausa "
            win_badge_color = "#10B981" if job.is_active else "#9CA3AF"
            win_bg = "#064E3B" if job.is_active else "#374151"
        else:
            win_badge_text = " Solo App Abierta "
            win_badge_color = "#9CA3AF"
            win_bg = "#1F2937"

        win_badge = ctk.CTkLabel(
            title_row,
            text=win_badge_text,
            font=("Consolas", 10, "bold"),
            text_color=win_badge_color,
            fg_color=win_bg,
            corner_radius=4
        )
        win_badge.pack(side="left")

        # Fila inferior con detalles
        freq_str = f"Cron: {job.cron_expression}" if job.cron_expression else f"Cada {job.interval_minutes}m"
        if job.start_time_str:
            freq_str += f" a las {job.start_time_str}"
        target_db = "Todas las bases de datos" if job.database_name == "__ALL__" else job.database_name
        next_run_str = job.next_run_time if job.next_run_time else "Calculando..."
        last_stat = job.last_status if job.last_status else "Pendiente"

        sub_info = f"Destino: {target_db}  |  Frecuencia: {freq_str}  |  Próxima corrida: {next_run_str}  |  Estado: {last_stat}"
        ctk.CTkLabel(info, text=sub_info, font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", pady=(3, 0))

        # Botones de Acción a la derecha
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        # 1. Modificar / Editar
        edit_btn = ctk.CTkButton(
            actions,
            text="✏️ Editar",
            width=70,
            height=28,
            font=FONT_SMALL,
            fg_color="#1E293B",
            hover_color="#334155",
            command=lambda j=job: self._on_edit_job_clicked(j)
        )
        edit_btn.pack(side="left", padx=3)

        # 2. Instalar / Quitar de Windows
        if is_win:
            win_toggle_btn = ctk.CTkButton(
                actions,
                text="Quitar de Windows",
                width=120,
                height=28,
                font=FONT_SMALL,
                fg_color="#2D333F",
                hover_color="#4B5563",
                command=lambda j=job: self._toggle_windows_install(j, install=False)
            )
        else:
            win_toggle_btn = ctk.CTkButton(
                actions,
                text="🪟 Poner en Windows",
                width=135,
                height=28,
                font=FONT_SMALL,
                fg_color="#065F46",
                hover_color="#047857",
                command=lambda j=job: self._toggle_windows_install(j, install=True)
            )
        win_toggle_btn.pack(side="left", padx=3)

        # 3. Ejecutar ahora
        run_now_btn = ctk.CTkButton(
            actions,
            text="▶ Ejecutar Ya",
            width=88,
            height=28,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=lambda j=job: self._run_job_now(j)
        )
        run_now_btn.pack(side="left", padx=3)

        # 4. Eliminar
        del_btn = ctk.CTkButton(
            actions,
            text="✕",
            width=28,
            height=28,
            font=FONT_SMALL,
            fg_color="#3B1D22",
            hover_color=ACCENT_DANGER,
            command=lambda j=job: self._delete_job(j)
        )
        del_btn.pack(side="left", padx=(3, 0))

    def _toggle_windows_install(self, job: BackupJob, install: bool) -> None:
        """Instala o desinstala directamente la tarea de Windows Task Scheduler."""
        if install:
            ok, msg = WindowsSchedulerService.install_job(job)
            if ok:
                job.windows_task_installed = True
                self.scheduler_service.add_or_update_job(job)
                app_logger.success(f"Tarea [{job.name}] programada exitosamente en Windows. Se ejecutará aunque la app esté cerrada.")
            else:
                app_logger.error(f"Fallo al instalar tarea en Windows: {msg}")
        else:
            ok, msg = WindowsSchedulerService.uninstall_job(job.id)
            if ok:
                job.windows_task_installed = False
                self.scheduler_service.add_or_update_job(job)
                app_logger.info(f"Tarea [{job.name}] desinstalada del Programador de Windows.")
            else:
                app_logger.warning(f"Aviso al desinstalar de Windows: {msg}")

        self.reload_jobs()

    def _toggle_job_active(self, job: BackupJob) -> None:
        """Activa o desactiva una tarea en la app y en Windows Task Scheduler si está instalada."""
        job.is_active = not job.is_active
        self.scheduler_service.add_or_update_job(job)

        # Sincronizar estado en Windows si corresponde
        if WindowsSchedulerService.is_task_installed(job.id):
            WindowsSchedulerService.set_task_state(job.id, job.is_active)

        state_str = "activada" if job.is_active else "desactivada"
        app_logger.info(f"Tarea [{job.name}] {state_str}.")
        self.reload_jobs()

    def _run_job_now(self, job: BackupJob) -> None:
        """Ejecuta inmediatamente una tarea en segundo plano."""
        def worker():
            app_logger.info(f"Ejecución forzada manual de tarea: [{job.name}]...")
            self.scheduler_service._execute_job_task(job.id)
            self.after(0, self.reload_jobs)

        threading.Thread(target=worker, daemon=True).start()

    def _delete_job(self, job: BackupJob) -> None:
        """Elimina una tarea y la desinstala del Programador de Windows."""
        # Limpiar de Windows si estaba instalada
        WindowsSchedulerService.uninstall_job(job.id)
        # Eliminar del scheduler
        self.scheduler_service.delete_job(job.id)
        app_logger.info(f"Tarea [{job.name}] eliminada por completo.")
        self.reload_jobs()

