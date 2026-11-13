"""Ventana principal de la aplicación.

La conexión con Drive (autenticación y listado de carpetas) se hace en un hilo
para que la interfaz aparezca de inmediato y siga respondiendo. El resultado se
aplica en el hilo principal con ``after(0, ...)``.
"""

from __future__ import annotations

import os
import threading
import traceback

import customtkinter as ctk

from src.config import DRY_RUN
from src.drive.folder_tree import FolderTreeModel
from src.programs import ProgramStore

from .programs_tab import ProgramsTab
from .theme import (
    DEFAULT_THEME,
    WINDOW_HEIGHT,
    WINDOW_MIN_SIZE,
    WINDOW_WIDTH,
    Theme,
)

#: Si vale "1", la aplicación arranca sin conectar con Drive. Útil para
#: desarrollar la interfaz sin abrir el flujo de autenticación.
OFFLINE_ENV = "DRIVE_AUTOMATOR_OFFLINE"


class DriveOrganizerApp(ctk.CTk):
    """Ventana principal: cabecera, pestañas y barra de estado."""

    def __init__(self, theme: Theme = DEFAULT_THEME):
        super().__init__()

        self._theme = theme
        self._theme.apply()

        self._closing = False
        self._loading_drive = False
        self.model: FolderTreeModel | None = None
        self.store = ProgramStore()

        self.title("Organizador de Drive")
        self._apply_window_geometry()
        self.minsize(*WINDOW_MIN_SIZE)
        self.configure(fg_color=theme.pair("window"))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.report_callback_exception = self._report_callback_exception

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()
        self._build_status_bar()
        self._update_summary()

        if os.environ.get(OFFLINE_ENV) == "1":
            self._set_status(
                "Modo sin conexión: las carpetas de Drive no se cargan.", "warning"
            )
        else:
            # Se deja pintar la ventana antes de lanzar la autenticación.
            self.after(250, self.reload_drive)

    # -- construcción de la interfaz --------------------------------------
    def _apply_window_geometry(self) -> None:
        """Fija el tamaño inicial sin salirse de la pantalla.

        ``geometry()`` de CustomTkinter escala las medidas según el DPI, así que
        el margen disponible se convierte a unidades lógicas antes de recortar.
        """
        try:
            scale = ctk.ScalingTracker.get_window_scaling(self) or 1.0
        except Exception:
            scale = 1.0
        available_width = int((self.winfo_screenwidth() - 60) / scale)
        available_height = int((self.winfo_screenheight() - 100) / scale)
        width = max(WINDOW_MIN_SIZE[0], min(WINDOW_WIDTH, available_width))
        height = max(WINDOW_MIN_SIZE[1], min(WINDOW_HEIGHT, available_height))
        self.geometry(f"{width}x{height}")

    def _build_header(self) -> None:
        theme = self._theme
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 12))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Organizador de Drive",
            font=theme.font(24, "bold"),
            text_color=theme.pair("text"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Clasifica los archivos de cada programa en su carpeta.",
            font=theme.font(12),
            text_color=theme.pair("muted"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=1, rowspan=2, sticky="e")

        self._mode_control = ctk.CTkSegmentedButton(
            controls,
            values=["Oscuro", "Claro"],
            command=self._on_mode_change,
            font=theme.font(11),
            selected_color=theme.pair("accent"),
            selected_hover_color=theme.pair("accent_hover"),
            unselected_color=theme.pair("panel_alt"),
            unselected_hover_color=theme.pair("border"),
            text_color=theme.pair("text"),
        )
        self._mode_control.set("Oscuro")
        self._mode_control.pack(side="left", padx=(0, 10))

        self._reload_button = ctk.CTkButton(
            controls,
            text="Recargar Drive",
            width=130,
            height=32,
            command=self.reload_drive,
            fg_color=theme.pair("panel_alt"),
            hover_color=theme.pair("border"),
            border_width=1,
            border_color=theme.pair("border"),
            text_color=theme.pair("text"),
        )
        self._reload_button.pack(side="left")

    def _build_body(self) -> None:
        theme = self._theme
        self._tabs = ctk.CTkTabview(
            self,
            fg_color=theme.pair("panel"),
            border_color=theme.pair("border"),
            segmented_button_fg_color=theme.pair("panel_alt"),
            segmented_button_selected_color=theme.pair("accent"),
            segmented_button_selected_hover_color=theme.pair("accent_hover"),
            segmented_button_unselected_color=theme.pair("panel_alt"),
            segmented_button_unselected_hover_color=theme.pair("border"),
            segmented_button_font=theme.font(12),
            text_color=theme.pair("text"),
            anchor="w",
        )
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))

        tab = self._tabs.add("Programas")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        self.programs_tab = ProgramsTab(
            tab,
            self.store,
            theme=theme,
            on_change=self._on_store_change,
        )
        self.programs_tab.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _build_status_bar(self) -> None:
        theme = self._theme
        bar = ctk.CTkFrame(self, fg_color=theme.pair("panel"), corner_radius=0)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self._status_label = ctk.CTkLabel(
            bar,
            text="Iniciando…",
            font=theme.font(11),
            text_color=theme.pair("muted"),
            anchor="w",
        )
        self._status_label.grid(row=0, column=0, sticky="w", padx=24, pady=8)

        self._summary_label = ctk.CTkLabel(
            bar,
            text="",
            font=theme.font(11),
            text_color=theme.pair("muted"),
            anchor="e",
        )
        self._summary_label.grid(row=0, column=1, sticky="e", padx=24, pady=8)

    # -- Drive -------------------------------------------------------------
    def reload_drive(self) -> None:
        """Vuelve a conectar con Drive y recarga el árbol de carpetas."""
        if self._closing or self._loading_drive:
            return

        self._loading_drive = True
        self.model = None
        self.programs_tab.set_model(None)
        self._reload_button.configure(state="disabled")
        self._set_status("Conectando con Google Drive…", "warning")

        threading.Thread(target=self._load_drive_worker, daemon=True).start()

    def _load_drive_worker(self) -> None:
        """Autentica y descarga las carpetas; nunca toca la interfaz."""
        try:
            from src.authentication.auth import get_credentials
            from src.drive.drive_client import get_root_id, get_service, list_folders

            credentials = get_credentials()
            service = get_service(credentials)
            root_id = get_root_id(service)
            folders = list_folders(service)
            model = FolderTreeModel(folders, root_id=root_id, root_name="Mi Drive")
        except Exception as exc:
            self._schedule(self._on_drive_error, exc)
            return
        self._schedule(self._on_drive_loaded, model)

    def _on_drive_loaded(self, model: FolderTreeModel) -> None:
        self._loading_drive = False
        self.model = model
        self.programs_tab.set_model(model)
        self._reload_button.configure(state="normal")
        self._set_status(f"{len(model)} carpetas de Drive cargadas.", "success")

    def _on_drive_error(self, exc: Exception) -> None:
        self._loading_drive = False
        self.model = None
        self.programs_tab.set_model(None)
        self._reload_button.configure(state="normal")
        self._set_status(f"No se pudo conectar con Drive: {exc}", "danger")

    def _schedule(self, callback, *args) -> None:
        """Encola una actualización en el hilo principal."""
        if self._closing:
            return
        try:
            self.after(0, callback, *args)
        except Exception:
            pass

    # -- eventos -----------------------------------------------------------
    def _on_mode_change(self, value: str) -> None:
        self._theme.set_mode("light" if value == "Claro" else "dark")
        self._theme.apply()
        self.configure(fg_color=self._theme.pair("window"))
        self.programs_tab.apply_theme()

    def _on_store_change(self, _store: ProgramStore) -> None:
        self._update_summary()

    def _update_summary(self) -> None:
        total = len(self.store)
        programas = "1 programa" if total == 1 else f"{total} programas"
        dry_run = "DRY_RUN activo" if DRY_RUN else "DRY_RUN desactivado"
        self._summary_label.configure(text=f"{programas}  ·  {dry_run}")

    def _set_status(self, text: str, kind: str = "muted") -> None:
        key = kind if kind in ("danger", "success", "warning") else "muted"
        self._status_label.configure(
            text=text,
            text_color=self._theme.pair(key),
        )

    def _report_callback_exception(self, exc, value, tb) -> None:
        """Muestra los errores de Tk en la barra de estado en vez de perderlos."""
        traceback.print_exception(exc, value, tb)
        self._set_status(f"Error inesperado: {value}", "danger")

    def _on_close(self) -> None:
        self._closing = True
        self.destroy()


def run_app() -> None:
    """Abre la ventana principal y entra en el bucle de eventos."""
    app = DriveOrganizerApp()
    app.mainloop()
