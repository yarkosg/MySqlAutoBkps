"""
Detector inteligente de ejecutables MySQL / MariaDB (mysqldump, mariadb-dump, mysqlbinlog, mysql).
Escanea el PATH del sistema operativo y rutas estándar conocidas en entornos Windows/Linux
(tales como XAMPP, Laragon, WampServer, MySQL Server oficial, MariaDB, Docker client).
"""

import glob
import os
import shutil
import sys
from typing import Dict, List, Optional
from src.core.logger import app_logger


class BinaryDetector:
    """Localiza y valida ejecutables requeridos para las operaciones de volcado y logs."""

    @staticmethod
    def _get_common_search_paths() -> List[str]:
        """Devuelve rutas de directorios habituales en Windows y Unix donde se instala MySQL/MariaDB."""
        paths: List[str] = []

        if sys.platform == "win32":
            # Rutas típicas en Windows
            candidates = [
                # XAMPP
                r"C:\xampp\mysql\bin",
                r"D:\xampp\mysql\bin",
                # Laragon (búsqueda dinámica en carpetas de mysql)
                r"C:\laragon\bin\mysql\*\bin",
                r"D:\laragon\bin\mysql\*\bin",
                # WampServer
                r"C:\wamp64\bin\mysql\*\bin",
                r"C:\wamp\bin\mysql\*\bin",
                # Instalaciones Oficiales MySQL
                r"C:\Program Files\MySQL\MySQL Server *\bin",
                r"C:\Program Files (x86)\MySQL\MySQL Server *\bin",
                # MariaDB Oficial
                r"C:\Program Files\MariaDB *\bin",
                r"C:\Program Files (x86)\MariaDB *\bin",
                # Scoop & Chocolatey
                r"C:\ProgramData\chocolatey\bin",
                os.path.expandvars(r"%USERPROFILE%\scoop\shims"),
            ]
            for pattern in candidates:
                if "*" in pattern:
                    for matched_dir in glob.glob(pattern):
                        if os.path.isdir(matched_dir):
                            paths.append(matched_dir)
                elif os.path.isdir(pattern):
                    paths.append(pattern)
        else:
            # Rutas en Linux / macOS
            unix_paths = [
                "/usr/bin",
                "/usr/local/bin",
                "/usr/local/mysql/bin",
                "/opt/lampp/bin",
                "/opt/homebrew/bin"
            ]
            for p in unix_paths:
                if os.path.isdir(p):
                    paths.append(p)

        return paths

    @classmethod
    def find_binary(cls, binary_name: str, custom_path: Optional[str] = None) -> Optional[str]:
        """
        Busca un ejecutable específico por prioridad:
        1. Ruta personalizada indicada por el usuario
        2. PATH del sistema operativo (shutil.which)
        3. Directorios de stacks comunes (XAMPP, Laragon, etc.)
        """
        # 1. Si el usuario definió una ruta específica y existe
        if custom_path and os.path.isfile(custom_path):
            return os.path.abspath(custom_path)

        # 2. Buscar en el PATH del sistema
        which_result = shutil.which(binary_name)
        if which_result:
            return os.path.abspath(which_result)

        # Si en Windows no se incluyó extensión .exe
        if sys.platform == "win32" and not binary_name.endswith(".exe"):
            which_exe = shutil.which(f"{binary_name}.exe")
            if which_exe:
                return os.path.abspath(which_exe)

        # 3. Escaneo exhaustivo en rutas comunes
        executable_names = [binary_name]
        if sys.platform == "win32" and not binary_name.endswith(".exe"):
            executable_names.append(f"{binary_name}.exe")

        for directory in cls._get_common_search_paths():
            for exe in executable_names:
                full_path = os.path.join(directory, exe)
                if os.path.isfile(full_path):
                    app_logger.debug(f"Ejecutable '{binary_name}' detectado en: {full_path}")
                    return os.path.abspath(full_path)

        return None

    @classmethod
    def get_mysqldump_path(cls, custom_path: Optional[str] = None) -> Optional[str]:
        """Busca mysqldump o mariadb-dump."""
        # Primero intentar mariadb-dump o mysqldump
        found = cls.find_binary("mysqldump", custom_path)
        if not found:
            found = cls.find_binary("mariadb-dump", custom_path)
        return found

    @classmethod
    def get_mysqlbinlog_path(cls, custom_path: Optional[str] = None) -> Optional[str]:
        """Busca mysqlbinlog o mariadb-binlog."""
        found = cls.find_binary("mysqlbinlog", custom_path)
        if not found:
            found = cls.find_binary("mariadb-binlog", custom_path)
        return found

    @classmethod
    def diagnose_tools(cls) -> Dict[str, Optional[str]]:
        """Realiza un diagnóstico de todas las herramientas requeridas y retorna sus rutas."""
        return {
            "mysqldump": cls.get_mysqldump_path(),
            "mysqlbinlog": cls.get_mysqlbinlog_path(),
            "mysql_client": cls.find_binary("mysql") or cls.find_binary("mariadb")
        }
