"""
Diálogo modal para añadir y configurar servidores MySQL/MariaDB.
Diseñado con pie de ventana anclado y scroll interno para garantizar que el botón
'Guardar Servidor' esté 100% visible en cualquier resolución y escala de pantalla.
"""

from typing import Callable, List, Optional
import customtkinter as ctk
from src.core.logger import app_logger
from src.core.security import secret_manager
from src.models.database import DatabaseConfig
from src.models.server import ServerConfig
from src.services.connection_service import ConnectionService
from src.ui.theme import (
    ACCENT_DANGER, ACCENT_PRIMARY, ACCENT_SUCCESS,
    BG_CARD, BG_INPUT, BG_MAIN, BORDER_COLOR,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_SUBTITLE,
    TEXT_MAIN, TEXT_MUTED
)


class ServerDialog(ctk.CTkToplevel):
    """Ventana modal de configuración de servidor."""

    def __init__(
        self,
        master,
        server: Optional[ServerConfig] = None,
        on_save_callback: Optional[Callable[[ServerConfig], None]] = None
    ):
        super().__init__(master)
        self.server = server
        self.on_save_callback = on_save_callback

        self.title("Configurar Servidor MySQL / MariaDB" if server else "Añadir Nuevo Servidor")
        self.geometry("680x620")
        self.minsize(580, 500)
        self.resizable(True, True)
        self.configure(fg_color=BG_MAIN)
        self.grab_set()  # Modal bloqueante

        self.discovered_dbs: List[DatabaseConfig] = []
        self._db_checkboxes = {}
        self._detected_version = server.server_version if server else None

        self._build_ui()
        if server:
            self._populate_fields(server)

    def _build_ui(self) -> None:
        """Construye los controles garantizando visibilidad total del pie."""
        # 1. PIE DE VENTANA ANCLADO PRIMERO (Garantiza visibilidad en cualquier resolución)
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

        self.save_btn = ctk.CTkButton(
            footer,
            text="💾 Guardar Servidor",
            width=150,
            height=36,
            font=FONT_BODY_BOLD,
            fg_color=ACCENT_SUCCESS,
            hover_color="#059669",
            command=self._save
        )
        self.save_btn.pack(side="right")

        self.footer_status = ctk.CTkLabel(footer, text="", font=FONT_SMALL)
        self.footer_status.pack(side="left")

        # 2. ENCABEZADO SUPERIOR
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=20, pady=(16, 8))

        title_text = " Editar Servidor" if self.server else " Nuevo Servidor MySQL / MariaDB"
        ctk.CTkLabel(header, text=title_text, font=FONT_SUBTITLE, text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Configura los datos de acceso. Las contraseñas se almacenan cifradas con AES-Fernet.",
            font=FONT_SMALL,
            text_color=TEXT_MUTED
        ).pack(anchor="w")

        # 3. FORMULARIO CENTRAL CON SCROLL
        form_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form_scroll.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 10))

        form = ctk.CTkFrame(form_scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        form.pack(fill="both", expand=True)

        # Nombre Amigable
        ctk.CTkLabel(form, text="Nombre del Servidor (Identificador):", font=FONT_SMALL, text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 2))
        self.name_entry = ctk.CTkEntry(form, placeholder_text="Ej: Producción AWS / Local XAMPP", fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 10))

        # Host y Puerto
        ctk.CTkLabel(form, text="Host / IP:", font=FONT_SMALL, text_color=TEXT_MUTED).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 2))
        self.host_entry = ctk.CTkEntry(form, placeholder_text="127.0.0.1", fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.host_entry.insert(0, "127.0.0.1")
        self.host_entry.grid(row=3, column=0, sticky="ew", padx=(16, 8), pady=(0, 10))

        ctk.CTkLabel(form, text="Puerto:", font=FONT_SMALL, text_color=TEXT_MUTED).grid(row=2, column=1, sticky="w", padx=8, pady=(0, 2))
        self.port_entry = ctk.CTkEntry(form, placeholder_text="3306", width=100, fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.port_entry.insert(0, "3306")
        self.port_entry.grid(row=3, column=1, sticky="ew", padx=(8, 16), pady=(0, 10))

        # Usuario y Contraseña
        ctk.CTkLabel(form, text="Usuario:", font=FONT_SMALL, text_color=TEXT_MUTED).grid(row=4, column=0, sticky="w", padx=16, pady=(0, 2))
        self.user_entry = ctk.CTkEntry(form, placeholder_text="root", fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.user_entry.insert(0, "root")
        self.user_entry.grid(row=5, column=0, sticky="ew", padx=(16, 8), pady=(0, 10))

        ctk.CTkLabel(form, text="Contraseña:", font=FONT_SMALL, text_color=TEXT_MUTED).grid(row=4, column=1, sticky="w", padx=8, pady=(0, 2))
        self.password_entry = ctk.CTkEntry(form, placeholder_text="••••••••", show="•", fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self.password_entry.grid(row=5, column=1, sticky="ew", padx=(8, 16), pady=(0, 10))

        # SSL Check
        self.ssl_check = ctk.CTkCheckBox(form, text="Habilitar SSL / TLS", font=FONT_SMALL, fg_color=ACCENT_PRIMARY)
        self.ssl_check.grid(row=6, column=0, sticky="w", padx=16, pady=(0, 10))

        form.grid_columnconfigure(0, weight=3)
        form.grid_columnconfigure(1, weight=1)

        # Botones de Conexión y Descubrimiento
        conn_actions = ctk.CTkFrame(form, fg_color="transparent")
        conn_actions.grid(row=7, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 10))

        self.test_btn = ctk.CTkButton(
            conn_actions,
            text="🔌 Probar Conexión",
            width=140,
            height=30,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=self._test_connection
        )
        self.test_btn.pack(side="left", padx=(0, 8))

        self.discover_btn = ctk.CTkButton(
            conn_actions,
            text="🔍 Auto-descubrir BDs",
            width=160,
            height=30,
            font=FONT_SMALL,
            fg_color=ACCENT_PRIMARY,
            hover_color="#1D4ED8",
            command=self._discover_databases
        )
        self.discover_btn.pack(side="left")

        # Etiqueta de resultado de prueba
        self.status_lbl = ctk.CTkLabel(form, text="", font=FONT_SMALL, text_color=TEXT_MUTED)
        self.status_lbl.grid(row=8, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))

        # Contenedor de Bases de datos descubiertas / asignadas
        dbs_header = ctk.CTkFrame(form, fg_color="transparent")
        dbs_header.grid(row=9, column=0, columnspan=2, sticky="ew", padx=16, pady=(6, 4))

        ctk.CTkLabel(dbs_header, text="Bases de datos asignadas a este servidor:", font=FONT_BODY_BOLD, text_color=TEXT_MAIN).pack(side="left")

        # Botón para seleccionar / deseleccionar todas
        self.toggle_all_btn = ctk.CTkButton(
            dbs_header,
            text="Seleccionar Todo",
            width=110,
            height=22,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=self._toggle_select_all
        )
        self.toggle_all_btn.pack(side="right")

        self.dbs_scroll = ctk.CTkScrollableFrame(form, height=180, fg_color=BG_INPUT, border_width=1, border_color=BORDER_COLOR)
        self.dbs_scroll.grid(row=10, column=0, columnspan=2, sticky="nsew", padx=16, pady=(0, 16))

        self._all_selected = True

    def _populate_fields(self, server: ServerConfig) -> None:
        """Carga datos de un servidor existente para edición."""
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, server.name)

        self.host_entry.delete(0, "end")
        self.host_entry.insert(0, server.host)

        self.port_entry.delete(0, "end")
        self.port_entry.insert(0, str(server.port))

        self.user_entry.delete(0, "end")
        self.user_entry.insert(0, server.user)

        raw_pwd = secret_manager.decrypt_text(server.encrypted_password)
        self.password_entry.delete(0, "end")
        self.password_entry.insert(0, raw_pwd)

        if server.ssl_enabled:
            self.ssl_check.select()

        self.discovered_dbs = list(server.databases)
        self._render_db_list()

    def _build_server_from_inputs(self) -> ServerConfig:
        """Construye un objeto ServerConfig temporal con las entradas actuales."""
        name = self.name_entry.get().strip() or "Servidor MySQL"
        host = self.host_entry.get().strip() or "127.0.0.1"
        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            port = 3306
        user = self.user_entry.get().strip() or "root"
        raw_password = self.password_entry.get()

        # Si estamos editando y el campo de contraseña se dejó vacío, conservar la previa
        if not raw_password and self.server and self.server.encrypted_password:
            encrypted_pwd = self.server.encrypted_password
        else:
            encrypted_pwd = secret_manager.encrypt_text(raw_password)

        ssl = bool(self.ssl_check.get())

        server_id = self.server.id if self.server else None
        s = ServerConfig(
            name=name,
            host=host,
            port=port,
            user=user,
            encrypted_password=encrypted_pwd,
            ssl_enabled=ssl,
            server_version=self._detected_version
        )
        if server_id:
            s.id = server_id
        return s

    def _test_connection(self) -> None:
        """Prueba la conexión al servidor."""
        self.status_lbl.configure(text="Probando conexión...", text_color=TEXT_MUTED)
        self.update_idletasks()

        server = self._build_server_from_inputs()
        success, message, version = ConnectionService.test_connection(server)

        if success:
            self.status_lbl.configure(text=f"✓ {message}", text_color=ACCENT_SUCCESS)
            self._detected_version = version
            if self.server:
                self.server.server_version = version
        else:
            self.status_lbl.configure(text=f"✕ {message}", text_color=ACCENT_DANGER)

    def _discover_databases(self) -> None:
        """Descubre bases de datos del servidor y las muestra para selección."""
        self.status_lbl.configure(text="Consultando bases de datos en el servidor...", text_color=TEXT_MUTED)
        self.update_idletasks()

        server = self._build_server_from_inputs()
        try:
            dbs = ConnectionService.discover_databases(server)
            self.discovered_dbs = dbs
            self._render_db_list()
            self.status_lbl.configure(text=f"✓ Se encontraron {len(dbs)} bases de datos.", text_color=ACCENT_SUCCESS)
        except Exception as e:
            self.status_lbl.configure(text=f"✕ Error en descubrimiento: {e}", text_color=ACCENT_DANGER)

    def _render_db_list(self) -> None:
        """Muestra las bases de datos en el scroll con checkboxes."""
        for widget in self.dbs_scroll.winfo_children():
            widget.destroy()

        self._db_checkboxes.clear()

        if not self.discovered_dbs:
            ctk.CTkLabel(
                self.dbs_scroll,
                text="No hay bases de datos listadas aún.",
                font=FONT_SMALL,
                text_color=TEXT_MUTED
            ).pack(pady=10)
            return

        for db in self.discovered_dbs:
            row = ctk.CTkFrame(self.dbs_scroll, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)

            chk = ctk.CTkCheckBox(
                row,
                text=f"{db.name} ({db.charset})",
                font=FONT_SMALL,
                fg_color=ACCENT_PRIMARY
            )
            if db.enabled:
                chk.select()
            chk.pack(side="left")
            self._db_checkboxes[db.name] = (chk, db)

    def _toggle_select_all(self) -> None:
        """Selecciona o deselecciona todas las casillas de bases de datos."""
        self._all_selected = not self._all_selected
        for chk, db in self._db_checkboxes.values():
            if self._all_selected:
                chk.select()
            else:
                chk.deselect()
        self.toggle_all_btn.configure(text="Deseleccionar Todo" if self._all_selected else "Seleccionar Todo")

    def _save(self) -> None:
        """Valida y guarda el servidor."""
        name = self.name_entry.get().strip()
        host = self.host_entry.get().strip()
        user = self.user_entry.get().strip()

        if not name:
            self.footer_status.configure(text="✕ Ingresa un nombre para el servidor", text_color=ACCENT_DANGER)
            return
        if not host:
            self.footer_status.configure(text="✕ Ingresa un host válido", text_color=ACCENT_DANGER)
            return
        if not user:
            self.footer_status.configure(text="✕ Ingresa un usuario válido", text_color=ACCENT_DANGER)
            return

        server = self._build_server_from_inputs()

        # Recoger bases de datos seleccionadas
        final_dbs: List[DatabaseConfig] = []
        if self._db_checkboxes:
            for name_db, (chk, db_obj) in self._db_checkboxes.items():
                db_obj.enabled = bool(chk.get())
                final_dbs.append(db_obj)
        elif self.server and self.server.databases:
            final_dbs = list(self.server.databases)
        elif self.discovered_dbs:
            final_dbs = list(self.discovered_dbs)

        server.databases = final_dbs

        app_logger.info(f"Guardando servidor [{server.name}] con {len(server.databases)} bases de datos...")

        if self.on_save_callback:
            try:
                self.on_save_callback(server)
            except Exception as e:
                app_logger.error(f"Error al guardar servidor: {e}")
                self.footer_status.configure(text=f"✕ Error al guardar: {e}", text_color=ACCENT_DANGER)
                return

        self.destroy()
