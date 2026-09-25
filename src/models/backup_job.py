"""
Modelo para definición de tareas programadas (BackupJob) en MySqlAutoBkps.
Permite definir periodicidad (intervalo o expresión cron), tipo de respaldo y retención.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from src.models.manifest import BackupType


@dataclass
class BackupJob:
    """Configuración de una tarea periódica de respaldo."""
    name: str
    server_id: str
    database_name: str
    backup_type: BackupType = BackupType.FULL
    interval_minutes: int = 1440  # Por defecto cada 24 horas (1440 min)
    cron_expression: Optional[str] = None
    is_active: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    last_run_time: Optional[str] = None
    next_run_time: Optional[str] = None
    last_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializa la tarea a diccionario."""
        return {
            "id": self.id,
            "name": self.name,
            "server_id": self.server_id,
            "database_name": self.database_name,
            "backup_type": self.backup_type.value,
            "interval_minutes": self.interval_minutes,
            "cron_expression": self.cron_expression,
            "is_active": self.is_active,
            "last_run_time": self.last_run_time,
            "next_run_time": self.next_run_time,
            "last_status": self.last_status
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupJob":
        """Instancia un BackupJob desde un diccionario."""
        raw_type = data.get("backup_type", "FULL")
        btype = BackupType.INCREMENTAL if raw_type == "INCREMENTAL" else BackupType.FULL

        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            name=data.get("name", "Tarea de respaldo"),
            server_id=data.get("server_id", ""),
            database_name=data.get("database_name", ""),
            backup_type=btype,
            interval_minutes=int(data.get("interval_minutes", 1440)),
            cron_expression=data.get("cron_expression"),
            is_active=bool(data.get("is_active", True)),
            last_run_time=data.get("last_run_time"),
            next_run_time=data.get("next_run_time"),
            last_status=data.get("last_status")
        )
