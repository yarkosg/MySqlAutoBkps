"""
Servicio planificador de tareas en segundo plano para MySqlAutoBkps.
Utiliza APScheduler (BackgroundScheduler) para ejecutar respaldos programados
por intervalo o por expresión cron, actualizando estados de ejecución sin congelar la interfaz.
"""

import json
import os
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.core.config import config_manager
from src.core.logger import app_logger
from src.models.backup_job import BackupJob
from src.models.manifest import BackupType
from src.models.server import ServerConfig


class SchedulerService:
    """Administra las tareas programadas y la ejecución periódica de respaldos."""

    _instance: Optional["SchedulerService"] = None

    def __new__(cls) -> "SchedulerService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self.jobs_file = os.path.join(config_manager.config_dir, "jobs.json")
        self.scheduler = BackgroundScheduler(daemon=True)
        self._ensure_jobs_file()
        self._initialized = True

    def _ensure_jobs_file(self) -> None:
        """Crea el archivo jobs.json si no existe."""
        if not os.path.exists(self.jobs_file):
            try:
                with open(self.jobs_file, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
            except Exception as e:
                app_logger.error(f"Error creando jobs.json: {e}")

    def load_jobs(self) -> List[BackupJob]:
        """Carga la lista de tareas programadas desde el archivo."""
        self._ensure_jobs_file()
        try:
            with open(self.jobs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [BackupJob.from_dict(item) for item in data]
        except Exception as e:
            app_logger.error(f"Error cargando tareas programadas: {e}")
            return []

    def save_jobs(self, jobs: List[BackupJob]) -> None:
        """Guarda las tareas programadas en disco de forma atómica."""
        self._ensure_jobs_file()
        try:
            payload = [j.to_dict() for j in jobs]
            temp_file = self.jobs_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            shutil.move(temp_file, self.jobs_file)
        except Exception as e:
            app_logger.error(f"Error guardando tareas programadas: {e}")

    def start(self) -> None:
        """Inicia el planificador y registra las tareas activas."""
        if not self.scheduler.running:
            self.scheduler.start()
            app_logger.info("Planificador de tareas en segundo plano iniciado.")
            self.reload_all_jobs()

    def stop(self) -> None:
        """Detiene el planificador."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            app_logger.info("Planificador de tareas detenido.")

    def is_running(self) -> bool:
        """Retorna el estado del planificador."""
        return self.scheduler.running

    def reload_all_jobs(self) -> None:
        """Limpia los jobs de APScheduler y los vuelve a programar según jobs.json."""
        self.scheduler.remove_all_jobs()
        jobs = self.load_jobs()
        active_count = 0

        for job in jobs:
            if job.is_active:
                self._schedule_job_in_engine(job)
                active_count += 1

        app_logger.debug(f"{active_count} tareas activas programadas en el motor.")

    def _schedule_job_in_engine(self, job: BackupJob) -> None:
        """Registra un trabajo individual dentro de APScheduler."""
        try:
            if job.cron_expression:
                parts = job.cron_expression.split()
                if len(parts) == 5:
                    trigger = CronTrigger(
                        minute=parts[0],
                        hour=parts[1],
                        day=parts[2],
                        month=parts[3],
                        day_of_week=parts[4]
                    )
                else:
                    trigger = IntervalTrigger(minutes=max(job.interval_minutes, 1))
            else:
                trigger = IntervalTrigger(minutes=max(job.interval_minutes, 1))

            self.scheduler.add_job(
                func=self._execute_job_task,
                trigger=trigger,
                args=[job.id],
                id=job.id,
                name=job.name,
                replace_existing=True
            )

            # Calcular próxima ejecución
            scheduled_job = self.scheduler.get_job(job.id)
            if scheduled_job and scheduled_job.next_run_time:
                job.next_run_time = scheduled_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")

        except Exception as e:
            app_logger.error(f"Error programando tarea [{job.name}]: {e}")

    def _execute_job_task(self, job_id: str) -> None:
        """Callback ejecutado por APScheduler cuando se dispara la alarma de una tarea."""
        jobs = self.load_jobs()
        target_job = next((j for j in jobs if j.id == job_id), None)
        if not target_job or not target_job.is_active:
            return

        app_logger.info(f"⏰ Ejecutando tarea programada: [{target_job.name}]...")
        from src.services.backup_service import BackupService
        backup_service = BackupService()

        # Cargar datos del servidor
        servers_data = config_manager.load_servers()
        server_dict = next((s for s in servers_data if s.get("id") == target_job.server_id), None)
        if not server_dict:
            app_logger.error(f"Servidor para la tarea [{target_job.name}] no encontrado.")
            target_job.last_status = "ERROR: Servidor no encontrado"
            self.save_jobs(jobs)
            return

        server = ServerConfig.from_dict(server_dict)
        target_job.last_run_time = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            if target_job.database_name.upper() == "__ALL__":
                backup_service.backup_server(server, target_job.backup_type)
            else:
                backup_service.backup_database(server, target_job.database_name, target_job.backup_type)

            target_job.last_status = "SUCCESS"
            app_logger.success(f"Tarea programada [{target_job.name}] completada con éxito.")
        except Exception as e:
            target_job.last_status = f"ERROR: {str(e)}"
            app_logger.error(f"Error en tarea programada [{target_job.name}]: {e}")

        # Actualizar siguiente corrida
        sched_job = self.scheduler.get_job(target_job.id)
        if sched_job and sched_job.next_run_time:
            target_job.next_run_time = sched_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")

        self.save_jobs(jobs)

    def add_or_update_job(self, job: BackupJob) -> None:
        """Añade o edita una tarea programada."""
        jobs = self.load_jobs()
        idx = next((i for i, j in enumerate(jobs) if j.id == job.id), None)
        if idx is not None:
            jobs[idx] = job
        else:
            jobs.append(job)

        self.save_jobs(jobs)
        if self.scheduler.running:
            if job.is_active:
                self._schedule_job_in_engine(job)
            else:
                self.scheduler.remove_job(job.id)

    def delete_job(self, job_id: str) -> None:
        """Elimina una tarea programada."""
        jobs = self.load_jobs()
        jobs = [j for j in jobs if j.id != job_id]
        self.save_jobs(jobs)
        if self.scheduler.running and self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
