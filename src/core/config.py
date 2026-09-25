"""
Gestor de configuración persistente para MySqlAutoBkps.
Controla el almacenamiento y carga de servidores, bases de datos agrupadas,
preferencias globales y tareas programadas.
Si los archivos de configuración no existen, los auto-crea silenciosamente.
"""

import json
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional
from src.core.exceptions import ConfigurationError
from src.core.logger import app_logger


class ConfigManager:
    """Administra la configuración del sistema, servidores y preferencias."""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            self.config_dir = os.path.join(os.getcwd(), "config")
        else:
            self.config_dir = config_dir

        self.servers_file = os.path.join(self.config_dir, "servers.enc.json")
        self.settings_file = os.path.join(self.config_dir, "settings.json")
        self.backups_default_dir = os.path.join(os.getcwd(), "backups")

        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        """Crea automáticamente los directorios y archivos de configuración si faltan."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            os.makedirs(self.backups_default_dir, exist_ok=True)

            # Auto-crear servers.enc.json inicial si no existe
            if not os.path.exists(self.servers_file):
                initial_servers_payload = {
                    "version": "1.0",
                    "servers": []
                }
                self._atomic_write_json(self.servers_file, initial_servers_payload)
                app_logger.info("Archivo de configuración de servidores inicializado automáticamente.")

            # Auto-crear settings.json inicial si no existe
            if not os.path.exists(self.settings_file):
                initial_settings_payload = {
                    "app_theme": "dark",
                    "dump_engine_mode": "native",
                    "mysqldump_path": "",
                    "mysqlbinlog_path": "",
                    "backups_dir": self.backups_default_dir,
                    "default_retention_days": 30,
                    "default_max_versions": 10,
                    "compression_enabled": True,
                    "compression_level": 6,
                    "notifications_enabled": True,
                    "auto_start_scheduler": False
                }
                self._atomic_write_json(self.settings_file, initial_settings_payload)
                app_logger.info("Archivo de ajustes globales inicializado automáticamente.")

        except Exception as e:
            raise ConfigurationError(
                "No se pudo inicializar la estructura de configuración",
                details=str(e)
            )

    def _atomic_write_json(self, file_path: str, data: Dict[str, Any]) -> None:
        """Escribe un archivo JSON de forma atómica para evitar corrupción por apagón o fallos."""
        dir_name = os.path.dirname(file_path)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=2, ensure_ascii=False)
            temp_name = tf.name

        shutil.move(temp_name, file_path)

    def load_servers(self) -> List[Dict[str, Any]]:
        """Carga la lista de servidores y sus bases de datos asociadas."""
        self._ensure_config_exists()
        try:
            with open(self.servers_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("servers", [])
        except Exception as e:
            app_logger.error(f"Error cargando archivo de servidores: {e}")
            return []

    def save_servers(self, servers: List[Dict[str, Any]]) -> None:
        """Guarda la lista de servidores de forma segura."""
        self._ensure_config_exists()
        try:
            payload = {
                "version": "1.0",
                "servers": servers
            }
            self._atomic_write_json(self.servers_file, payload)
            app_logger.debug("Servidores actualizados y guardados correctamente.")
        except Exception as e:
            raise ConfigurationError("Fallo al guardar servidores", details=str(e))

    def load_settings(self) -> Dict[str, Any]:
        """Carga las preferencias globales de la aplicación."""
        self._ensure_config_exists()
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            app_logger.error(f"Error cargando ajustes globales: {e}")
            return {}

    def save_settings(self, settings: Dict[str, Any]) -> None:
        """Guarda las preferencias globales de la aplicación."""
        self._ensure_config_exists()
        try:
            self._atomic_write_json(self.settings_file, settings)
            app_logger.info("Ajustes globales guardados exitosamente.")
        except Exception as e:
            raise ConfigurationError("Fallo al guardar ajustes globales", details=str(e))


# Instancia singleton predeterminada
config_manager = ConfigManager()
