"""Ventana principal de la aplicación.

La conexión con Drive (autenticación y listado de carpetas) se hace en un hilo
para que la interfaz aparezca de inmediato y siga respondiendo. El resultado se
aplica en el hilo principal con ``after(0, ...)``.

La cuenta activa determina qué credenciales, qué programas y qué árbol de
Drive se cargan. Al cambiar de cuenta se invalida todo el estado anterior.
"""

from __future__ import annotations

import threading
import traceback

import customtkinter as ctk

from src.config import DRY_RUN
from src.drive.folder_tree import FolderTreeModel
from src.programs import ProgramRepository, ProgramStore, ProgramStoreError
from src.profiles import ProfileStore
from src.profiles.service import AccountService
from src.runtime_settings import RuntimeSettings

from .accounts_tab import AccountsTab
from .browser_picker import pick_browser
from .icon import apply_window_icon, set_app_user_model_id
from .organize_tab import OrganizeTab
from .programs_tab import ProgramsTab
from .theme import (
    DEFAULT_THEME,
    WINDOW_HEIGHT,
    WINDOW_MIN_SIZE,
    WINDOW_WIDTH,
    Theme,
)


class DriveOrganizerApp(ctk.CTk):
    """Ventana principal: cabecera, pestañas y barra de estado."""

    def __init__(
        self,
        theme: Theme = DEFAULT_THEME,
        *,
        profiles: ProfileStore | None = None,
        accounts: AccountService | None = None,
    ):
        super().__init__()
        # CustomTkinter pone su propio icono 200 ms después de iniciar, pero
        # solo si nadie llamó a iconbitmap antes: hacerlo aquí lo evita.
        apply_window_icon(self)

        self._theme = theme
        self._theme.apply()

        self._closing = False
        self._loading_drive = False
        self._drive_generation = 0
        self._suspend_program_save = False
        self._account_labels: dict[str, str] = {}
        self.model: FolderTreeModel | None = None
        self.store = ProgramStore()
        self.settings = RuntimeSettings(dry_run=DRY_RUN)

        if accounts is not None:
            self.accounts = accounts
            self.profiles = accounts.store
        else:
            self.profiles = (
                profiles if profiles is not None else ProfileStore()
            )
            self.accounts = AccountService(self.profiles)

        self.title("Organizador de Drive")
        self._apply_window_geometry()
        self.minsize(*WINDOW_MIN_SIZE)
        self.configure(fg_color=theme.color("window"))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.report_callback_exception = self._report_callback_exception

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()
        self._build_status_bar()
        self._update_summary()
        self._refresh_account_ui()
        # Se deja pintar la ventana antes de cargar la cuenta activa.
        self.after(250, self._startup)

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
            text_color=theme.color("text"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Clasifica los archivos de cada programa en su carpeta según un patrón específico.",
            font=theme.font(12),
            text_color=theme.color("muted"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=1, rowspan=2, sticky="e")

        ctk.CTkLabel(
            controls,
            text="Cuenta:",
            font=theme.font(11, "bold"),
            text_color=theme.color("muted"),
        ).pack(side="left", padx=(0, 6))

        self._account_menu = ctk.CTkOptionMenu(
            controls,
            values=["Sin cuenta"],
            command=self._on_account_menu,
            width=190,
            height=32,
            dynamic_resizing=False,
            font=theme.font(11),
            dropdown_font=theme.font(11),
            fg_color=theme.color("panel_alt"),
            button_color=theme.color("border"),
            button_hover_color=theme.color("accent_hover"),
            dropdown_fg_color=theme.color("panel_alt"),
            dropdown_hover_color=theme.color("border"),
            dropdown_text_color=theme.color("text"),
            text_color=theme.color("text"),
        )
        self._account_menu.pack(side="left", padx=(0, 8))

        self._reload_button = ctk.CTkButton(
            controls,
            text="Recargar Drive",
            width=130,
            height=32,
            command=self.reload_drive,
            fg_color=theme.color("panel_alt"),
            hover_color=theme.color("border"),
            border_width=1,
            border_color=theme.color("border"),
            text_color=theme.color("text"),
        )
        self._reload_button.pack(side="left")

    def _build_body(self) -> None:
        theme = self._theme
        self._tabs = ctk.CTkTabview(
            self,
            fg_color=theme.color("panel"),
            border_color=theme.color("border"),
            segmented_button_fg_color=theme.color("panel_alt"),
            segmented_button_selected_color=theme.color("accent"),
            segmented_button_selected_hover_color=theme.color("accent_hover"),
            segmented_button_unselected_color=theme.color("panel_alt"),
            segmented_button_unselected_hover_color=theme.color("border"),
            segmented_button_font=theme.font(12),
            text_color=theme.color("text"),
            anchor="w",
        )
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))

        tab = self._tabs.add("Gestión de programas")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        self.programs_tab = ProgramsTab(
            tab,
            self.store,
            theme=theme,
            on_change=self._on_store_change,
        )
        self.programs_tab.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        organize = self._tabs.add("Organización")
        organize.grid_columnconfigure(0, weight=1)
        organize.grid_rowconfigure(0, weight=1)

        self.organize_tab = OrganizeTab(
            organize,
            self.store,
            theme=theme,
            on_reload=self.reload_drive,
            settings=self.settings,
            on_dry_run_change=self._on_dry_run_change,
            browser_provider=self._provide_browser,
            auth_paths_provider=self._active_auth_paths,
        )
        self.organize_tab.grid(
            row=0, column=0, sticky="nsew", padx=10, pady=10
        )

        accounts = self._tabs.add("Cuentas")
        accounts.grid_columnconfigure(0, weight=1)
        accounts.grid_rowconfigure(0, weight=1)

        self.accounts_tab = AccountsTab(
            accounts,
            self.profiles,
            self.accounts,
            theme=theme,
            on_switch=self.switch_account,
            on_profile_added=self._on_profile_added,
            on_profile_removed=self._on_profile_removed,
            on_connected=self._on_connected,
            on_credentials_replaced=self._on_credentials_replaced,
            on_profiles_changed=self._on_profiles_changed,
            browser_provider=self._provide_browser,
        )
        self.accounts_tab.grid(
            row=0, column=0, sticky="nsew", padx=10, pady=10
        )

    def _build_status_bar(self) -> None:
        theme = self._theme
        bar = ctk.CTkFrame(self, fg_color=theme.color("panel"), corner_radius=0)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self._status_label = ctk.CTkLabel(
            bar,
            text="Iniciando…",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        )
        self._status_label.grid(row=0, column=0, sticky="w", padx=24, pady=8)

        self._summary_label = ctk.CTkLabel(
            bar,
            text="",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="e",
        )
        self._summary_label.grid(row=0, column=1, sticky="e", padx=24, pady=8)

    # -- cuentas y arranque ------------------------------------------------
    def _startup(self) -> None:
        """Migra la configuración antigua y carga la cuenta activa."""
        if self._closing:
            return

        try:
            migrated = self.accounts.migrate_legacy()
        except Exception as exc:
            migrated = None
            self._set_status(
                f"No se pudieron importar las credenciales antiguas: {exc}",
                "warning",
            )
        if migrated is not None:
            self._set_status(
                "Se importó la cuenta 'Predeterminada' de la raíz.", "success"
            )

        if not self.profiles.profiles:
            self._reset_drive_state()
            self._refresh_account_ui()
            self._set_status(
                "Añade una cuenta en la pestaña Cuentas para empezar.",
                "warning",
            )
            return

        if self.profiles.active_id is None:
            first = self.profiles.profiles[0]
            try:
                self.accounts.switch(first.id)
            except Exception as exc:
                self._set_status(
                    f"No se pudo activar la cuenta: {exc}", "danger"
                )
                return

        self._load_programs_for_active()
        self._refresh_account_ui()
        self.reload_drive()

    def _active_auth_paths(self):
        """Archivos del perfil activo; falla si no hay cuenta."""
        paths = self.accounts.active_paths()
        if paths is None:
            raise RuntimeError("No hay una cuenta activa.")
        return paths

    def _activate_profile(self, profile_id: str) -> None:
        """Activa una cuenta y recarga todo su estado."""
        try:
            self.accounts.switch(profile_id)
        except Exception as exc:
            self._set_status(
                f"No se pudo activar la cuenta: {exc}", "danger"
            )
            self._refresh_account_ui()
            return

        self._reset_drive_state()
        self._load_programs_for_active()
        self._refresh_account_ui()
        self.reload_drive()

    def switch_account(self, profile_id: str) -> None:
        """Cambia de cuenta si no hay una operación en curso."""
        if profile_id == self.profiles.active_id:
            self._refresh_account_ui()
            return

        busy = (
            self._loading_drive
            or self.organize_tab.busy
            or self.accounts_tab.busy
        )
        if busy:
            self._set_status(
                "Espera a que termine la operación actual antes de cambiar "
                "de cuenta.",
                "warning",
            )
            self._refresh_account_ui()
            return

        self._activate_profile(profile_id)

    def _on_profile_added(self, profile_id: str) -> None:
        """Activa la cuenta recién importada y conectada."""
        self._activate_profile(profile_id)

    def _on_profile_removed(self, profile_id: str) -> None:
        """Reorganiza el estado después de eliminar una cuenta."""
        if self.profiles.active_id is None and self.profiles.profiles:
            self._activate_profile(self.profiles.profiles[0].id)
            return
        if self.profiles.active_id is None:
            self._reset_drive_state()
            self._replace_programs(())
            self._refresh_account_ui()
            self._set_status(
                "No hay cuentas configuradas. Añade una en la pestaña Cuentas.",
                "warning",
            )
            return
        self._refresh_account_ui()

    def _on_connected(self, profile_id: str) -> None:
        """Recarga Drive si la cuenta conectada es la activa."""
        if profile_id == self.profiles.active_id:
            self.reload_drive()

    def _on_credentials_replaced(self, profile_id: str) -> None:
        """Invalida el estado si se cambió el cliente OAuth de la cuenta."""
        if profile_id != self.profiles.active_id:
            return
        self._reset_drive_state()
        self._set_status(
            "Credenciales reemplazadas. Pulsa 'Conectar' en la pestaña "
            "Cuentas.",
            "warning",
        )

    def _on_profiles_changed(self) -> None:
        self._refresh_account_ui()

    def _refresh_account_ui(self) -> None:
        """Sincroniza el selector de cabecera y la pestaña de cuentas."""
        self._refresh_account_menu()
        if hasattr(self, "accounts_tab"):
            self.accounts_tab.refresh()

    def _refresh_account_menu(self) -> None:
        profiles = self.profiles.profiles
        self._account_labels = {}

        if not profiles:
            self._account_menu.configure(values=["Sin cuenta"], state="disabled")
            self._account_menu.set("Sin cuenta")
            return

        labels: list[str] = []
        for profile in profiles:
            label = profile.name
            suffix = 1
            while label in self._account_labels:
                suffix += 1
                label = f"{profile.name} ({suffix})"
            self._account_labels[label] = profile.id
            labels.append(label)

        self._account_menu.configure(values=labels, state="normal")
        active = self.profiles.active
        if active is not None:
            for label, profile_id in self._account_labels.items():
                if profile_id == active.id:
                    self._account_menu.set(label)
                    break

    def _on_account_menu(self, label: str) -> None:
        profile_id = self._account_labels.get(label)
        if profile_id is None:
            return
        if profile_id == self.profiles.active_id:
            return
        self.switch_account(profile_id)

    # -- programas ---------------------------------------------------------
    def _load_programs_for_active(self) -> None:
        """Carga en el registro compartido los programas de la cuenta activa."""
        profile = self.profiles.active
        if profile is None:
            self._replace_programs(())
            return

        paths = self.profiles.paths_for(profile.id)
        result = ProgramRepository(paths.programs).load()
        self._replace_programs(result.items)
        if result.errors:
            self._set_status(
                "Algunos programas se omitieron: " + " ".join(result.errors),
                "warning",
            )

    def _replace_programs(self, items) -> None:
        """Sustituye el contenido del registro sin guardarlo de vuelta."""
        self._suspend_program_save = True
        try:
            self.store.replace(items)
        except ProgramStoreError:
            self.store.clear()
        finally:
            self._suspend_program_save = False
        if hasattr(self, "programs_tab"):
            self.programs_tab.reload()

    def _save_programs(self) -> None:
        """Guarda los programas de la cuenta activa."""
        if self._suspend_program_save:
            return
        profile = self.profiles.active
        if profile is None:
            return
        paths = self.profiles.paths_for(profile.id)
        try:
            ProgramRepository(paths.programs).save(self.store.items())
        except Exception as exc:
            self._set_status(
                f"No se pudieron guardar los programas: {exc}", "danger"
            )

    # -- Drive -------------------------------------------------------------
    def _provide_browser(self):
        """Pide el navegador con el que se abrirá la autorización de Google.

        La autenticación corre en un hilo, pero el modal se construye en el
        hilo principal para no tocar Tkinter desde un hilo secundario.
        """
        if threading.current_thread() is threading.main_thread():
            return pick_browser(self, theme=self._theme)

        event = threading.Event()
        result: dict[str, object] = {}

        def ask() -> None:
            try:
                result["browser"] = pick_browser(self, theme=self._theme)
            except Exception:
                result["browser"] = None
            finally:
                event.set()

        try:
            self.after(0, ask)
        except Exception:
            return None

        while not event.wait(0.1):
            if self._closing:
                return None
        return result.get("browser")

    def reload_drive(self) -> None:
        """Vuelve a conectar con Drive y recarga el árbol de carpetas."""
        if self._closing or self._loading_drive:
            return

        profile = self.profiles.active
        if profile is None:
            self._reset_drive_state()
            self._set_status(
                "Añade una cuenta en la pestaña Cuentas para empezar.",
                "warning",
            )
            return

        try:
            auth_paths = self.accounts.paths_for(profile.id)
        except Exception as exc:
            self._set_status(
                f"No se pudo preparar la cuenta: {exc}", "danger"
            )
            return

        self._loading_drive = True
        self._drive_generation += 1
        generation = self._drive_generation
        self.model = None
        self.programs_tab.set_model(None)
        self.organize_tab.set_model(None)
        self._reload_button.configure(state="disabled")
        self._set_status(
            f"Conectando con Google Drive ({profile.name})…", "warning"
        )

        threading.Thread(
            target=self._load_drive_worker,
            args=(auth_paths, generation, profile.email),
            daemon=True,
        ).start()

    def _load_drive_worker(
        self,
        auth_paths,
        generation: int,
        login_hint: str | None,
    ) -> None:
        """Autentica y descarga las carpetas; nunca toca la interfaz."""
        try:
            from src.authentication.auth import get_credentials
            from src.drive.drive_client import (
                get_root_id,
                get_service,
                list_folders,
            )

            credentials = get_credentials(
                browser_provider=self._provide_browser,
                paths=auth_paths,
                login_hint=login_hint,
            )
            service = get_service(credentials)
            root_id = get_root_id(service)
            folders = list_folders(service)
            model = FolderTreeModel(folders, root_id=root_id, root_name="Mi Drive")
        except Exception as exc:
            self._schedule(self._on_drive_error, exc, generation)
            return
        self._schedule(self._on_drive_loaded, model, generation)

    def _on_drive_loaded(
        self, model: FolderTreeModel, generation: int | None = None
    ) -> None:
        if generation is not None and generation != self._drive_generation:
            return
        self._loading_drive = False
        self.model = model
        self.programs_tab.set_model(model)
        self.organize_tab.set_model(model)
        self._reload_button.configure(state="normal")
        active = self.profiles.active
        account = f" ({active.name})" if active is not None else ""
        self._set_status(
            f"{len(model)} carpetas de Drive cargadas{account}.", "success"
        )

    def _on_drive_error(
        self, exc: Exception, generation: int | None = None
    ) -> None:
        if generation is not None and generation != self._drive_generation:
            return
        self._loading_drive = False
        self.model = None
        self.programs_tab.set_model(None)
        self.organize_tab.set_model(None)
        self._reload_button.configure(state="normal")

        from src.authentication.auth import AuthenticationCancelled

        if isinstance(exc, AuthenticationCancelled):
            self._set_status(
                "Autenticación cancelada. No se generó el token.", "warning"
            )
            return
        self._set_status(f"No se pudo conectar con Drive: {exc}", "danger")

    def _reset_drive_state(self) -> None:
        """Descarta el árbol y el plan de la cuenta anterior."""
        self._drive_generation += 1
        self._loading_drive = False
        self.model = None
        if hasattr(self, "programs_tab"):
            self.programs_tab.set_model(None)
        if hasattr(self, "organize_tab"):
            self.organize_tab.set_model(None)
        if hasattr(self, "_reload_button"):
            self._reload_button.configure(state="normal")

    def _schedule(self, callback, *args) -> None:
        """Encola una actualización en el hilo principal."""
        if self._closing:
            return
        try:
            self.after(0, callback, *args)
        except Exception:
            pass

    # -- eventos -----------------------------------------------------------
    def _on_store_change(self, _store: ProgramStore) -> None:
        self._update_summary()
        if hasattr(self, "organize_tab"):
            self.organize_tab.invalidate_plan()
        self._save_programs()

    def _update_summary(self) -> None:
        total = len(self.store)
        programas = "1 programa" if total == 1 else f"{total} programas"
        dry_run = (
            "PRUEBA EN SECO: ACTIVADA"
            if self.settings.dry_run
            else "PRUEBA EN SECO: DESACTIVADA"
        )
        self._summary_label.configure(text=f"{programas}  ·  {dry_run}")

    def _on_dry_run_change(self, _dry_run: bool) -> None:
        """Refresca el resumen cuando cambia el modo de simulación."""
        self._update_summary()

    def _set_status(self, text: str, kind: str = "muted") -> None:
        key = kind if kind in ("danger", "success", "warning") else "muted"
        self._status_label.configure(
            text=text,
            text_color=self._theme.color(key),
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
    # La identidad debe registrarse antes de crear la ventana para que Windows
    # no asocie el botón de la barra de tareas con el intérprete de Python.
    set_app_user_model_id()
    app = DriveOrganizerApp()
    app.mainloop()
