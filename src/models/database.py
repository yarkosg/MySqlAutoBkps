"""
Modelo de datos para bases de datos individuales dentro de un servidor.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class DatabaseConfig:
    """Representa una base de datos gestionada para respaldos."""
    name: str
    charset: str = "utf8mb4"
    collation: str = "utf8mb4_general_ci"
    enabled: bool = True
    retention_days: int = 30
    last_backup_time: Optional[str] = None
    last_backup_status: Optional[str] = None
    total_backups_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario estándar."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatabaseConfig":
        """Instancia a partir de un diccionario."""
        return cls(
            name=data.get("name", ""),
            charset=data.get("charset", "utf8mb4"),
            collation=data.get("collation", "utf8mb4_general_ci"),
            enabled=data.get("enabled", True),
            retention_days=data.get("retention_days", 30),
            last_backup_time=data.get("last_backup_time"),
            last_backup_status=data.get("last_backup_status"),
            total_backups_count=data.get("total_backups_count", 0)
        )
