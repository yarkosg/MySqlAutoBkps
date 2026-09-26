"""
Servicio para administrar el Programador de Tareas de Windows (Windows Task Scheduler).
Permite crear, consultar, modificar y eliminar tareas programadas en el sistema operativo
para que los respaldos automáticos se ejecuten puntualmente incluso cuando la aplicación está cerrada.
"""

import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple
from src.core.logger import app_logger
from src.models.backup_job import BackupJob


class WindowsSchedulerService:
    """Administrador de tareas programadas nativas en Windows mediante schtasks.exe."""

    TASK_PREFIX = "MySqlAutoBkps_"

    @classmethod
    def get_pythonw_executable(cls) -> str:
        """Localiza el ejecutable pythonw.exe (modo ventana oculta sin consola emergente)."""
        current_python = sys.executable
        python_dir = os.path.dirname(current_python)

        # Buscar pythonw.exe en la misma carpeta del intérprete actual
        pythonw_candidate = os.path.join(python_dir, "pythonw.exe")
        if os.path.isfile(pythonw_candidate):
            return os.path.abspath(pythonw_candidate)

        # Buscar en el PATH del sistema
        which_pythonw = shutil.which("pythonw.exe") or shutil.which("pythonw")
        if which_pythonw:
            return os.path.abspath(which_pythonw)

        # Fallback al ejecutable de Python activo
        return os.path.abspath(current_python)

    @classmethod
    def get_headless_runner_path(cls) -> str:
        """Retorna la ruta absoluta del script ejecutor sin interfaz run_headless.py."""
        # Se asume que el script está en la raíz del proyecto
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        runner = os.path.join(base_dir, "run_headless.py")
        return runner

    @classmethod
    def build_task_name(cls, job_id: str) -> str:
        """Construye el identificador de la tarea para Windows Task Scheduler."""
        # Sanitizar id para nombre seguro de tarea
        clean_id = job_id.replace("-", "_")
        return f"{cls.TASK_PREFIX}{clean_id}"

    @classmethod
    def is_task_installed(cls, job_id: str) -> bool:
        """Verifica si la tarea ya existe en el Programador de Tareas de Windows."""
        if sys.platform != "win32":
            return False

        task_name = cls.build_task_name(job_id)
        cmd = ["schtasks", "/query", "/tn", task_name]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                text=True
            )
            return res.returncode == 0
        except Exception:
            return False

    @classmethod
    def get_task_details(cls, job_id: str) -> Optional[Dict[str, str]]:
        """Consulta los detalles de la tarea registrada en Windows (próxima ejecución y estado)."""
        if sys.platform != "win32":
            return None

        task_name = cls.build_task_name(job_id)
        cmd = ["schtasks", "/query", "/tn", task_name, "/fo", "list"]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                text=True
            )
            if res.returncode != 0:
                return None

            details: Dict[str, str] = {}
            for line in res.stdout.splitlines():
                if ":" in line:
                    parts = line.split(":", 1)
                    k = parts[0].strip().lower()
                    v = parts[1].strip()
                    details[k] = v

            return details
        except Exception as e:
            app_logger.debug(f"Error consultando detalles de tarea de Windows: {e}")
            return None

    @classmethod
    def install_job(cls, job: BackupJob) -> Tuple[bool, str]:
        """
        Crea o actualiza la tarea en el Programador de Tareas de Windows.
        Se ejecutará en segundo plano con pythonw.exe de forma 100% silenciosa.
        """
        if sys.platform != "win32":
            return False, "Esta función solo está disponible en sistemas Windows."

        task_name = cls.build_task_name(job.id)
        pythonw = cls.get_pythonw_executable()
        runner = cls.get_headless_runner_path()

        # Validar ruta de runner
        if not os.path.isfile(runner):
            return False, f"No se encontró el script ejecutor en {runner}"

        # Comando que ejecutará Windows:
        # pythonw.exe "c:\...\run_headless.py" --job-id "job-xxx"
        run_command = f'"{pythonw}" "{runner}" --job-id "{job.id}"'

        # Determinar frecuencia para schtasks
        # /sc DAILY /st HH:MM
        # /sc HOURLY /mo N
        # /sc MINUTE /mo N
        # /sc WEEKLY /st HH:MM
        schedule_type = "DAILY"
        modifier_arg: List[str] = []
        start_time = job.start_time_str if job.start_time_str else "02:00"

        # Validar formato HH:MM
        if ":" not in start_time or len(start_time.split(":")) != 2:
            start_time = "02:00"

        minutes = job.interval_minutes
        if minutes < 60:
            schedule_type = "MINUTE"
            modifier_arg = ["/mo", str(max(minutes, 5))]
        elif minutes < 1440 and (minutes % 60 == 0):
            schedule_type = "HOURLY"
            modifier_arg = ["/mo", str(minutes // 60)]
        elif minutes >= 10080:
            schedule_type = "WEEKLY"
        else:
            schedule_type = "DAILY"

        schtasks_args = [
            "schtasks",
            "/create",
            "/tn", task_name,
            "/tr", run_command,
            "/sc", schedule_type,
            "/f"  # Forzar sobreescritura si ya existe
        ]

        if schedule_type in ("DAILY", "WEEKLY"):
            schtasks_args.extend(["/st", start_time])

        if modifier_arg:
            schtasks_args.extend(modifier_arg)

        app_logger.info(f"Registrando tarea en Windows Task Scheduler: [{task_name}]...")
        try:
            proc = subprocess.run(
                schtasks_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )

            if proc.returncode == 0:
                app_logger.success(f"Tarea de Windows [{task_name}] instalada exitosamente.")
                job.windows_task_installed = True

                # Obtener detalles de próxima corrida
                details = cls.get_task_details(job.id)
                if details:
                    # En español: "hora próxima ejecución"
                    for k, v in details.items():
                        if "próxima" in k or "next" in k:
                            job.next_run_time = v
                            break

                return True, "Tarea registrada exitosamente en Windows Task Scheduler."
            else:
                err_msg = proc.stderr.strip() or proc.stdout.strip()
                app_logger.error(f"Fallo al instalar tarea de Windows: {err_msg}")
                return False, err_msg

        except Exception as e:
            app_logger.error(f"Excepción al ejecutar schtasks: {e}")
            return False, str(e)

    @classmethod
    def uninstall_job(cls, job_id: str) -> Tuple[bool, str]:
        """Elimina una tarea del Programador de Tareas de Windows."""
        if sys.platform != "win32":
            return False, "Solo disponible en Windows."

        task_name = cls.build_task_name(job_id)
        if not cls.is_task_installed(job_id):
            return True, "La tarea no estaba registrada en Windows."

        cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            if proc.returncode == 0:
                app_logger.info(f"Tarea de Windows [{task_name}] eliminada.")
                return True, "Tarea eliminada de Windows."
            else:
                return False, proc.stderr.strip()
        except Exception as e:
            return False, str(e)

    @classmethod
    def set_task_state(cls, job_id: str, enable: bool) -> Tuple[bool, str]:
        """Habilita o deshabilita la tarea en Windows Task Scheduler sin eliminarla."""
        if sys.platform != "win32":
            return False, "Solo disponible en Windows."

        task_name = cls.build_task_name(job_id)
        if not cls.is_task_installed(job_id):
            return False, "La tarea no está instalada en Windows."

        action_flag = "/ENABLE" if enable else "/DISABLE"
        cmd = ["schtasks", "/change", "/tn", task_name, action_flag]
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            if proc.returncode == 0:
                status_str = "habilitada" if enable else "deshabilitada"
                app_logger.info(f"Tarea de Windows [{task_name}] {status_str}.")
                return True, f"Tarea {status_str} en Windows."
            else:
                return False, proc.stderr.strip() or proc.stdout.strip()
        except Exception as e:
            return False, str(e)

    @classmethod
    def sync_jobs_with_windows(cls, jobs: List[BackupJob]) -> None:
        """Sincroniza el estado de instalación y próxima corrida de cada trabajo con Windows."""
        if sys.platform != "win32":
            return

        for job in jobs:
            installed = cls.is_task_installed(job.id)
            job.windows_task_installed = installed

            if installed:
                details = cls.get_task_details(job.id)
                if details:
                    for k, v in details.items():
                        if "próxima" in k or "next" in k:
                            job.next_run_time = v
                            break
                        if "estado" in k or "status" in k:
                            if not job.last_status:
                                job.last_status = v
