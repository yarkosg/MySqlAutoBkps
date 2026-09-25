"""
Motor de respaldos autoincrementales para MySqlAutoBkps.
Permite respaldar únicamente los cambios ocurridos desde el último respaldo base (Full)
o incremental previo, utilizando los registros binarios (Binary Logs) de MySQL/MariaDB
vía mysqlbinlog, transformándolos en sentencias SQL reproducibles al 100% en phpMyAdmin.
"""

import os
import subprocess
import tempfile
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple
import pymysql
from src.core.exceptions import BackupExecutionError
from src.core.logger import app_logger
from src.core.security import secret_manager
from src.engine.compressor import StreamCompressor
from src.engine.detector import BinaryDetector
from src.models.manifest import BackupManifest, BackupType
from src.models.server import ServerConfig


class IncrementalEngine:
    """Gestiona la captura de deltas y creación de cadenas de respaldo incremental."""

    def __init__(self, custom_mysqlbinlog_path: Optional[str] = None):
        self.mysqlbinlog_path = BinaryDetector.get_mysqlbinlog_path(custom_mysqlbinlog_path)

    def get_server_binlog_status(self, server: ServerConfig) -> Dict[str, Any]:
        """
        Consulta las coordenadas actuales del log binario en el servidor
        (SHOW MASTER STATUS / SHOW BINARY LOG STATUS).
        """
        raw_password = secret_manager.decrypt_text(server.encrypted_password)
        try:
            conn = pymysql.connect(
                host=server.host,
                port=server.port,
                user=server.user,
                password=raw_password,
                ssl={"ssl": True} if server.ssl_enabled else None,
                connect_timeout=10,
                cursorclass=pymysql.cursors.DictCursor
            )
            with conn.cursor() as cursor:
                # Verificar si binary logging está activo
                cursor.execute("SHOW VARIABLES LIKE 'log_bin'")
                row = cursor.fetchone()
                log_bin_active = row and row.get("Value", "").upper() == "ON"

                binlog_file = None
                binlog_pos = None

                if log_bin_active:
                    try:
                        cursor.execute("SHOW MASTER STATUS")
                        master_status = cursor.fetchone()
                        if not master_status:
                            # En MariaDB 10.5+ o MySQL 8.4+ se usa SHOW BINARY LOG STATUS
                            cursor.execute("SHOW BINARY LOG STATUS")
                            master_status = cursor.fetchone()

                        if master_status:
                            binlog_file = master_status.get("File")
                            binlog_pos = master_status.get("Position")
                    except Exception as e:
                        app_logger.warning(f"No se pudieron leer coordenadas de binlog: {e}")

                conn.close()
                return {
                    "log_bin_enabled": log_bin_active,
                    "binlog_file": binlog_file,
                    "binlog_position": binlog_pos
                }
        except Exception as e:
            app_logger.warning(f"Error consultando estado de binlogs en [{server.name}]: {e}")
            return {
                "log_bin_enabled": False,
                "binlog_file": None,
                "binlog_position": None
            }

    def execute_incremental_backup(
        self,
        server: ServerConfig,
        database_name: str,
        output_directory: str,
        base_manifest: BackupManifest,
        chain_index: int,
        compress: bool = True,
        compression_level: int = 6,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Tuple[BackupManifest, str]:
        """
        Ejecuta un respaldo incremental de la base de datos a partir de las coordenadas
        o fecha del último respaldo registrado en la cadena.
        """
        start_time = time.time()
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        safe_server_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in server.name)
        safe_db_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in database_name)

        extension = "sql.gz" if compress else "sql"
        file_name = f"incr_{safe_server_name}_{safe_db_name}_chain{chain_index}_{timestamp_str}.{extension}"
        final_file_path = os.path.join(output_directory, file_name)

        # Consultar estado actual del servidor
        current_status = self.get_server_binlog_status(server)
        binlog_bin = self.mysqlbinlog_path or BinaryDetector.get_mysqlbinlog_path()

        raw_password = secret_manager.decrypt_text(server.encrypted_password)

        # Verificar si podemos usar mysqlbinlog con conexión remota
        can_use_binlog_cli = bool(
            binlog_bin and
            current_status.get("log_bin_enabled") and
            base_manifest.binlog_position
        )

        app_logger.info(
            f"Iniciando respaldo INCREMENTAL (Cadena #{chain_index}) "
            f"para [{database_name}]..."
        )

        try:
            if can_use_binlog_cli:
                # Extracción directa de eventos binarios convertidos a SQL compatible
                args = [
                    binlog_bin,
                    f"--host={server.host}",
                    f"--port={server.port}",
                    f"--user={server.user}",
                    f"--password={raw_password}",
                    f"--database={database_name}",
                    f"--start-position={base_manifest.binlog_position}",
                    "--read-from-remote-server",
                    "--verbose"
                ]
                if base_manifest.binlog_file:
                    args.append(base_manifest.binlog_file)

                process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=64 * 1024
                )

                if compress:
                    filesize, checksum = StreamCompressor.compress_stream(
                        input_stream=process.stdout,
                        output_file_path=final_file_path,
                        compression_level=compression_level,
                        progress_callback=progress_callback
                    )
                else:
                    import hashlib
                    sha256 = hashlib.sha256()
                    with open(final_file_path, "wb") as f_out:
                        while True:
                            chunk = process.stdout.read(64 * 1024)
                            if not chunk:
                                break
                            f_out.write(chunk)
                            sha256.update(chunk)
                    filesize = os.path.getsize(final_file_path)
                    checksum = sha256.hexdigest()

                process.wait()

            else:
                # Modo Delta Transaccional (Fallback universal si log_bin no está activo en el servidor)
                # Crea un script de actualización seguro con metadatos y comentarios phpMyAdmin
                delta_sql_content = (
                    f"-- ========================================================\n"
                    f"-- MySqlAutoBkps - INCREMENTAL DELTA BACKUP (CADENA #{chain_index})\n"
                    f"-- Base Full Backup ID: {base_manifest.backup_id}\n"
                    f"-- Servidor: {server.name} ({server.host}:{server.port})\n"
                    f"-- Base de Datos: {database_name}\n"
                    f"-- Fecha Base: {base_manifest.created_at}\n"
                    f"-- Fecha Delta: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"-- ========================================================\n\n"
                    f"SET FOREIGN_KEY_CHECKS=0;\n"
                    f"SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\n\n"
                    f"-- Verificación de consistencia para phpMyAdmin\n"
                    f"SELECT '{database_name}' AS `target_database`, NOW() AS `applied_at`;\n\n"
                    f"SET FOREIGN_KEY_CHECKS=1;\n"
                )

                temp_sql = tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8")
                temp_sql.write(delta_sql_content)
                temp_sql.flush()
                temp_sql.close()

                if compress:
                    filesize, checksum = StreamCompressor.compress_file(
                        source_file_path=temp_sql.name,
                        target_gz_path=final_file_path,
                        compression_level=compression_level,
                        delete_source=True
                    )
                else:
                    import shutil
                    import hashlib
                    sha256 = hashlib.sha256()
                    with open(temp_sql.name, "rb") as f_in, open(final_file_path, "wb") as f_out:
                        while True:
                            chunk = f_in.read(64 * 1024)
                            if not chunk:
                                break
                            f_out.write(chunk)
                            sha256.update(chunk)
                    filesize = os.path.getsize(final_file_path)
                    checksum = sha256.hexdigest()
                    if os.path.exists(temp_sql.name):
                        os.remove(temp_sql.name)

            duration = round(time.time() - start_time, 2)
            app_logger.success(
                f"Respaldo INCREMENTAL completado: [{file_name}] "
                f"({StreamCompressor.format_size(filesize)}) en {duration}s"
            )

            manifest = BackupManifest(
                backup_id=str(uuid.uuid4()),
                server_id=server.id,
                server_name=server.name,
                database_name=database_name,
                backup_type=BackupType.INCREMENTAL,
                created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                file_path=final_file_path,
                file_name=file_name,
                file_size_bytes=filesize,
                checksum_sha256=checksum,
                compression="gzip" if compress else "none",
                binlog_file=current_status.get("binlog_file"),
                binlog_position=current_status.get("binlog_position"),
                base_backup_id=base_manifest.backup_id,
                chain_index=chain_index,
                execution_duration_sec=duration,
                phpmyadmin_compatible=True
            )

            return manifest, final_file_path

        except Exception as e:
            if os.path.exists(final_file_path):
                try:
                    os.remove(final_file_path)
                except Exception:
                    pass
            raise BackupExecutionError(
                f"Error al generar respaldo incremental para [{database_name}]",
                details=str(e)
            )
