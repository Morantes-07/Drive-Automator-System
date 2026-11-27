"""Pestaña para administrar las cuentas de Google y su sesión.

La pestaña no modifica el estado global de la aplicación directamente:
notifica a ``DriveOrganizerApp`` mediante callbacks para que cargue los
programas y el árbol de Drive de la cuenta elegida.
"""

from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

import customtkinter as ctk

from src.authentication.auth import (
    AuthenticationCancelled,
    BrowserProvider,
    TOKEN_STATUS_INVALID,
    TOKEN_STATUS_MISSING,
    TOKEN_STATUS_RECONNECT_REQUIRED,
    TOKEN_STATUS_REFRESHABLE,
    TOKEN_STATUS_VALID,
    token_status,
)
from src.profiles.models import AccountProfile
from src.profiles.service import AccountService
from src.profiles.store import ProfileStore

from .theme import DEFAULT_THEME, TREE_STYLE, Theme

#: Texto que se muestra para cada estado local del token.
STATUS_LABELS: dict[str, str] = {
    TOKEN_STATUS_MISSING: "Sin sesión",
    TOKEN_STATUS_INVALID: "Token inválido",
    TOKEN_STATUS_VALID: "Sesión activa",
    TOKEN_STATUS_REFRESHABLE: "Renovable",
    TOKEN_STATUS_RECONNECT_REQUIRED: "Requiere reconexión",
}

SwitchCallback = Callable[[str], None]
ProfileCallback = Callable[[str], None]
ProfilesChangedCallback = Callable[[], None]

COLUMNS = ("nombre", "correo", "proyecto", "estado", "ultimo")


