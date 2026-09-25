"""
Servicio para importar conexiones desde MySQL Workbench.
Detecta automáticamente el archivo connections.xml en Windows (%APPDATA%), Linux y macOS,
extrayendo servidores, hosts, puertos, usuarios, esquemas y configuraciones SSL.
"""

import os
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from src.core.logger import app_logger


class WorkbenchImporter:
    """Importador de perfiles de conexión de MySQL Workbench."""

    @classmethod
    def get_default_connections_path(cls) -> Optional[str]:
        """Localiza la ruta por defecto del archivo connections.xml según el sistema operativo."""
        candidate_paths = []

        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                candidate_paths.append(os.path.join(appdata, "MySQL", "Workbench", "connections.xml"))
            userprofile = os.environ.get("USERPROFILE", "")
            if userprofile:
                candidate_paths.append(os.path.join(userprofile, "AppData", "Roaming", "MySQL", "Workbench", "connections.xml"))
        elif sys.platform == "darwin":
            home = os.path.expanduser("~")
            candidate_paths.append(os.path.join(home, "Library", "Application Support", "MySQL", "Workbench", "connections.xml"))
        else:
            home = os.path.expanduser("~")
            candidate_paths.append(os.path.join(home, ".mysql", "workbench", "connections.xml"))

        for path in candidate_paths:
            if os.path.isfile(path):
                return os.path.abspath(path)

        return None

    @classmethod
    def parse_connections_file(cls, xml_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Analiza el archivo XML de MySQL Workbench y retorna una lista de conexiones descubiertas.
        """
        target_path = xml_path or cls.get_default_connections_path()
        if not target_path or not os.path.isfile(target_path):
            app_logger.warning("No se encontró el archivo connections.xml de MySQL Workbench.")
            return []

        connections: List[Dict[str, Any]] = []

        try:
            tree = ET.parse(target_path)
            root = tree.getroot()

            for conn_elem in root.iter("value"):
                if conn_elem.attrib.get("struct-name") == "db.mgmt.Connection":
                    conn_info: Dict[str, Any] = {
                        "name": "",
                        "host": "127.0.0.1",
                        "port": 3306,
                        "user": "root",
                        "password": "",
                        "ssl": False,
                        "schema": "",
                        "server_version": ""
                    }

                    for child in conn_elem:
                        key = child.attrib.get("key")
                        if key == "name":
                            conn_info["name"] = child.text or "Conexión Workbench"
                        elif key == "parameterValues":
                            for param in child:
                                p_key = param.attrib.get("key")
                                if p_key == "hostName":
                                    conn_info["host"] = param.text or "127.0.0.1"
                                elif p_key == "port":
                                    try:
                                        conn_info["port"] = int(param.text or 3306)
                                    except ValueError:
                                        conn_info["port"] = 3306
                                elif p_key == "userName":
                                    conn_info["user"] = param.text or "root"
                                elif p_key == "schema":
                                    conn_info["schema"] = param.text or ""
                                elif p_key == "serverVersion":
                                    conn_info["server_version"] = param.text or ""
                                elif p_key == "useSSL":
                                    # 1 o 2 indica SSL habilitado en Workbench
                                    val = param.text or "0"
                                    conn_info["ssl"] = val in ("1", "2")
                                elif p_key == "password":
                                    conn_info["password"] = param.text or ""

                    if conn_info["name"] or conn_info["host"] != "127.0.0.1":
                        if not conn_info["name"]:
                            conn_info["name"] = f"Workbench ({conn_info['host']})"
                        connections.append(conn_info)

            app_logger.info(f"Se encontraron {len(connections)} conexiones en MySQL Workbench ({target_path}).")
            return connections

        except Exception as e:
            app_logger.error(f"Error parseando archivo de MySQL Workbench: {e}")
            return []
