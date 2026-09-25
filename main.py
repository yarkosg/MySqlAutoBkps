"""
Punto de entrada principal para MySqlAutoBkps.
Ejecuta la inicialización de archivos de configuración seguros y lanza la interfaz visual.
"""

import os
import sys

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.config import config_manager
from src.core.logger import app_logger
from src.ui.app import MainWindow


def main():
    """Función de inicio de la aplicación."""
    try:
        app_logger.info("Iniciando MySqlAutoBkps...")
        app = MainWindow()
        app.mainloop()
    except Exception as e:
        app_logger.error(f"Error crítico no controlado durante la ejecución: {e}")
        raise e


if __name__ == "__main__":
    main()
