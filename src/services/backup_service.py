"""
Servicio principal de orquestación de respaldos para MySqlAutoBkps.
Coordina respaldos manuales y programados, gestiona el registro de manifiestos,
mantiene la cadena de respaldos incrementales y aplica políticas de retención.
"""

import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from src.core.config import config_manager
from src.core.exceptions import BackupExecutionError
from src.core.logger import app_logger
from src.engine.dump_engine import DumpEngine
from src.engine.incremental_engine import IncrementalEngine
from src.models.manifest import BackupManifest, BackupType
from src.models.server import ServerConfig
from src.services.retention_service import RetentionService


class BackupService:
    """Orquestador central para respaldos de bases de datos individuales o servidores completos."""

    def __init__(self):
        settings = config_manager.load_settings()
        self.backups_dir = settings.get("backups_dir", os.path.join(os.getcwd(), "backups"))
        self.manifest_file = os.path.join(self.backups_dir, "manifests.json")

        self.dump_engine = DumpEngine(settings.get("mysqldump_path"))
        self.incremental_engine = IncrementalEngine(settings.get("mysqlbinlog_path"))

        self._ensure_manifests_file()

    def _ensure_manifests_file(self) -> None:
        """Crea el archivo de manifiestos si no existe."""
        os.makedirs(self.backups_dir, exist_ok=True)
        if not os.path.exists(self.manifest_file):
            try:
                with open(self.manifest_file, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
            except Exception as e:
                app_logger.error(f"Error creando archivo de manifiestos: {e}")

    def load_manifests(self) -> List[BackupManifest]:
        """Carga el historial completo de respaldos."""
        self._ensure_manifests_file()
        try:
            with open(self.manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [BackupManifest.from_dict(item) for item in data]
        except Exception as e:
            app_logger.error(f"Error leyendo manifiestos: {e}")
            return []

    def save_manifests(self, manifests: List[BackupManifest]) -> None:
        """Guarda la lista de manifiestos en disco de forma atómica."""
        self._ensure_manifests_file()
        try:
            payload = [m.to_dict() for m in manifests]
            temp_file = self.manifest_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            import shutil
            shutil.move(temp_file, self.manifest_file)
        except Exception as e:
            app_logger.error(f"Error guardando manifiestos: {e}")

    def add_manifest(self, manifest: BackupManifest) -> None:
        """Añade un nuevo manifiesto al registro histórico y aplica retención."""
        manifests = self.load_manifests()
        manifests.append(manifest)

        # Aplicar retención automática configurada
        settings = config_manager.load_settings()
        max_days = int(settings.get("default_retention_days", 30))
        max_versions = int(settings.get("default_max_versions", 10))

        remaining, deleted = RetentionService.apply_retention(
            manifests=manifests,
            max_days=max_days,
            max_versions=max_versions
        )
        self.save_manifests(remaining)

    def get_latest_base_manifest(self, server_id: str, database_name: str) -> Optional[BackupManifest]:
        """Busca el último respaldo FULL exitoso para una base de datos específica."""
        manifests = self.load_manifests()
        full_manifests = [
            m for m in manifests
            if m.server_id == server_id
            and m.database_name.lower() == database_name.lower()
            and m.backup_type == BackupType.FULL
            and os.path.exists(m.file_path)
        ]
        if not full_manifests:
            return None
        # Ordenar por fecha descendente
        full_manifests.sort(key=lambda x: x.created_at, reverse=True)
        return full_manifests[0]

    def get_incremental_chain_index(self, base_id: str) -> int:
        """Calcula el número secuencial en la cadena incremental."""
        manifests = self.load_manifests()
        chain = [m for m in manifests if m.base_backup_id == base_id]
        return len(chain) + 1

    def backup_database(
        self,
        server: ServerConfig,
        database_name: str,
        backup_type: BackupType = BackupType.FULL,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> BackupManifest:
        """
        Ejecuta el respaldo de una base de datos específica (FULL o INCREMENTAL).
        """
        settings = config_manager.load_settings()
        compress = settings.get("compression_enabled", True)
        comp_level = settings.get("compression_level", 6)

        # Si se solicita INCREMENTAL, verificar si existe un FULL previo
        if backup_type == BackupType.INCREMENTAL:
            base_manifest = self.get_latest_base_manifest(server.id, database_name)
            if not base_manifest:
                app_logger.warning(
                    f"No existe un respaldo base previo para [{database_name}]. "
                    f"Se creará un respaldo FULL inicial como ancla de la cadena."
                )
                backup_type = BackupType.FULL
            else:
                chain_idx = self.get_incremental_chain_index(base_manifest.backup_id)
                manifest, path = self.incremental_engine.execute_incremental_backup(
                    server=server,
                    database_name=database_name,
                    output_directory=self.backups_dir,
                    base_manifest=base_manifest,
                    chain_index=chain_idx,
                    compress=compress,
                    compression_level=comp_level,
                    progress_callback=progress_callback
                )
                self.add_manifest(manifest)
                return manifest

        # Ejecución FULL
        manifest, path = self.dump_engine.execute_dump(
            server=server,
            database_name=database_name,
            output_directory=self.backups_dir,
            compress=compress,
            compression_level=comp_level,
            progress_callback=progress_callback
        )
        self.add_manifest(manifest)
        return manifest

    def backup_server(
        self,
        server: ServerConfig,
        backup_type: BackupType = BackupType.FULL,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[BackupManifest]:
        """
        Respalda todas las bases de datos habilitadas de un servidor.
        """
        enabled_dbs = [db for db in server.databases if db.enabled]
        if not enabled_dbs:
            app_logger.warning(f"No hay bases de datos activas seleccionadas en [{server.name}].")
            return []

        results: List[BackupManifest] = []
        total = len(enabled_dbs)

        for idx, db in enumerate(enabled_dbs, start=1):
            if progress_callback:
                progress_callback(db.name, idx, total)
            try:
                manifest = self.backup_database(server, db.name, backup_type)
                results.append(manifest)
                db.last_backup_time = manifest.created_at
                db.last_backup_status = "SUCCESS"
                db.total_backups_count += 1
            except Exception as e:
                db.last_backup_time = time.strftime("%Y-%m-%d %H:%M:%S")
                db.last_backup_status = f"ERROR: {str(e)}"
                app_logger.error(f"Fallo en base de datos [{db.name}]: {e}")

        return results

    @staticmethod
    def generate_phpmyadmin_restore_instructions(manifest: BackupManifest) -> str:
        """Genera una guía paso a paso para restaurar el respaldo en phpMyAdmin."""
        is_gz = manifest.file_name.endswith(".gz")
        guide = (
            f"=== GUÍA DE RESTAURACIÓN PARA PHPMYADMIN ===\n"
            f"Archivo: {manifest.file_name}\n"
            f"Tipo: {manifest.backup_type.value}\n"
            f"Base de Datos destino recomendada: {manifest.database_name}\n\n"
            f"PASOS:\n"
            f"1. Abre phpMyAdmin en tu navegador.\n"
            f"2. En la barra lateral izquierda, selecciona la base de datos '{manifest.database_name}'\n"
            f"   (o crea una nueva vacía con cotejamiento utf8mb4_general_ci).\n"
            f"3. Haz clic en la pestaña superior 'Importar' (Import).\n"
            f"4. En 'Seleccionar archivo', elige el archivo de respaldo:\n"
            f"   {manifest.file_path}\n"
            f"   * Nota: phpMyAdmin acepta archivos comprimidos .sql.gz directamente sin descomprimir.\n"
            f"5. Deja el conjunto de caracteres en 'utf-8' y haz clic en 'Importar' (o 'Continuar').\n"
        )
        if manifest.backup_type == BackupType.INCREMENTAL:
            guide += (
                f"\n⚠️ IMPORTANTE (INCREMENTAL):\n"
                f"Este es un respaldo incremental (Cadena #{manifest.chain_index}).\n"
                f"Debes haber restaurado primero el respaldo FULL base (ID: {manifest.base_backup_id})\n"
                f"y luego los incrementales en orden numérico antes de este archivo.\n"
            )
        return guide
