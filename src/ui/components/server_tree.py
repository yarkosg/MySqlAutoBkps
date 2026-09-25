"""
Componente visual de árbol jerárquico para Servidores y Bases de Datos agrupadas.
Permite expandir/contraer servidores, seleccionar bases de datos individuales,
lanzar respaldos directos y gestionar configuraciones.
"""

from typing import Callable, Dict, List, Optional
import customtkinter as ctk
from src.models.server import ServerConfig
from src.ui.theme import (
    ACCENT_DANGER, ACCENT_PRIMARY, ACCENT_SUCCESS, ACCENT_WARNING,
    ACCENT_WARNING_HOVER, BG_CARD, BG_CARD_HOVER, BORDER_COLOR,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, TEXT_DIMMED, TEXT_MAIN, TEXT_MUTED
)


class ServerTree(ctk.CTkScrollableFrame):
    """Árbol interactivo que agrupa bases de datos bajo sus respectivos servidores."""

    def __init__(
        self,
        master,
        on_backup_db: Callable[[ServerConfig, str, str], None],
        on_backup_server: Callable[[ServerConfig, str], None],
        on_edit_server: Callable[[ServerConfig], None],
        on_delete_server: Callable[[ServerConfig], None],
        on_manage_dbs: Callable[[ServerConfig], None],
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_backup_db = on_backup_db
        self.on_backup_server = on_backup_server
        self.on_edit_server = on_edit_server
        self.on_delete_server = on_delete_server
        self.on_manage_dbs = on_manage_dbs

        self.servers: List[ServerConfig] = []
        self._expanded_states: Dict[str, bool] = {}

    def set_servers(self, servers: List[ServerConfig]) -> None:
        """Carga y renderiza la jerarquía de servidores y bases de datos."""
        self.servers = servers
        self.refresh()

    def refresh(self) -> None:
        """Reconstruye los elementos gráficos en el contenedor."""
        for widget in self.winfo_children():
            widget.destroy()

        if not self.servers:
            empty_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
            empty_frame.pack(fill="x", padx=10, pady=20)

            ctk.CTkLabel(
                empty_frame,
                text="No hay servidores registrados aún",
                font=FONT_BODY_BOLD,
                text_color=TEXT_MAIN
            ).pack(pady=(18, 4))

            ctk.CTkLabel(
                empty_frame,
                text="Haz clic en '+ Añadir Servidor' en la barra superior para comenzar.",
                font=FONT_SMALL,
                text_color=TEXT_MUTED
            ).pack(pady=(0, 18))
            return

        for server in self.servers:
            self._render_server_card(server)

    def _render_server_card(self, server: ServerConfig) -> None:
        """Renderiza la tarjeta del servidor y su lista de bases de datos."""
        is_expanded = self._expanded_states.get(server.id, True)

        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="x", padx=6, pady=6)

        # Header del Servidor
        header = ctk.CTkFrame(card, fg_color="transparent", height=42)
        header.pack(fill="x", padx=12, pady=(10, 8))

        # Botón Expandir/Contraer
        toggle_icon = "▼" if is_expanded else "►"
        toggle_btn = ctk.CTkButton(
            header,
            text=toggle_icon,
            width=28,
            height=28,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=lambda s=server: self._toggle_expand(s.id)
        )
        toggle_btn.pack(side="left", padx=(0, 8))

        # Información del servidor
        info_frame = ctk.CTkFrame(header, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True)

        title_lbl = ctk.CTkLabel(
            info_frame,
            text=f"{server.name} ({server.host}:{server.port})",
            font=FONT_BODY_BOLD,
            text_color=TEXT_MAIN,
            anchor="w"
        )
        title_lbl.pack(anchor="w")

        sub_info = f"Usuario: {server.user}  |  Bases de datos: {len(server.databases)}"
        if server.server_version:
            sub_info += f"  |  Versión: {server.server_version}"

        subtitle_lbl = ctk.CTkLabel(
            info_frame,
            text=sub_info,
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
            anchor="w"
        )
        subtitle_lbl.pack(anchor="w")

        # Botones de acción del servidor
        actions_frame = ctk.CTkFrame(header, fg_color="transparent")
        actions_frame.pack(side="right")

        # Respaldo Full Servidor
        bkp_btn = ctk.CTkButton(
            actions_frame,
            text="Respaldar Servidor",
            width=120,
            height=28,
            font=FONT_SMALL,
            fg_color=ACCENT_SUCCESS,
            hover_color="#059669",
            command=lambda s=server: self.on_backup_server(s, "FULL")
        )
        bkp_btn.pack(side="left", padx=4)

        # Gestionar / Descubrir BDs
        dbs_btn = ctk.CTkButton(
            actions_frame,
            text="Gestionar BDs",
            width=95,
            height=28,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=lambda s=server: self.on_manage_dbs(s)
        )
        dbs_btn.pack(side="left", padx=4)

        # Editar
        edit_btn = ctk.CTkButton(
            actions_frame,
            text="Editar",
            width=60,
            height=28,
            font=FONT_SMALL,
            fg_color="#2D333F",
            hover_color="#374151",
            command=lambda s=server: self.on_edit_server(s)
        )
        edit_btn.pack(side="left", padx=4)

        # Eliminar
        del_btn = ctk.CTkButton(
            actions_frame,
            text="✕",
            width=28,
            height=28,
            font=FONT_SMALL,
            fg_color="#3B1D22",
            hover_color=ACCENT_DANGER,
            command=lambda s=server: self.on_delete_server(s)
        )
        del_btn.pack(side="left", padx=(4, 0))

        # Lista de bases de datos si está expandido
        if is_expanded:
            dbs_container = ctk.CTkFrame(card, fg_color="#181B21", corner_radius=6)
            dbs_container.pack(fill="x", padx=12, pady=(0, 10))

            if not server.databases:
                ctk.CTkLabel(
                    dbs_container,
                    text="No hay bases de datos vinculadas. Usa 'Gestionar BDs' para agregarlas o detectarlas automáticamente.",
                    font=FONT_SMALL,
                    text_color=TEXT_MUTED
                ).pack(pady=10)
            else:
                for db in server.databases:
                    self._render_db_row(dbs_container, server, db)

    def _render_db_row(self, container, server: ServerConfig, db) -> None:
        """Renderiza una fila de base de datos con sus acciones."""
        row = ctk.CTkFrame(container, fg_color="transparent", height=32)
        row.pack(fill="x", padx=8, pady=3)

        # Checkbox de activación
        chk = ctk.CTkCheckBox(
            row,
            text="",
            width=20,
            height=20,
            checkbox_width=18,
            checkbox_height=18,
            fg_color=ACCENT_PRIMARY
        )
        if db.enabled:
            chk.select()
        chk.configure(command=lambda d=db, c=chk: self._toggle_db_enabled(d, c.get()))
        chk.pack(side="left", padx=(4, 8))

        # Nombre y Charset
        lbl = ctk.CTkLabel(
            row,
            text=f"🗄️ {db.name}",
            font=FONT_BODY_BOLD if db.enabled else FONT_BODY,
            text_color=TEXT_MAIN if db.enabled else TEXT_DIMMED,
            anchor="w"
        )
        lbl.pack(side="left")

        charset_lbl = ctk.CTkLabel(
            row,
            text=f"({db.charset})",
            font=FONT_SMALL,
            text_color=TEXT_MUTED
        )
        charset_lbl.pack(side="left", padx=8)

        # Último respaldo
        last_bkp_str = db.last_backup_time if db.last_backup_time else "Sin respaldos"
        status_lbl = ctk.CTkLabel(
            row,
            text=f"Último: {last_bkp_str}",
            font=FONT_SMALL,
            text_color=TEXT_MUTED
        )
        status_lbl.pack(side="left", padx=12)

        # Botones de acción individual
        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="right")

        # Botón Respaldo Full
        full_btn = ctk.CTkButton(
            actions,
            text="Full",
            width=50,
            height=24,
            font=FONT_SMALL,
            fg_color=ACCENT_SUCCESS,
            hover_color="#059669",
            command=lambda s=server, d=db.name: self.on_backup_db(s, d, "FULL")
        )
        full_btn.pack(side="left", padx=2)

        # Botón Respaldo Incremental
        incr_btn = ctk.CTkButton(
            actions,
            text="Incr.",
            width=50,
            height=24,
            font=FONT_SMALL,
            fg_color=ACCENT_WARNING,
            hover_color=ACCENT_WARNING_HOVER,
            command=lambda s=server, d=db.name: self.on_backup_db(s, d, "INCREMENTAL")
        )
        incr_btn.pack(side="left", padx=2)

    def _toggle_expand(self, server_id: str) -> None:
        """Alterna el estado de expansión de un servidor."""
        current = self._expanded_states.get(server_id, True)
        self._expanded_states[server_id] = not current
        self.refresh()

    def _toggle_db_enabled(self, db, is_checked: int) -> None:
        """Habilita o deshabilita la base de datos para respaldos en lote."""
        db.enabled = bool(is_checked)
