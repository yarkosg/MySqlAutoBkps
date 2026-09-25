"""
Modelo de Manifiesto para Respaldos de MySqlAutoBkps.
Almacena la metadata forense, sumas de verificación (SHA256),
coordenadas de binlog para respaldos autoincrementales y cadena de dependencias.
"""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, Optional


class BackupType(str, Enum):
    """Tipo de respaldo realizado."""
    FULL = "FULL"
    INCREMENTAL = "INCREMENTAL"


@dataclass
class BackupManifest:
    """Metadatos completos de un respaldo para auditoría y restauración garantizada."""
    backup_id: str
    server_id: str
    server_name: str
    database_name: str
    backup_type: BackupType
    created_at: str
    file_path: str
    file_name: str
    file_size_bytes: int
    checksum_sha256: str
    compression: str = "gzip"
    binlog_file: Optional[str] = None
    binlog_position: Optional[int] = None
    base_backup_id: Optional[str] = None
    chain_index: int = 0
    tables_count: int = 0
    views_count: int = 0
    routines_count: int = 0
    triggers_count: int = 0
    execution_duration_sec: float = 0.0
    phpmyadmin_compatible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el manifiesto a diccionario JSON-friendly."""
        data = asdict(self)
        data["backup_type"] = self.backup_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupManifest":
        """Reconstruye un manifiesto desde un diccionario."""
        raw_type = data.get("backup_type", "FULL")
        btype = BackupType.INCREMENTAL if raw_type == "INCREMENTAL" else BackupType.FULL

        return cls(
            backup_id=data["backup_id"],
            server_id=data.get("server_id", ""),
            server_name=data.get("server_name", "Unknown"),
            database_name=data.get("database_name", "Unknown"),
            backup_type=btype,
            created_at=data.get("created_at", ""),
            file_path=data.get("file_path", ""),
            file_name=data.get("file_name", ""),
            file_size_bytes=int(data.get("file_size_bytes", 0)),
            checksum_sha256=data.get("checksum_sha256", ""),
            compression=data.get("compression", "gzip"),
            binlog_file=data.get("binlog_file"),
            binlog_position=data.get("binlog_position"),
            base_backup_id=data.get("base_backup_id"),
            chain_index=int(data.get("chain_index", 0)),
            tables_count=int(data.get("tables_count", 0)),
            views_count=int(data.get("views_count", 0)),
            routines_count=int(data.get("routines_count", 0)),
            triggers_count=int(data.get("triggers_count", 0)),
            execution_duration_sec=float(data.get("execution_duration_sec", 0.0)),
            phpmyadmin_compatible=bool(data.get("phpmyadmin_compatible", True))
        )
