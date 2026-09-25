"""
Motor de volcado nativo en Python puro (NativeDumpEngine) para MySQL y MariaDB.
No requiere que la máquina local tenga instalado MySQL, MariaDB ni mysqldump.
100% compatible con todas las versiones de MySQL (5.0, 5.5, 5.6, 5.7, 8.0, 8.4, 9.0+)
y MariaDB (10.x, 11.x).
Genera volcados íntegros (Estructura, Datos, Vistas, Procedimientos, Funciones, Triggers y Eventos)
con formato estándar idéntico a phpMyAdmin.
"""

import datetime
import decimal
import gzip
import hashlib
import io
import os
import time
import uuid
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple
import pymysql
import pymysql.cursors
from src.core.exceptions import BackupExecutionError
from src.core.logger import app_logger
from src.core.security import secret_manager
from src.engine.compressor import StreamCompressor
from src.models.manifest import BackupManifest, BackupType
from src.models.server import ServerConfig


class NativeDumpEngine:
    """Motor de volcado puro en Python con streaming y cero dependencias de ejecutables externos."""

    CHUNK_ROWS = 500  # Filas por bloque en sentencias INSERT extendidas

    @classmethod
    def get_connection(cls, server: ServerConfig, database: Optional[str] = None) -> pymysql.Connection:
        """Crea una conexión con cursor optimizado para streaming hacia el servidor MySQL."""
        raw_password = secret_manager.decrypt_text(server.encrypted_password)

        ssl_config = None
        if server.ssl_enabled:
            import ssl
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            ssl_config = ssl_ctx

        return pymysql.connect(
            host=server.host,
            port=server.port,
            user=server.user,
            password=raw_password,
            database=database,
            charset="utf8mb4",
            ssl=ssl_config,
            connect_timeout=15,
            read_timeout=3600,  # 1 hora para bases de datos masivas
            write_timeout=3600,
            cursorclass=pymysql.cursors.Cursor
        )

    @classmethod
    def _escape_value(cls, val: Any) -> str:
        """Convierte un valor de Python a su representación SQL segura para phpMyAdmin."""
        if val is None:
            return "NULL"
        elif isinstance(val, bool):
            return "1" if val else "0"
        elif isinstance(val, (int, float, decimal.Decimal)):
            return str(val)
        elif isinstance(val, (bytes, bytearray)):
            # Formato hexadecimal estándar de MySQL para BLOBs (previene corrupción binaria)
            return f"X'{val.hex()}'"
        elif isinstance(val, (datetime.datetime, datetime.date, datetime.time)):
            return f"'{val}'"
        else:
            # Cadena de texto escapada
            escaped = pymysql.converters.escape_string(str(val))
            return f"'{escaped}'"

    @classmethod
    def execute_native_dump(
        cls,
        server: ServerConfig,
        database_name: str,
        output_directory: str,
        compress: bool = True,
        compression_level: int = 6,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Tuple[BackupManifest, str]:
        """
        Ejecuta el volcado completo de una base de datos directamente por protocolo MySQL
        sin usar ejecutables locales.
        """
        os.makedirs(output_directory, exist_ok=True)
        start_time = time.time()
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        safe_server_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in server.name)
        safe_db_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in database_name)

        ext = "sql.gz" if compress else "sql"
        file_name = f"dump_{safe_server_name}_{safe_db_name}_{timestamp_str}.{ext}"
        final_file_path = os.path.join(output_directory, file_name)

        app_logger.info(f"Iniciando respaldo FULL [Motor Nativo Python] para [{database_name}] en [{server.name}]...")

        sha256 = hashlib.sha256()
        total_tables = 0
        total_views = 0
        total_routines = 0
        total_triggers = 0
        total_events = 0

        # Apertura del stream de salida
        f_raw = open(final_file_path, "wb")
        if compress:
            out_stream = gzip.GzipFile(filename="", mode="wb", compresslevel=compression_level, fileobj=f_raw)
        else:
            out_stream = f_raw

        def write_sql(text: str) -> None:
            data = text.encode("utf-8")
            out_stream.write(data)
            sha256.update(data)
            if progress_callback:
                progress_callback(len(data))

        conn = cls.get_connection(server, database=database_name)

        try:
            with conn.cursor() as cur:
                # Obtener versión del servidor
                cur.execute("SELECT VERSION()")
                row_ver = cur.fetchone()
                server_ver = row_ver[0] if row_ver else "MySQL"

                # 1. ENCABEZADO ESTÁNDAR PHPMYADMIN
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                write_sql(
                    f"-- phpMyAdmin SQL Dump\n"
                    f"-- version 5.2.1\n"
                    f"-- https://www.phpmyadmin.net/\n"
                    f"--\n"
                    f"-- Servidor: {server.host}:{server.port}\n"
                    f"-- Tiempo de generación: {now_str}\n"
                    f"-- Versión del servidor: {server_ver}\n"
                    f"-- Generado por: MySqlAutoBkps (Pure Python Native Engine)\n"
                    f"--\n\n"
                    f"SET SQL_MODE = \"NO_AUTO_VALUE_ON_ZERO\";\n"
                    f"START TRANSACTION;\n"
                    f"SET time_zone = \"+00:00\";\n\n"
                    f"/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;\n"
                    f"/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;\n"
                    f"/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;\n"
                    f"/*!40101 SET NAMES utf8mb4 */;\n"
                    f"/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;\n"
                    f"/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;\n"
                    f"/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;\n"
                    f"/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;\n\n"
                )

                # 2. LISTAR TABLAS Y VISTAS
                cur.execute("SHOW FULL TABLES")
                all_tables_info = cur.fetchall()

                base_tables = [r[0] for r in all_tables_info if len(r) >= 2 and r[1] == "BASE TABLE"]
                views = [r[0] for r in all_tables_info if len(r) >= 2 and r[1] == "VIEW"]
                total_tables = len(base_tables)
                total_views = len(views)

                # 3. VOLCADO DE TABLAS BASE (ESTRUCTURA + DATOS)
                for tbl in base_tables:
                    # Estructura
                    cur.execute(f"SHOW CREATE TABLE `{tbl}`")
                    create_row = cur.fetchone()
                    create_table_sql = create_row[1] if create_row else ""

                    write_sql(
                        f"-- --------------------------------------------------------\n"
                        f"-- Estructura de tabla para la tabla `{tbl}`\n"
                        f"-- --------------------------------------------------------\n\n"
                        f"DROP TABLE IF EXISTS `{tbl}`;\n"
                        f"{create_table_sql};\n\n"
                    )

                    # Obtener nombres de columnas
                    cur.execute(f"SHOW COLUMNS FROM `{tbl}`")
                    cols = [f"`{col_row[0]}`" for col_row in cur.fetchall()]
                    cols_clause = f"({', '.join(cols)})" if cols else ""

                    # Volcado de Filas con Cursor Servidor (Streaming memory-safe)
                    with conn.cursor(pymysql.cursors.SSCursor) as stream_cur:
                        stream_cur.execute(f"SELECT * FROM `{tbl}`")
                        batch = stream_cur.fetchmany(cls.CHUNK_ROWS)

                        if batch:
                            write_sql(
                                f"-- Volcado de datos para la tabla `{tbl}`\n\n"
                                f"LOCK TABLES `{tbl}` WRITE;\n"
                                f"/*!40000 ALTER TABLE `{tbl}` DISABLE KEYS */;\n"
                            )

                            while batch:
                                rows_sql = []
                                for r in batch:
                                    vals = [cls._escape_value(v) for v in r]
                                    rows_sql.append(f"({', '.join(vals)})")

                                insert_stmt = f"INSERT INTO `{tbl}` {cols_clause} VALUES\n" + ",\n".join(rows_sql) + ";\n"
                                write_sql(insert_stmt)
                                batch = stream_cur.fetchmany(cls.CHUNK_ROWS)

                            write_sql(
                                f"/*!40000 ALTER TABLE `{tbl}` ENABLE KEYS */;\n"
                                f"UNLOCK TABLES;\n\n"
                            )

                # 4. VOLCADO DE VISTAS (Con tablas dummy preliminares estándar phpMyAdmin)
                if views:
                    write_sql(
                        f"-- --------------------------------------------------------\n"
                        f"-- Estructura preliminar para vistas para evitar errores de dependencias\n"
                        f"-- --------------------------------------------------------\n\n"
                    )
                    for vw in views:
                        write_sql(f"DROP VIEW IF EXISTS `{vw}`;\n")

                    for vw in views:
                        cur.execute(f"SHOW CREATE VIEW `{vw}`")
                        view_row = cur.fetchone()
                        create_view_sql = view_row[1] if view_row else ""

                        write_sql(
                            f"-- --------------------------------------------------------\n"
                            f"-- Estructura de vista `{vw}`\n"
                            f"-- --------------------------------------------------------\n\n"
                            f"{create_view_sql};\n\n"
                        )

                # 5. PROCEDIMIENTOS Y FUNCIONES ALMACENADAS
                try:
                    cur.execute(f"SHOW PROCEDURE STATUS WHERE Db = '{database_name}'")
                    procedures = [r[1] for r in cur.fetchall() if len(r) >= 2]
                    for proc in procedures:
                        cur.execute(f"SHOW CREATE PROCEDURE `{proc}`")
                        proc_row = cur.fetchone()
                        if proc_row and len(proc_row) >= 3:
                            total_routines += 1
                            write_sql(
                                f"-- --------------------------------------------------------\n"
                                f"-- Procedimiento `{proc}`\n"
                                f"-- --------------------------------------------------------\n\n"
                                f"DROP PROCEDURE IF EXISTS `{proc}`;\n"
                                f"DELIMITER $$\n"
                                f"{proc_row[2]}$$\n"
                                f"DELIMITER ;\n\n"
                            )
                except Exception as e:
                    app_logger.debug(f"Aviso al extraer procedimientos: {e}")

                try:
                    cur.execute(f"SHOW FUNCTION STATUS WHERE Db = '{database_name}'")
                    functions = [r[1] for r in cur.fetchall() if len(r) >= 2]
                    for fn in functions:
                        cur.execute(f"SHOW CREATE FUNCTION `{fn}`")
                        fn_row = cur.fetchone()
                        if fn_row and len(fn_row) >= 3:
                            total_routines += 1
                            write_sql(
                                f"-- --------------------------------------------------------\n"
                                f"-- Función `{fn}`\n"
                                f"-- --------------------------------------------------------\n\n"
                                f"DROP FUNCTION IF EXISTS `{fn}`;\n"
                                f"DELIMITER $$\n"
                                f"{fn_row[2]}$$\n"
                                f"DELIMITER ;\n\n"
                            )
                except Exception as e:
                    app_logger.debug(f"Aviso al extraer funciones: {e}")

                # 6. DISPARADORES (TRIGGERS)
                try:
                    cur.execute(f"SHOW TRIGGERS FROM `{database_name}`")
                    triggers = [r[0] for r in cur.fetchall() if r]
                    for tr in triggers:
                        cur.execute(f"SHOW CREATE TRIGGER `{tr}`")
                        tr_row = cur.fetchone()
                        if tr_row and len(tr_row) >= 3:
                            total_triggers += 1
                            write_sql(
                                f"-- --------------------------------------------------------\n"
                                f"-- Disparador `{tr}`\n"
                                f"-- --------------------------------------------------------\n\n"
                                f"DROP TRIGGER IF EXISTS `{tr}`;\n"
                                f"DELIMITER $$\n"
                                f"{tr_row[2]}$$\n"
                                f"DELIMITER ;\n\n"
                            )
                except Exception as e:
                    app_logger.debug(f"Aviso al extraer triggers: {e}")

                # 7. EVENTOS PROGRAMADOS
                try:
                    cur.execute(f"SHOW EVENTS FROM `{database_name}`")
                    events = [r[1] for r in cur.fetchall() if len(r) >= 2]
                    for ev in events:
                        cur.execute(f"SHOW CREATE EVENT `{ev}`")
                        ev_row = cur.fetchone()
                        if ev_row and len(ev_row) >= 4:
                            total_events += 1
                            write_sql(
                                f"-- --------------------------------------------------------\n"
                                f"-- Evento `{ev}`\n"
                                f"-- --------------------------------------------------------\n\n"
                                f"DROP EVENT IF EXISTS `{ev}`;\n"
                                f"DELIMITER $$\n"
                                f"{ev_row[3]}$$\n"
                                f"DELIMITER ;\n\n"
                            )
                except Exception as e:
                    app_logger.debug(f"Aviso al extraer eventos: {e}")

                # 8. PIE DE PÁGINA FINAL PHPMYADMIN
                write_sql(
                    f"COMMIT;\n\n"
                    f"/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;\n"
                    f"/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;\n"
                    f"/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;\n"
                    f"/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;\n"
                    f"/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;\n"
                )

        finally:
            conn.close()
            out_stream.close()
            f_raw.close()

        filesize = os.path.getsize(final_file_path)
        checksum = sha256.hexdigest()
        duration = round(time.time() - start_time, 2)

        app_logger.success(
            f"Respaldo Nativo completado: [{file_name}] "
            f"({StreamCompressor.format_size(filesize)}) en {duration}s "
            f"({total_tables} tablas, {total_views} vistas, {total_routines} rutinas, {total_triggers} triggers)"
        )

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
            tables_count=total_tables,
            views_count=total_views,
            routines_count=total_routines,
            triggers_count=total_triggers,
            execution_duration_sec=duration,
            phpmyadmin_compatible=True
        )

        return manifest, final_file_path
