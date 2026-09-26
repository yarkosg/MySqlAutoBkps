"""
Script ejecutor sin interfaz gráfica (Headless Runner) para MySqlAutoBkps.
Invocado automáticamente por el Programador de Tareas de Windows (Windows Task Scheduler)
para ejecutar respaldos periódicos en segundo plano sin requerir que la aplicación esté abierta.
"""

import argparse
import os
import sys
import time

# Asegurar que el directorio raíz del proyecto esté en sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.core.config import config_manager
from src.core.logger import app_logger
from src.models.manifest import BackupType
from src.models.server import ServerConfig
from src.services.backup_service import BackupService
from src.services.scheduler_service import SchedulerService


def run_job(job_id: str) -> int:
    """Ejecuta una tarea programada por su ID."""
    app_logger.info(f"=== [Windows Task Scheduler] Ejecutando Tarea: {job_id} ===")

    scheduler_service = SchedulerService()
    jobs = scheduler_service.load_jobs()

    target_job = next((j for j in jobs if j.id == job_id), None)
    if not target_job:
        app_logger.error(f"Error: La tarea con ID [{job_id}] no existe en jobs.json.")
        return 1

    if not target_job.is_active:
        app_logger.warning(f"La tarea [{target_job.name}] está marcada como inactiva. Omitiendo ejecución.")
        return 0

    servers_data = config_manager.load_servers()
    server_dict = next((s for s in servers_data if s.get("id") == target_job.server_id), None)
    if not server_dict:
        app_logger.error(f"Error: El servidor asociado con ID [{target_job.server_id}] no existe.")
        target_job.last_status = "ERROR: Servidor no encontrado"
        target_job.last_run_time = time.strftime("%Y-%m-%d %H:%M:%S")
        scheduler_service.save_jobs(jobs)
        return 1

    server = ServerConfig.from_dict(server_dict)
    backup_service = BackupService()
    target_job.last_run_time = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        if target_job.database_name.upper() == "__ALL__":
            app_logger.info(f"Respaldando todas las bases de datos de [{server.name}]...")
            results = backup_service.backup_server(server, target_job.backup_type)
            target_job.last_status = f"SUCCESS ({len(results)} BDs respaldadas)"
        else:
            app_logger.info(f"Respaldando base de datos [{target_job.database_name}] en [{server.name}]...")
            manifest = backup_service.backup_database(server, target_job.database_name, target_job.backup_type)
            target_job.last_status = "SUCCESS"

        app_logger.success(f"=== [Windows Task Scheduler] Tarea [{target_job.name}] finalizada con éxito ===")
        scheduler_service.save_jobs(jobs)
        return 0

    except Exception as e:
        error_msg = f"ERROR: {str(e)}"
        target_job.last_status = error_msg
        app_logger.error(f"Fallo en ejecución de tarea [{target_job.name}]: {e}")
        scheduler_service.save_jobs(jobs)
        return 1


def main():
    parser = argparse.ArgumentParser(description="MySqlAutoBkps Headless Background Runner")
    parser.add_argument("--job-id", required=True, help="ID de la tarea a ejecutar")
    args = parser.parse_args()

    exit_code = run_job(args.job_id)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
