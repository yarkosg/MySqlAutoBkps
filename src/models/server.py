"""
Modelo de datos para Servidores MySQL / MariaDB.
Agrupa las bases de datos pertenecientes al host y mantiene las credenciales cifradas.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from src.models.database import DatabaseConfig


@dataclass
class ServerConfig:
    """Configuración de conexión a un servidor MySQL/MariaDB y sus bases de datos agrupadas."""
    name: str
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    encrypted_password: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ssl_enabled: bool = False
    databases: List[DatabaseConfig] = field(default_factory=list)
    notes: str = ""
    server_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializa la configuración del servidor excluyendo contraseñas en claro."""
        return {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "encrypted_password": self.encrypted_password,
            "ssl_enabled": self.ssl_enabled,
            "notes": self.notes,
            "server_version": self.server_version,
            "databases": [db.to_dict() for db in self.databases]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServerConfig":
        """Instancia un ServerConfig a partir de un diccionario."""
        server_id = data.get("id") or str(uuid.uuid4())
        dbs_raw = data.get("databases", [])
        dbs = [DatabaseConfig.from_dict(d) for d in dbs_raw]

        return cls(
            id=server_id,
            name=data.get("name", "Servidor MySQL"),
            host=data.get("host", "127.0.0.1"),
            port=int(data.get("port", 3306)),
            user=data.get("user", "root"),
            encrypted_password=data.get("encrypted_password", ""),
            ssl_enabled=bool(data.get("ssl_enabled", False)),
            notes=data.get("notes", ""),
            server_version=data.get("server_version"),
            databases=dbs
        )

    def get_database(self, name: str) -> Optional[DatabaseConfig]:
        """Busca una base de datos por nombre."""
        for db in self.databases:
            if db.name.lower() == name.lower():
                return db
        return None

    def add_or_update_database(self, db_config: DatabaseConfig) -> None:
        """Añade o actualiza una base de datos en la lista del servidor."""
        existing = self.get_database(db_config.name)
        if existing:
            existing.charset = db_config.charset
            existing.collation = db_config.collation
            existing.enabled = db_config.enabled
            existing.retention_days = db_config.retention_days
        else:
            self.databases.append(db_config)
