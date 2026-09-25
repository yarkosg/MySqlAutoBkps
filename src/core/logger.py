"""
Módulo de registro (Logger) estructurado y multicanal.
Emite logs formateados a archivo local con rotación y permite registrar listeners
(callbacks) para actualizar la consola visual en tiempo real de forma segura.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Callable, List, Optional

# Nivel personalizado para operaciones exitosas
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")


class StructuredLogger:
    """Gestor centralizado de logging con soporte para archivo rotativo y emisión a GUI."""

    _instance: Optional["StructuredLogger"] = None
    _listeners: List[Callable[[str, str, str], None]] = []

    def __new__(cls) -> "StructuredLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self.logger = logging.getLogger("MySqlAutoBkps")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        # Formato estándar de consola y archivo
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)-7s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 1. Handler para Consola Estándar (CLI)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)

        # 2. Handler para Archivo Rotativo en logs/
        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, "mysql_autobkps.log")

        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        self._initialized = True

    def add_listener(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Registra una función callback para recibir logs en tiempo real.
        callback(timestamp: str, level: str, message: str)
        """
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, str, str], None]) -> None:
        """Desregistra un listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, level: str, message: str) -> None:
        """Notifica a todos los oyentes de la interfaz gráfica."""
        now = datetime.now().strftime("%H:%M:%S")
        for listener in self._listeners:
            try:
                listener(now, level, message)
            except Exception:
                pass  # Evita que un fallo en UI rompa el hilo de fondo

    def debug(self, msg: str) -> None:
        self.logger.debug(msg)
        self._notify_listeners("DEBUG", msg)

    def info(self, msg: str) -> None:
        self.logger.info(msg)
        self._notify_listeners("INFO", msg)

    def success(self, msg: str) -> None:
        self.logger.log(SUCCESS_LEVEL_NUM, msg)
        self._notify_listeners("SUCCESS", msg)

    def warning(self, msg: str) -> None:
        self.logger.warning(msg)
        self._notify_listeners("WARNING", msg)

    def error(self, msg: str) -> None:
        self.logger.error(msg)
        self._notify_listeners("ERROR", msg)


# Instancia singleton accesible globalmente
app_logger = StructuredLogger()
