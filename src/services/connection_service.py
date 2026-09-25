"""
Servicio de conexión y descubrimiento para MySQL y MariaDB.
Valida conectividad, autenticación segura y permite descubrir automáticamente
las bases de datos existentes en el servidor sin necesidad de que el usuario las escriba una a una.
"""

from typing import Any, Dict, List, Optional, Tuple
import pymysql
from src.core.exceptions import DatabaseConnectionError
from src.core.logger import app_logger
from src.core.security import secret_manager
from src.models.database import DatabaseConfig
from src.models.server import ServerConfig


class ConnectionService:
    """Gestiona pruebas de conexión y auto-descubrimiento de metadatos del servidor."""

    SYSTEM_DATABASES = {
        "information_schema",
        "performance_schema",
        "sys",
        "mysql"
    }

    @classmethod
    def get_raw_connection(cls, server: ServerConfig, database: Optional[str] = None) -> pymysql.Connection:
        """Crea una conexión pymysql directa al servidor utilizando la contraseña descifrada."""
        raw_password = secret_manager.decrypt_text(server.encrypted_password)
        try:
            return pymysql.connect(
                host=server.host,
                port=server.port,
                user=server.user,
                password=raw_password,
                database=database,
                ssl={"ssl": True} if server.ssl_enabled else None,
                connect_timeout=8,
                cursorclass=pymysql.cursors.DictCursor
            )
        except pymysql.MySQLError as e:
            code, msg = e.args if len(e.args) >= 2 else (0, str(e))
            raise DatabaseConnectionError(
                f"Error al conectar con [{server.name}] ({server.host}:{server.port})",
                details=f"[Código {code}] {msg}"
            )
        except Exception as e:
            raise DatabaseConnectionError(
                f"Error inesperado al conectar con [{server.name}]",
                details=str(e)
            )

    @classmethod
    def test_connection(cls, server: ServerConfig) -> Tuple[bool, str, Optional[str]]:
        """
        Prueba la conexión al servidor.
        Retorna:
            Tuple[exito: bool, mensaje: str, version_detectada: Optional[str]]
        """
        try:
            conn = cls.get_raw_connection(server)
            with conn.cursor() as cursor:
                cursor.execute("SELECT VERSION() AS ver, @@character_set_server AS charset")
                row = cursor.fetchone()
                version = row.get("ver", "Desconocida") if row else "Desconocida"
                charset = row.get("charset", "utf8mb4") if row else "utf8mb4"

            conn.close()
            msg = f"Conexión exitosa a {version} (Charset: {charset})"
            app_logger.success(f"[{server.name}] {msg}")
            return True, msg, version

        except DatabaseConnectionError as dbe:
            app_logger.error(str(dbe))
            return False, str(dbe), None
        except Exception as e:
            app_logger.error(f"Fallo en prueba de conexión: {e}")
            return False, str(e), None

    @classmethod
    def discover_databases(
        cls,
        server: ServerConfig,
        include_system_dbs: bool = False
    ) -> List[DatabaseConfig]:
        """
        Consulta el servidor mediante SHOW DATABASES y devuelve una lista de DatabaseConfig
        con su charset y collation reales.
        """
        discovered: List[DatabaseConfig] = []
        conn = cls.get_raw_connection(server)

        try:
            with conn.cursor() as cursor:
                cursor.execute("SHOW DATABASES")
                rows = cursor.fetchall()
                db_names = [r["Database"] for r in rows if "Database" in r]

                for name in db_names:
                    is_system = name.lower() in cls.SYSTEM_DATABASES
                    if is_system and not include_system_dbs:
                        continue

                    # Consultar collation predeterminado de la base de datos
                    charset = "utf8mb4"
                    collation = "utf8mb4_general_ci"
                    try:
                        cursor.execute(
                            "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
                            "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s",
                            (name,)
                        )
                        schema_info = cursor.fetchone()
                        if schema_info:
                            charset = schema_info.get("DEFAULT_CHARACTER_SET_NAME") or charset
                            collation = schema_info.get("DEFAULT_COLLATION_NAME") or collation
                    except Exception:
                        pass

                    discovered.append(DatabaseConfig(
                        name=name,
                        charset=charset,
                        collation=collation,
                        enabled=True
                    ))

            app_logger.info(f"Se descubrieron {len(discovered)} bases de datos en [{server.name}].")
            return discovered

        finally:
            conn.close()