class AccountsTab(ctk.CTkFrame):
    """Listado, alta y mantenimiento de las cuentas configuradas.

    Args:
        master: Widget contenedor (una pestaña de ``CTkTabview``).
        store: Registro persistente de perfiles.
        service: Operaciones de importación, conexión y borrado.
        theme: Tema compartido de la aplicación.
        on_switch: Se llama al pulsar "Usar esta cuenta".
        on_profile_added: Se llama después de importar y conectar una cuenta.
        on_profile_removed: Se llama después de eliminar una cuenta.
        on_connected: Se llama al terminar de conectar una cuenta.
        on_credentials_replaced: Se llama al reemplazar las credenciales.
        on_profiles_changed: Se llama tras cualquier cambio en la lista.
        browser_provider: Selecciona el navegador para el flujo de Google.
    """

    def __init__(
        self,
        master,
        store: ProfileStore,
        service: AccountService,
        *,
        theme: Theme = DEFAULT_THEME,
        on_switch: SwitchCallback | None = None,
        on_profile_added: ProfileCallback | None = None,
        on_profile_removed: ProfileCallback | None = None,
        on_connected: ProfileCallback | None = None,
        on_credentials_replaced: ProfileCallback | None = None,
        on_profiles_changed: ProfilesChangedCallback | None = None,
        browser_provider: BrowserProvider | None = None,
    ):
        super().__init__(master, fg_color="transparent")

        self._store = store
        self._service = service
        self._theme = theme
        self._on_switch = on_switch
        self._on_profile_added = on_profile_added
        self._on_profile_removed = on_profile_removed
        self._on_connected = on_connected
        self._on_credentials_replaced = on_credentials_replaced
        self._on_profiles_changed = on_profiles_changed
        self._browser_provider = browser_provider
        self._busy = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_active_card()
        self._build_table()
        self._build_footer()
        self.refresh()

    # -- API pública -------------------------------------------------------
    @property
    def busy(self) -> bool:
        """Indica si hay una operación de cuenta en curso."""
        return self._busy

    def refresh(self) -> None:
        """Vuelve a pintar la cuenta activa y la tabla de perfiles."""
        self._refresh_active_card()
        self._refresh_table()
        self._update_buttons()

    # -- construcción de la interfaz --------------------------------------
    def _build_active_card(self) -> None:
        theme = self._theme
        card = ctk.CTkFrame(
            self,
            fg_color=theme.color("panel"),
            border_color=theme.color("border"),
            border_width=1,
            corner_radius=12,
        )
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Cuenta activa",
            font=theme.font(15, "bold"),
            text_color=theme.color("text"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 0))

        self._active_name_label = ctk.CTkLabel(
            card,
            text="Sin cuenta activa",
            font=theme.font(13, "bold"),
            text_color=theme.color("text"),
            anchor="w",
        )
        self._active_name_label.grid(
            row=1, column=0, sticky="w", padx=16, pady=(6, 0)
        )

        self._active_status_label = ctk.CTkLabel(
            card,
            text="",
            font=theme.font(11, "bold"),
            text_color=theme.color("muted"),
            anchor="e",
        )
        self._active_status_label.grid(
            row=1, column=1, sticky="e", padx=16, pady=(6, 0)
        )

        self._active_detail_label = ctk.CTkLabel(
            card,
            text="Añade una cuenta para empezar.",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        )
        self._active_detail_label.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
            padx=16,
            pady=(2, 10),
        )

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            padx=16,
            pady=(0, 14),
        )

        self._connect_button = ctk.CTkButton(
            actions,
            text="Conectar",
            width=120,
            height=32,
            command=self._connect_active,
            fg_color=theme.color("accent"),
            hover_color=theme.color("accent_hover"),
            text_color=theme.color("accent_text"),
        )
        self._connect_button.pack(side="left", padx=(0, 8))

        self._check_button = ctk.CTkButton(
            actions,
            text="Comprobar",
            width=120,
            height=32,
            command=self._check_active,
            fg_color=theme.color("panel_alt"),
            hover_color=theme.color("border"),
            border_width=1,
            border_color=theme.color("border"),
            text_color=theme.color("text"),
        )
        self._check_button.pack(side="left", padx=(0, 8))

        self._replace_button = ctk.CTkButton(
            actions,
            text="Reemplazar credenciales…",
            width=190,
            height=32,
            command=self._replace_credentials,
            fg_color=theme.color("panel_alt"),
            hover_color=theme.color("border"),
            border_width=1,
            border_color=theme.color("border"),
            text_color=theme.color("text"),
        )
        self._replace_button.pack(side="left")

    def _build_table(self) -> None:
        theme = self._theme
        card = ctk.CTkFrame(
            self,
            fg_color=theme.color("panel"),
            border_color=theme.color("border"),
            border_width=1,
            corner_radius=12,
        )
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Cuentas configuradas",
            font=theme.font(15, "bold"),
            text_color=theme.color("text"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._count_label = ctk.CTkLabel(
            header,
            text="",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="e",
        )
        self._count_label.grid(row=0, column=1, sticky="e")

        frame = ctk.CTkFrame(card, fg_color="transparent")
        frame.grid(row=1, column=0, sticky="nsew", padx=16)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            frame,
            columns=COLUMNS,
            show="headings",
            selectmode="browse",
            style=TREE_STYLE,
            height=8,
        )
        self.tree.heading("nombre", text="Cuenta", anchor="w")
        self.tree.heading("correo", text="Correo", anchor="w")
        self.tree.heading("proyecto", text="Proyecto", anchor="w")
        self.tree.heading("estado", text="Estado", anchor="w")
        self.tree.heading("ultimo", text="Último uso", anchor="w")
        self.tree.column(
            "nombre", width=170, minwidth=110, stretch=False, anchor="w"
        )
        self.tree.column(
            "correo", width=250, minwidth=150, stretch=True, anchor="w"
        )
        self.tree.column(
            "proyecto", width=200, minwidth=120, stretch=True, anchor="w"
        )
        self.tree.column(
            "estado", width=130, minwidth=100, stretch=False, anchor="w"
        )
        self.tree.column(
            "ultimo", width=140, minwidth=100, stretch=False, anchor="w"
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_change)

        self._scrollbar = ctk.CTkScrollbar(
            frame, command=self.tree.yview, width=12
        )
        self._scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        self.tree.configure(yscrollcommand=self._scrollbar.set)

        self._empty_label = ctk.CTkLabel(
            frame,
            text=(
                "Todavía no hay cuentas.\n"
                "Pulsa 'Añadir cuenta…' para importar un credentials.json."
            ),
            font=theme.font(12),
            text_color=theme.color("muted"),
            justify="center",
        )

    def _build_footer(self) -> None:
        theme = self._theme
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        footer.grid_columnconfigure(1, weight=1)

        self._add_button = ctk.CTkButton(
            footer,
            text="Añadir cuenta…",
            width=150,
            height=32,
            command=self._add_account,
            fg_color=theme.color("accent"),
            hover_color=theme.color("accent_hover"),
            text_color=theme.color("accent_text"),
        )
        self._add_button.grid(row=0, column=0, sticky="w")

        self._message_label = ctk.CTkLabel(
            footer,
            text="",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        )
        self._message_label.grid(row=0, column=1, sticky="w", padx=12)

        self._use_button = ctk.CTkButton(
            footer,
            text="Usar esta cuenta",
            width=150,
            height=32,
            command=self._use_selected,
            fg_color=theme.color("panel_alt"),
            hover_color=theme.color("border"),
            border_width=1,
            border_color=theme.color("border"),
            text_color=theme.color("text"),
        )
        self._use_button.grid(row=0, column=2, padx=(8, 0))

        self._delete_button = ctk.CTkButton(
            footer,
            text="Eliminar",
            width=100,
            height=32,
            command=self._delete_selected,
            fg_color="transparent",
            hover_color=theme.color("panel_alt"),
            border_width=1,
            border_color=theme.color("danger"),
            text_color=theme.color("danger"),
        )
        self._delete_button.grid(row=0, column=3, padx=(8, 0))

    # -- pintura -----------------------------------------------------------
    def _refresh_active_card(self) -> None:
        theme = self._theme
        profile = self._store.active
        if profile is None:
            self._active_name_label.configure(text="Sin cuenta activa")
            self._active_detail_label.configure(
                text="Añade una cuenta para empezar."
            )
            self._active_status_label.configure(
                text="", text_color=theme.color("muted")
            )
            return

        self._active_name_label.configure(text=profile.name)
        detail = profile.email or "Sin sesión iniciada"
        if profile.project_id:
            detail = f"{detail}  ·  Proyecto: {profile.project_id}"
        self._active_detail_label.configure(text=detail)

        try:
            status = token_status(self._service.paths_for(profile.id))
        except Exception:
            status = TOKEN_STATUS_RECONNECT_REQUIRED
        self._active_status_label.configure(
            text=STATUS_LABELS.get(status, status),
            text_color=theme.color(self._status_color(status)),
        )

    def _refresh_table(self) -> None:
        selected = self.tree.selection()
        selected_id = selected[0] if selected else self._store.active_id
        rows = self.tree.get_children("")
        if rows:
            self.tree.delete(*rows)

        profiles = self._store.profiles
        ids: list[str] = []
        for profile in profiles:
            ids.append(profile.id)
            try:
                status = token_status(self._service.paths_for(profile.id))
            except Exception:
                status = TOKEN_STATUS_RECONNECT_REQUIRED
            self.tree.insert(
                "",
                "end",
                iid=profile.id,
                values=(
                    profile.name,
                    profile.email or "—",
                    profile.project_id or "—",
                    STATUS_LABELS.get(status, status),
                    self._format_timestamp(profile.last_used_at),
                ),
            )

        total = len(profiles)
        self._count_label.configure(
            text=(
                "1 cuenta"
                if total == 1
                else f"{total} cuentas"
            )
        )
        if total:
            self._empty_label.place_forget()
        else:
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")

        if selected_id in ids:
            self.tree.selection_set(selected_id)
            self.tree.see(selected_id)

    def _status_color(self, status: str) -> str:
        if status == TOKEN_STATUS_VALID:
            return "success"
        if status in (TOKEN_STATUS_MISSING, TOKEN_STATUS_INVALID):
            return "muted"
        return "warning"

    @staticmethod
    def _format_timestamp(value: str | None) -> str:
        """Muestra una marca ISO de forma compacta."""
        if not value:
            return "—"
        return value.replace("T", " ")[:16]

    # -- acciones ----------------------------------------------------------
    def _add_account(self) -> None:
        if self._busy:
            return
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Elegir credentials.json",
            filetypes=[
                ("Credenciales de Google", "*.json"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not path:
            return

        name = simpledialog.askstring(
            "Nombre de la cuenta",
            "Nombre para identificar esta cuenta:",
            parent=self.winfo_toplevel(),
        )
        if name is None:
            return

        self._set_busy(True, "Importando credenciales…")
        self._start_worker(self._add_worker, Path(path), name)

    def _add_worker(self, source: Path, name: str) -> None:
        try:
            profile = self._service.import_client_secrets(
                source, name=name
            )
        except Exception as exc:
            self._schedule(
                self._on_operation_error,
                exc,
                "No se pudo importar la cuenta",
            )
            return

        warning = self._service.last_warning
        try:
            connected = self._service.connect(
                profile.id,
                browser_provider=self._browser_provider,
            )
        except Exception as exc:
            self._schedule(
                self._on_add_without_session,
                profile,
                warning,
                exc,
            )
            return
        self._schedule(self._on_add_done, connected, warning)

    def _on_add_done(
        self,
        profile: AccountProfile,
        warning: str | None,
    ) -> None:
        self._set_busy(False)
        self.refresh()
        message = f"Cuenta '{profile.name}' añadida."
        if warning:
            message = f"{message} {warning}"
        self._show_message(message, "warning" if warning else "success")
        self._notify_profiles_changed()
        if self._on_profile_added is not None:
            self._on_profile_added(profile.id)

    def _on_add_without_session(
        self,
        profile: AccountProfile,
        warning: str | None,
        exc: Exception,
    ) -> None:
        self._set_busy(False)
        self.refresh()
        message = (
            f"Cuenta '{profile.name}' importada sin sesión: {self._error_text(exc)}"
        )
        if warning:
            message = f"{message} {warning}"
        self._show_message(message, "warning")
        self._notify_profiles_changed()

    def _connect_active(self) -> None:
        profile = self._store.active
        if profile is None or self._busy:
            return
        self._set_busy(True, f"Conectando con '{profile.name}'…")
        self._start_worker(self._connect_worker, profile.id)

    def _connect_worker(self, profile_id: str) -> None:
        try:
            updated = self._service.connect(
                profile_id,
                browser_provider=self._browser_provider,
            )
        except Exception as exc:
            self._schedule(
                self._on_operation_error,
                exc,
                "No se pudo conectar la cuenta",
            )
            return
        self._schedule(self._on_connect_done, updated)

    def _on_connect_done(self, profile: AccountProfile) -> None:
        self._set_busy(False)
        self.refresh()
        self._show_message(
            f"Sesión iniciada como {profile.email}.", "success"
        )
        self._notify_profiles_changed()
        if self._on_connected is not None:
            self._on_connected(profile.id)

    def _check_active(self) -> None:
        profile = self._store.active
        if profile is None or self._busy:
            return
        self._set_busy(True, "Comprobando la sesión…")
        self._start_worker(self._check_worker, profile.id)

    def _check_worker(self, profile_id: str) -> None:
        try:
            updated = self._service.refresh_profile(profile_id)
        except Exception as exc:
            self._schedule(
                self._on_operation_error,
                exc,
                "La sesión no se pudo renovar",
            )
            return
        self._schedule(self._on_check_done, updated)

    def _on_check_done(self, profile: AccountProfile) -> None:
        self._set_busy(False)
        self.refresh()
        self._show_message(
            f"La sesión de '{profile.name}' es válida.", "success"
        )
        self._notify_profiles_changed()

    def _replace_credentials(self) -> None:
        profile = self._store.active
        if profile is None or self._busy:
            return
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Elegir el nuevo credentials.json",
            filetypes=[
                ("Credenciales de Google", "*.json"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not path:
            return
        confirmed = messagebox.askyesno(
            "Reemplazar credenciales",
            "Se sustituirá el cliente OAuth de esta cuenta y se eliminará "
            "su sesión actual. Tendrás que pulsar 'Conectar' de nuevo.\n\n"
            "¿Quieres continuar?",
            parent=self.winfo_toplevel(),
        )
        if not confirmed:
            return

        self._set_busy(True, "Reemplazando credenciales…")
        self._start_worker(self._replace_worker, profile.id, Path(path))

    def _replace_worker(self, profile_id: str, source: Path) -> None:
        try:
            updated = self._service.replace_client_secrets(
                profile_id, source
            )
        except Exception as exc:
            self._schedule(
                self._on_operation_error,
                exc,
                "No se pudieron reemplazar las credenciales",
            )
            return
        self._schedule(self._on_replace_done, updated)

    def _on_replace_done(self, profile: AccountProfile) -> None:
        self._set_busy(False)
        self.refresh()
        self._show_message(
            "Credenciales reemplazadas. Pulsa 'Conectar' para iniciar sesión.",
            "warning",
        )
        self._notify_profiles_changed()
        if self._on_credentials_replaced is not None:
            self._on_credentials_replaced(profile.id)

    def _delete_selected(self) -> None:
        profile = self._selected_profile()
        if profile is None or self._busy:
            return
        confirmed = messagebox.askyesno(
            "Eliminar cuenta",
            f"¿Eliminar la cuenta '{profile.name}' "
            f"({profile.email or 'sin sesión'})?\n\n"
            "Se borrarán sus credenciales y token administrados. "
            "El archivo original que importaste no se toca.",
            parent=self.winfo_toplevel(),
        )
        if not confirmed:
            return

        self._set_busy(True, "Eliminando cuenta…")
        self._start_worker(self._delete_worker, profile.id)

    def _delete_worker(self, profile_id: str) -> None:
        try:
            removed = self._service.delete(profile_id)
        except Exception as exc:
            self._schedule(
                self._on_operation_error,
                exc,
                "No se pudo eliminar la cuenta",
            )
            return
        self._schedule(self._on_delete_done, removed)

    def _on_delete_done(self, profile: AccountProfile) -> None:
        self._set_busy(False)
        self.refresh()
        self._show_message(f"Cuenta '{profile.name}' eliminada.", "success")
        self._notify_profiles_changed()
        if self._on_profile_removed is not None:
            self._on_profile_removed(profile.id)

    def _use_selected(self) -> None:
        profile = self._selected_profile()
        if profile is None or self._busy:
            return
        if self._store.active_id == profile.id:
            return
        if self._on_switch is not None:
            self._on_switch(profile.id)
        self.refresh()

    def _on_operation_error(self, exc: Exception, prefix: str) -> None:
        self._set_busy(False)
        self.refresh()
        if isinstance(exc, AuthenticationCancelled):
            self._show_message(
                "Autenticación cancelada. No se modificó la sesión.",
                "warning",
            )
            return
        self._show_message(f"{prefix}: {self._error_text(exc)}", "danger")

    # -- estado ------------------------------------------------------------
    def _selected_profile(self) -> AccountProfile | None:
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return self._store.get(selection[0])
        except KeyError:
            return None

    def _on_selection_change(self, _event) -> None:
        self._update_buttons()

    def _update_buttons(self) -> None:
        if not hasattr(self, "_connect_button"):
            return
        active = self._store.active
        selected = self._selected_profile()
        enabled = not self._busy

        self._connect_button.configure(
            state=(
                "normal"
                if enabled and active is not None
                else "disabled"
            ),
            text="Reconectar" if active is not None and active.email else "Conectar",
        )
        self._check_button.configure(
            state=(
                "normal"
                if enabled and active is not None
                else "disabled"
            )
        )
        self._replace_button.configure(
            state=(
                "normal"
                if enabled and active is not None
                else "disabled"
            )
        )
        self._add_button.configure(
            state="normal" if enabled else "disabled"
        )
        can_use = (
            enabled
            and selected is not None
            and selected.id != self._store.active_id
        )
        self._use_button.configure(
            state="normal" if can_use else "disabled"
        )
        self._delete_button.configure(
            state="normal" if enabled and selected is not None else "disabled"
        )

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self._busy = busy
        if message is not None:
            self._show_message(message, "warning")
        self._update_buttons()

    def _show_message(self, text: str, kind: str = "muted") -> None:
        key = kind if kind in ("danger", "success", "warning") else "muted"
        self._message_label.configure(
            text=text,
            text_color=self._theme.color(key),
        )

    def _notify_profiles_changed(self) -> None:
        if self._on_profiles_changed is not None:
            self._on_profiles_changed()

    @staticmethod
    def _error_text(exc: Exception) -> str:
        text = str(exc).strip()
        return text or exc.__class__.__name__

    # -- hilos -------------------------------------------------------------
    def _start_worker(self, target, *args) -> None:
        threading.Thread(target=target, args=args, daemon=True).start()

    def _schedule(self, callback, *args) -> None:
        """Encola una actualización en el hilo principal."""
        try:
            self.after(0, callback, *args)
        except Exception:
            pass
