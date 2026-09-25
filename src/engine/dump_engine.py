"""
Motor de volcado (Dump Engine) de alto rendimiento para MySQL y MariaDB.
Configurado para compatibilidad al 100% con phpMyAdmin, garantizando el volcado
íntegro de estructuras, datos, vistas, funciones, procedimientos almacenados, disparadores y eventos.

Implementa el estándar de seguridad oficial: paso de credenciales mediante
archivo temporal con directiva [client] (--defaults-extra-file) para evitar
la exposición de contraseñas en la tabla de procesos del sistema operativo.
"""

import os
import subprocess
import tempfile
import time
from typing import Callable, Dict, List, Optional, Tuple
from src.core.config import config_manager
from src.core.exceptions import BackupExecutionError, DumpEngineNotFoundError
from src.core.logger import app_logger
from src.core.security import secret_manager
from src.engine.compressor import StreamCompressor
from src.engine.detector import BinaryDetector
from src.engine.native_dump_engine import NativeDumpEngine
from src.models.manifest import BackupManifest, BackupType
from src.models.server import ServerConfig


class DumpEngine:
    """Ejecutor de respaldos completos y estructurados mediante mysqldump / mariadb-dump."""

    def __init__(self, custom_binary_path: Optional[str] = None):
        self.binary_path = BinaryDetector.get_mysqldump_path(custom_binary_path)

    def _ensure_binary_available(self) -> str:
        """Verifica que el ejecutable esté disponible."""
        if not self.binary_path or not os.path.isfile(self.binary_path):
            # Reintentar detección en tiempo de ejecución
            self.binary_path = BinaryDetector.get_mysqldump_path()
            if not self.binary_path:
                raise DumpEngineNotFoundError(
                    "No se encontró 'mysqldump' ni 'mariadb-dump' en el sistema.",
                    details="Asegúrate de tener MySQL/MariaDB instalado o define la ruta en Configuración."
                )
        return self.binary_path

    def _create_secure_cnf(self, server: ServerConfig) -> str:
        """
        Crea un archivo temporal seguro de configuración [client] para que mysqldump
        se conecte sin exponer contraseñas en la línea de comandos ni generar advertencias.
        """
        raw_password = secret_manager.decrypt_text(server.encrypted_password)

        temp_cnf = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".cnf",
            delete=False,
            encoding="utf-8"
        )
        content = (
            "[client]\n"
            f"host = {server.host}\n"
            f"port = {server.port}\n"
            f"user = {server.user}\n"
            f"password = \"{raw_password}\"\n"
        )
        if server.ssl_enabled:
            content += "ssl-mode = REQUIRED\n"
        else:
            content += "ssl-mode = PREFERRED\n"

        temp_cnf.write(content)
        temp_cnf.flush()
        temp_cnf.close()

        # Asegurar permisos estrictos en sistemas tipo Unix
        try:
            os.chmod(temp_cnf.name, 0o600)
        except Exception:
            pass

        return temp_cnf.name

    def _supports_column_statistics(self) -> bool:
        """Determina si el binario de mysqldump soporta la opción --column-statistics."""
        if not hasattr(self, "_cached_col_stats"):
            try:
                proc = subprocess.run(
                    [self._ensure_binary_available(), "--column-statistics=0", "--help"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=4
                )
                self._cached_col_stats = (proc.returncode == 0)
            except Exception:
                self._cached_col_stats = False
        return self._cached_col_stats

    def build_dump_arguments(self, cnf_path: str, database_name: str) -> List[str]:
        """
        Construye el conjunto riguroso de banderas para garantizar compatibilidad total
        con phpMyAdmin, MySQL y MariaDB.
        """
        args = [
            f"--defaults-extra-file={cnf_path}",
            # Consistencia y memoria
            "--single-transaction",
            "--quick",
            # Integridad de objetos de base de datos (100% de la BD)
            "--routines",
            "--triggers",
            "--events",
            # Compatibilidad y optimización para phpMyAdmin
            "--add-drop-table",
            "--add-locks",
            "--create-options",
            "--disable-keys",
            "--extended-insert",
            "--hex-blob",
            "--default-character-set=utf8mb4",
            "--comments",
            # Evita errores de permisos en cPanel / Shared hosting al importar
            "--set-gtid-purged=OFF",
        ]

        # En MySQL 8+ conectado a MySQL 5.7 (HostGator/cPanel), evita fallo por tabla COLUMN_STATISTICS
        if self._supports_column_statistics():
            args.append("--column-statistics=0")

        # Nombre de la base de datos a respaldar
        args.append(database_name)
        return args

    def execute_dump(
        self,
        server: ServerConfig,
        database_name: str,
        output_directory: str,
        compress: bool = True,
        compression_level: int = 6,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Tuple[BackupManifest, str]:
        """
        Ejecuta el volcado completo de una base de datos con compresión en streaming.
        Utiliza el Motor Nativo Python de forma predeterminada (cero dependencias locales)
        o mysqldump con fallback automático a nativo.
        """
        settings = config_manager.load_settings()
        engine_mode = settings.get("dump_engine_mode", "native")

        # Modo Nativo Puro Python (Predeterminado: No requiere MySQL en la máquina local)
        if engine_mode == "native" or not self.binary_path:
            return NativeDumpEngine.execute_native_dump(
                server=server,
                database_name=database_name,
                output_directory=output_directory,
                compress=compress,
                compression_level=compression_level,
                progress_callback=progress_callback
            )

        # Modo CLI con fallback seguro a nativo
        try:
            return self._execute_cli_dump(
                server=server,
                database_name=database_name,
                output_directory=output_directory,
                compress=compress,
                compression_level=compression_level,
                progress_callback=progress_callback
            )
        except Exception as e:
            app_logger.warning(f"mysqldump CLI falló ({e}); respaldando con Motor Nativo Python...")
            return NativeDumpEngine.execute_native_dump(
                server=server,
                database_name=database_name,
                output_directory=output_directory,
                compress=compress,
                compression_level=compression_level,
                progress_callback=progress_callback
            )

    def _execute_cli_dump(
        self,
        server: ServerConfig,
        database_name: str,
        output_directory: str,
        compress: bool = True,
        compression_level: int = 6,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Tuple[BackupManifest, str]:
        """Ejecuta el volcado mediante el ejecutable CLI mysqldump."""
        binary = self._ensure_binary_available()
        os.makedirs(output_directory, exist_ok=True)

        start_time = time.time()
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        safe_server_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in server.name)
        safe_db_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in database_name)

        extension = "sql.gz" if compress else "sql"
        file_name = f"dump_{safe_server_name}_{safe_db_name}_{timestamp_str}.{extension}"
        final_file_path = os.path.join(output_directory, file_name)

        cnf_path = self._create_secure_cnf(server)

        try:
            dump_args = [binary] + self.build_dump_arguments(cnf_path, database_name)
            app_logger.info(f"Iniciando respaldo FULL [CLI mysqldump] para [{database_name}] en servidor [{server.name}]...")

            # Iniciar el proceso de mysqldump con tubería de stdout
            process = subprocess.Popen(
                dump_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=64 * 1024
            )

            if compress:
                # Comprimir directamente desde stdout hacia el archivo final
                filesize, checksum = StreamCompressor.compress_stream(
                    input_stream=process.stdout,
                    output_file_path=final_file_path,
                    compression_level=compression_level,
                    progress_callback=progress_callback
                )
            else:
                # Escribir el SQL en claro calculando hash
                import hashlib
                sha256 = hashlib.sha256()
                with open(final_file_path, "wb") as f_out:
                    while True:
                        chunk = process.stdout.read(64 * 1024)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        sha256.update(chunk)
                        if progress_callback:
                            progress_callback(len(chunk))
                filesize = os.path.getsize(final_file_path)
                checksum = sha256.hexdigest()

            # Esperar a que el proceso termine y capturar stderr
            stderr_output = process.stderr.read().decode("utf-8", errors="replace")
            process.wait()

            if process.returncode != 0:
                if os.path.exists(final_file_path):
                    try:
                        os.remove(final_file_path)
                    except Exception:
                        pass
                raise BackupExecutionError(
                    f"Fallo en mysqldump (código de salida {process.returncode})",
                    details=stderr_output.strip()
                )

            duration = round(time.time() - start_time, 2)
            app_logger.success(
                f"Respaldo FULL completado: [{file_name}] "
                f"({StreamCompressor.format_size(filesize)}) en {duration}s"
            )

            # Generar el Manifiesto de Respaldo
            import uuid
            manifest = BackupManifest(
                backup_id=str(uuid.uuid4()),
                server_id=server.id,
                server_name=server.name,
                database_name=database_name,
                backup_type=BackupType.FULL,
                created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                file_path=final_file_path,
                file_name=file_name,
                file_size_bytes=filesize,
                checksum_sha256=checksum,
                compression="gzip" if compress else "none",
                execution_duration_sec=duration,
                phpmyadmin_compatible=True
            )

            return manifest, final_file_path

        finally:
            # Eliminar siempre el archivo temporal con las credenciales
            if os.path.exists(cnf_path):
                try:
                    os.remove(cnf_path)
                except Exception:
                    pass
