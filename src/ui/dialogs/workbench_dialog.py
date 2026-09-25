"""
Diálogo modal para importar conexiones desde MySQL Workbench.
Muestra conexiones detectadas, permite ingresar contraseñas, probar conectividad
y auto-descubrir las bases de datos asociadas en bloque.
"""

from tkinter import filedialog
from typing import Any, Callable, Dict, List, Optional
import customtkinter as ctk
from src.core.logger import app_logger
from src.core.security import secret_manager
from src.models.server import ServerConfig
from src.services.connection_service import ConnectionService
from src.services.workbench_importer import WorkbenchImporter
from src.ui.theme import (
    ACCENT_DANGER, ACCENT_PRIMARY, ACCENT_SUCCESS,
    BG_CARD, BG_INPUT, BG_MAIN, BORDER_COLOR,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_SUBTITLE,
    TEXT_MAIN, TEXT_MUTED
)


class WorkbenchDialog(ctk.CTkToplevel):
    """Modal para importar perfiles desde MySQL Workbench."""

    def __init__(self, master, on_imported_callback: Optional[Callable[[List[ServerConfig]], None]] = None):
        super().__init__(master)
        self.on_imported_callback = on_imported_callback

        self.title("Importar Conexiones desde MySQL Workbench")
        self.geometry("720x620")
        self.minsize(580, 480)
        self.configure(fg_color=BG_MAIN)
        self.grab_set()

        self.current_xml_path = WorkbenchImporter.get_default_connections_path()
        self.conn_items: List[Dict[str, Any]] = []
        self._row_widgets: List[Dict[str, Any]] = []

        self._build_ui()
        self._load_connections()

    def _build_ui(self) -> None:
        """Construye los controles con el footer anclado abajo para visibilidad garantizada."""
        # 1. Footer inferior anclado PRIMERO
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=20, pady=(10, 16))

        cancel_btn = ctk.CTkButton(
            footer,
            text="Cancelar",
            width=100,
            height=36,
            fg_color="#2D333F",
            hover_color="#374151",
            command=self.destroy
        )
        cancel_btn.pack(side="right", padx=(10, 0))

        self.import_btn = ctk.CTkButton(
            footer,
            text="📥 Importar Seleccionados",
            width=180,
            height=36,
            font=FONT_BODY_BOLD,
            fg_color=ACCENT_SUCCESS,
            hover_color="#059669",
            command=self._on_import_clicked
        )
        self.import_btn.pack(side="right")

        self.auto_discover_chk = ctk.CTkCheckBox(
            footer,
            text="Auto-descubrir BDs al importar",
            font=FONT_SMALL,
            fg_color=ACCENT_PRIMARY
        )
        self.auto_discover_chk.select()
        self.auto_discover_chk.pack(side="left")

        # 2. Header superior
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=20, pady=(16, 8))

        ctk.CTkLabel(header, text="🐬 Importar desde MySQL Workbench", font=FONT_SUBTITLE, text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Detecta perfiles configurados en Workbench para agregarlos directamente a MySqlAutoBkps.",
            font=FONT_SMALL,
            text_color=TEXT_MUTED
        ).pack(anchor="w")

        # Selector de archivo connections.xml
        path_bar = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        path_bar.pack(side="top", fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(path_bar, text="Archivo:", font=FONT_SMALL, text_color=TEXT_MUTED).pack(side="left", padx=(12, 4))
        self.path_lbl = ctk.CTkLabel(
            path_bar,
            text=self.current_xml_path or "No detectado automáticamente",
            font=FONT_SMALL,
            text_color=TEXT_MAIN,
            anchor="w"
        )
        self.path_lbl.pack(side="left", fill="x", expand=True, padx=4)

        browse_btn = ctk.CTkButton(
            path_bar,
            text="Examinar...",
            width=85,
            height=26,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=self._browse_xml
        )
        browse_btn.pack(side="right", padx=8, pady=6)

        # 3. Contenedor scrollable central
        self.scroll_list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_list.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 10))

    def _browse_xml(self) -> None:
        """Permite al usuario elegir un archivo connections.xml manualmente."""
        chosen = filedialog.askopenfilename(
            title="Seleccionar archivo connections.xml de MySQL Workbench",
            filetypes=[("Archivos XML", "*.xml"), ("Todos los archivos", "*.*")]
        )
        if chosen:
            self.current_xml_path = chosen
            self.path_lbl.configure(text=chosen)
            self._load_connections()

    def _load_connections(self) -> None:
        """Carga las conexiones usando WorkbenchImporter."""
        for w in self.scroll_list.winfo_children():
            w.destroy()
        self._row_widgets.clear()

        if not self.current_xml_path or not os.path.isfile(self.current_xml_path):
            empty = ctk.CTkFrame(self.scroll_list, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
            empty.pack(fill="x", pady=20)
            ctk.CTkLabel(empty, text="No se encontró el archivo connections.xml de MySQL Workbench.", font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(pady=(16, 4))
            ctk.CTkLabel(empty, text="Usa el botón 'Examinar...' para localizarlo manualmente.", font=FONT_SMALL, text_color=TEXT_MUTED).pack(pady=(0, 16))
            return

        self.conn_items = WorkbenchImporter.parse_connections_file(self.current_xml_path)

        if not self.conn_items:
            empty = ctk.CTkFrame(self.scroll_list, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
            empty.pack(fill="x", pady=20)
            ctk.CTkLabel(empty, text="No se encontraron conexiones configuradas en el archivo.", font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(pady=(16, 4))
            return

        for item in self.conn_items:
            self._render_conn_card(item)

    def _render_conn_card(self, item: Dict[str, Any]) -> None:
        """Renderiza una tarjeta para cada conexión de Workbench."""
        card = ctk.CTkFrame(self.scroll_list, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="x", pady=4)

        # Header con Checkbox y Datos
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 4))

        chk = ctk.CTkCheckBox(row1, text="", width=20, fg_color=ACCENT_PRIMARY)
        chk.select()
        chk.pack(side="left", padx=(0, 8))

        title_lbl = ctk.CTkLabel(
            row1,
            text=f"🐬 {item.get('name')}  ({item.get('host')}:{item.get('port')})",
            font=FONT_BODY_BOLD,
            text_color=TEXT_MAIN
        )
        title_lbl.pack(side="left")

        details_str = f"Usuario: {item.get('user')}  |  SSL: {'Sí' if item.get('ssl') else 'No'}"
        if item.get("server_version"):
            details_str += f"  |  Versión: {item.get('server_version')}"

        ctk.CTkLabel(row1, text=details_str, font=FONT_SMALL, text_color=TEXT_MUTED).pack(side="right")

        # Fila de contraseña y prueba
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(row2, text="Contraseña:", font=FONT_SMALL, text_color=TEXT_MUTED).pack(side="left", padx=(28, 6))

        pwd_entry = ctk.CTkEntry(
            row2,
            placeholder_text="Ingresa la contraseña de la conexión...",
            show="•",
            width=220,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR
        )
        if item.get("password"):
            pwd_entry.insert(0, item.get("password"))
        pwd_entry.pack(side="left", padx=(0, 8))

        test_btn = ctk.CTkButton(
            row2,
            text="🔌 Probar",
            width=70,
            height=26,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151"
        )
        test_btn.pack(side="left", padx=(0, 8))

        test_lbl = ctk.CTkLabel(row2, text="", font=FONT_SMALL)
        test_lbl.pack(side="left")

        def on_test(it=item, pe=pwd_entry, tl=test_lbl):
            tl.configure(text="Probando...", text_color=TEXT_MUTED)
            self.update_idletasks()
            temp_server = ServerConfig(
                name=it.get("name", "Test"),
                host=it.get("host", "127.0.0.1"),
                port=it.get("port", 3306),
                user=it.get("user", "root"),
                encrypted_password=secret_manager.encrypt_text(pe.get()),
                ssl_enabled=it.get("ssl", False)
            )
            success, msg, ver = ConnectionService.test_connection(temp_server)
            if success:
                tl.configure(text=f"✓ Conectado ({ver})", text_color=ACCENT_SUCCESS)
            else:
                tl.configure(text=f"✕ Error", text_color=ACCENT_DANGER)

        test_btn.configure(command=on_test)

        self._row_widgets.append({
            "item": item,
            "chk": chk,
            "pwd_entry": pwd_entry
        })

    def _on_import_clicked(self) -> None:
        """Importa las conexiones seleccionadas."""
        imported_servers: List[ServerConfig] = []
        should_discover = bool(self.auto_discover_chk.get())

        for row in self._row_widgets:
            if not row["chk"].get():
                continue

            item = row["item"]
            raw_pwd = row["pwd_entry"].get()
            encrypted_pwd = secret_manager.encrypt_text(raw_pwd)

            server = ServerConfig(
                name=item.get("name") or f"Workbench {item.get('host')}",
                host=item.get("host", "127.0.0.1"),
                port=item.get("port", 3306),
                user=item.get("user", "root"),
                encrypted_password=encrypted_pwd,
                ssl_enabled=item.get("ssl", False),
                server_version=item.get("server_version")
            )

            # Auto-descubrir BDs si está marcado
            if should_discover:
                try:
                    dbs = ConnectionService.discover_databases(server)
                    server.databases = dbs
                except Exception as e:
                    app_logger.warning(f"No se pudieron auto-descubrir BDs para [{server.name}]: {e}")

            imported_servers.append(server)

        if self.on_imported_callback and imported_servers:
            self.on_imported_callback(imported_servers)

        app_logger.success(f"Se importaron {len(imported_servers)} servidores desde MySQL Workbench.")
        self.destroy()
