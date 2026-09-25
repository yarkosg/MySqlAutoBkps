"""
Servicio de políticas de retención para MySqlAutoBkps.
Elimina automáticamente respaldos obsoletos según días de antigüedad o número máximo
de versiones por base de datos, optimizando el espacio en disco sin romper cadenas incrementales activas.
"""

import os
from datetime import datetime, timedelta
from typing import List, Tuple
from src.core.logger import app_logger
from src.models.manifest import BackupManifest, BackupType


class RetentionService:
    """Aplica reglas de depuración de respaldos antiguos."""

    @classmethod
    def apply_retention(
        cls,
        manifests: List[BackupManifest],
        max_days: int = 30,
        max_versions: int = 10
    ) -> Tuple[List[BackupManifest], List[str]]:
        """
        Evalúa la lista de manifiestos y elimina los archivos físicos caducados.

        Retorna:
            Tuple[manifiestos_restantes, rutas_archivos_eliminados]
        """
        if not manifests:
            return [], []

        cutoff_date = datetime.now() - timedelta(days=max_days)
        deleted_files: List[str] = []
        remaining_manifests: List[BackupManifest] = []

        # Agrupar manifiestos por servidor y base de datos
        groups = {}
        for m in manifests:
            key = f"{m.server_id}::{m.database_name}"
            groups.setdefault(key, []).append(m)

        for key, group in groups.items():
            # Ordenar del más reciente al más antiguo
            group.sort(
                key=lambda x: datetime.strptime(x.created_at, "%Y-%m-%d %H:%M:%S")
                if x.created_at else datetime.min,
                reverse=True
            )

            # Conservar hasta max_versions, descartar los restantes
            for idx, item in enumerate(group):
                should_delete = False

                # 1. Condición por versión máxima
                if max_versions > 0 and idx >= max_versions:
                    should_delete = True

                # 2. Condición por antigüedad en días
                if max_days > 0 and item.created_at:
                    try:
                        item_date = datetime.strptime(item.created_at, "%Y-%m-%d %H:%M:%S")
                        if item_date < cutoff_date:
                            should_delete = True
                    except ValueError:
                        pass

                # Protección: si es un FULL que tiene incrementales activos más recientes, conservarlo
                if should_delete and item.backup_type == BackupType.FULL:
                    has_active_children = any(
                        child.base_backup_id == item.backup_id and child in remaining_manifests
                        for child in group
                    )
                    if has_active_children:
                        should_delete = False

                if should_delete:
                    if os.path.exists(item.file_path):
                        try:
                            os.remove(item.file_path)
                            deleted_files.append(item.file_path)
                            app_logger.info(f"Retención: Respaldo eliminado [{item.file_name}]")
                        except Exception as e:
                            app_logger.warning(f"No se pudo eliminar archivo de respaldo caducado: {e}")
                else:
                    remaining_manifests.append(item)

        return remaining_manifests, deleted_files
