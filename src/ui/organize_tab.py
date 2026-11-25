"""Pestaña para escanear, planificar y organizar archivos de Drive.

La lógica de negocio vive en ``src.workflow.organizer``. Esta pestaña solo
recoge la selección de tipos de archivo, lanza el trabajo en un hilo y pinta
el plan y el reporte.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

import customtkinter as ctk

from src.authentication.auth import (
    AuthenticationCancelled,
    BrowserProvider,
    get_credentials,
)
from src.config import DRY_RUN
from src.drive.drive_client import get_service, list_files
from src.drive.file_types import CATEGORY_LABELS, filter_files
from src.drive.folder_tree import FolderTreeModel
from src.drive.queries import QUERY_OWNED
from src.programs import ProgramStore
from src.runtime_settings import RuntimeSettings
from src.workflow.organizer import (
    FolderCreationResult,
    FolderError,
    OrganizationPlan,
    OrganizationReport,
    PlannedFile,
    build_plan,
    create_missing_folders,
    execute_plan,
)

from .theme import DEFAULT_THEME, TREE_STYLE, Theme

#: Etiquetas de estado para la tabla.
STATUS_LABELS: dict[str, str] = {
    "ready": "Listo",
    "missing_folder": "Falta carpeta",
    "already_in_place": "Ya está",
    "ambiguous": "Ambiguo",
    "unmatched": "Sin patrón",
    "error": "Error",
}

#: Columnas de la tabla de plan.
COLUMNS = ("archivo", "programa", "subcarpeta", "estado", "detalle")

ReloadCallback = Callable[[], None]
DryRunChangeCallback = Callable[[bool], None]


class OrganizeTab(ctk.CTkFrame):
    """Pestaña de organización: filtros, plan y ejecución.

    Args:
        master: Widget contenedor (una pestaña de ``CTkTabview``).
        store: Registro compartido de programas.
        theme: Tema compartido de la aplicación.
        on_reload: Se llama para recargar el árbol de Drive después de crear
            carpetas o mover archivos.
        settings: Ajustes mutables de la sesión. Si se omite, se crea uno con
            el valor de ``config.DRY_RUN``.
        on_dry_run_change: Se llama cuando cambia el modo de simulación.
        browser_provider: Se llama si hay que regenerar el token para elegir
            el navegador de autenticación.
    """

    def __init__(
        self,
        master,
        store: ProgramStore,
        *,
        theme: Theme = DEFAULT_THEME,
        on_reload: ReloadCallback | None = None,
        settings: RuntimeSettings | None = None,
        on_dry_run_change: DryRunChangeCallback | None = None,
        browser_provider: BrowserProvider | None = None,
    ):
        super().__init__(master, fg_color="transparent")

        self._store = store
        self._theme = theme
        self._on_reload = on_reload
        self._settings = settings or RuntimeSettings(dry_run=DRY_RUN)
        self._on_dry_run_change = on_dry_run_change
        self._browser_provider = browser_provider
        self._dry_run_var = tk.BooleanVar(value=self._settings.dry_run)
        self._model: FolderTreeModel | None = None
        self._plan: OrganizationPlan | None = None
        self._busy = False
        self._generation = 0
        self._category_vars: dict[str, tk.BooleanVar] = {}
        self._category_checks: list[ctk.CTkCheckBox] = []
        self._selected_categories: set[str] = set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_filters()
        self._build_actions()
        self._build_table()
        self._build_summary()
        self._update_buttons()
        self._show_message(
            "Conecta con Drive y pulsa 'Escanear archivos'.", "muted"
        )

    # -- API pública -------------------------------------------------------
    @property
    def plan(self) -> OrganizationPlan | None:
        """Plan actual, o None si todavía no se ha escaneado."""
        return self._plan

    def set_model(self, model: FolderTreeModel | None) -> None:
        """Actualiza el árbol de carpetas disponible."""
        self._model = model
        self._clear_plan()
        self._update_buttons()
        if model is None:
            self._show_message(
                "Las carpetas de Drive todavía no están cargadas.",
                "warning",
            )
        else:
            self._show_message(
                "Pulsa 'Escanear archivos' para analizar Drive.", "muted"
            )

    def invalidate_plan(self) -> None:
        """Descarta el plan cuando cambian los programas definidos."""
        had_plan = self._plan is not None
        was_busy = self._busy
        self._clear_plan()
        if had_plan or was_busy:
            self._show_message(
                "Los programas cambiaron. Vuelve a escanear.", "warning"
            )

    def apply_theme(self) -> None:
        """Reaplica el estilo del árbol tras cambiar de modo."""
        self.tree.configure(style=TREE_STYLE)

    # -- construcción de la interfaz --------------------------------------
    def _build_filters(self) -> None:
        theme = self._theme
        card = ctk.CTkFrame(
            self,
            fg_color=theme.color("panel"),
            border_color=theme.color("border"),
            border_width=1,
            corner_radius=12,
        )
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for column in range(3):
            card.grid_columnconfigure(column, weight=1)

        ctk.CTkLabel(
            card,
            text="Tipos de archivo",
            font=theme.font(15, "bold"),
            text_color=theme.color("text"),
            anchor="w",
        ).grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
            padx=16,
            pady=(14, 0),
        )

        ctk.CTkLabel(
            card,
            text="Sin selección = todos los tipos. Puedes marcar varios.",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        ).grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="w",
            padx=16,
            pady=(0, 10),
        )

        for index, (key, label) in enumerate(CATEGORY_LABELS.items()):
            row = 2 + index // 3
            column = index % 3
            variable = tk.BooleanVar(value=False)
            self._category_vars[key] = variable
            check = ctk.CTkCheckBox(
                card,
                text=label,
                variable=variable,
                command=self._on_category_change,
                font=theme.font(11),
                text_color=theme.color("text"),
                fg_color=theme.color("accent"),
                hover_color=theme.color("accent_hover"),
                border_color=theme.color("border"),
                checkmark_color=theme.color("accent_text"),
            )
            check.grid(
                row=row,
                column=column,
                sticky="w",
                padx=16,
                pady=(0, 6),
            )
            self._category_checks.append(check)

        rows = 2 + (len(CATEGORY_LABELS) + 2) // 3
        self._clear_categories_button = ctk.CTkButton(
            card,
            text="Limpiar selección",
            width=140,
            height=28,
            command=self._clear_categories,
            fg_color=theme.color("panel_alt"),
            hover_color=theme.color("border"),
            text_color=theme.color("text"),
        )
        self._clear_categories_button.grid(
            row=rows,
            column=0,
            columnspan=3,
            sticky="w",
            padx=16,
            pady=(4, 14),
        )

    def _build_actions(self) -> None:
        theme = self._theme
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        bar.grid_columnconfigure(1, weight=1)

        self._scan_button = ctk.CTkButton(
            bar,
            text="Escanear archivos",
            width=150,
            height=32,
            command=self._scan,
            fg_color=theme.color("accent"),
            hover_color=theme.color("accent_hover"),
            text_color=theme.color("accent_text"),
        )
        self._scan_button.grid(row=0, column=0, sticky="w")

        self._status_label = ctk.CTkLabel(
            bar,
            text="",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        )
        self._status_label.grid(row=0, column=1, sticky="w", padx=12)

        self._dry_run_switch = ctk.CTkSwitch(
            bar,
            text="",
            width=40,
            command=self._on_dry_run_toggle,
            variable=self._dry_run_var,
            onvalue=True,
            offvalue=False,
            progress_color=theme.color("accent"),
            fg_color=theme.color("border"),
            button_color=theme.color("panel"),
            button_hover_color=theme.color("border"),
        )
        self._dry_run_switch.grid(
            row=0, column=2, sticky="e", padx=(0, 8)
        )

        self._dry_run_label = ctk.CTkLabel(
            bar,
            text="",
            font=theme.font(11, "bold"),
            text_color=theme.color("warning"),
            anchor="e",
        )
        self._dry_run_label.grid(row=0, column=3, sticky="e")
        self._update_dry_run_display()

    def _on_dry_run_toggle(self) -> None:
        """Cambia el modo de simulación desde el switch."""
        if self._busy:
            self._dry_run_var.set(self._settings.dry_run)
            return
        dry_run = bool(self._dry_run_var.get())
        if not dry_run:
            confirmed = messagebox.askyesno(
                "Desactivar la simulación",
                "Vas a desactivar la prueba en seco.\n\n"
                "Las próximas carpetas y movimientos se aplicarán de "
                "verdad en Google Drive.\n\n"
                "¿Quieres continuar?",
                parent=self.winfo_toplevel(),
            )
            if not confirmed:
                self._dry_run_var.set(True)
                return
        self._set_dry_run(dry_run)

    def _set_dry_run(self, dry_run: bool) -> None:
        """Fija el modo y sincroniza el switch con el resto de la app."""
        self._settings.dry_run = dry_run
        self._update_dry_run_display()
        if self._on_dry_run_change is not None:
            self._on_dry_run_change(dry_run)

    def _update_dry_run_display(self) -> None:
        """Pinta el estado actual de la prueba en seco."""
        if not hasattr(self, "_dry_run_label"):
            return
        dry_run = self._settings.dry_run
        self._dry_run_label.configure(
            text=(
                "PRUEBA EN SECO: ACTIVADA"
                if dry_run
                else "PRUEBA EN SECO: DESACTIVADA"
            ),
            text_color=self._theme.color(
                "warning" if dry_run else "success"
            ),
        )
        if bool(self._dry_run_var.get()) != dry_run:
            self._dry_run_var.set(dry_run)

    def _build_table(self) -> None:
        theme = self._theme
        card = ctk.CTkFrame(
            self,
            fg_color=theme.color("panel"),
            border_color=theme.color("border"),
            border_width=1,
            corner_radius=12,
        )
        card.grid(row=2, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(card, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=14)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            frame,
            columns=COLUMNS,
            show="headings",
            selectmode="browse",
            style=TREE_STYLE,
            height=10,
        )
        self.tree.heading("archivo", text="Archivo", anchor="w")
        self.tree.heading("programa", text="Programa", anchor="w")
        self.tree.heading("subcarpeta", text="Subcarpeta", anchor="w")
        self.tree.heading("estado", text="Estado", anchor="w")
        self.tree.heading("detalle", text="Detalle", anchor="w")
        self.tree.column(
            "archivo", width=220, minwidth=140, stretch=True, anchor="w"
        )
        self.tree.column(
            "programa", width=130, minwidth=90, stretch=False, anchor="w"
        )
        self.tree.column(
            "subcarpeta", width=200, minwidth=130, stretch=True, anchor="w"
        )
        self.tree.column(
            "estado", width=100, minwidth=90, stretch=False, anchor="w"
        )
        self.tree.column(
            "detalle", width=280, minwidth=160, stretch=True, anchor="w"
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        self._scrollbar = ctk.CTkScrollbar(
            frame, command=self.tree.yview, width=12
        )
        self._scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        self.tree.configure(yscrollcommand=self._scrollbar.set)

        self._empty_label = ctk.CTkLabel(
            frame,
            text="Sin plan todavía.\nPulsa 'Escanear archivos'.",
            font=theme.font(12),
            text_color=theme.color("muted"),
            justify="center",
        )
        self._empty_label.place(relx=0.5, rely=0.5, anchor="center")

    def _build_summary(self) -> None:
        theme = self._theme
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        footer.grid_columnconfigure(0, weight=1)

        self._summary_label = ctk.CTkLabel(
            footer,
            text="",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        )
        self._summary_label.grid(row=0, column=0, sticky="w")

        self._organize_button = ctk.CTkButton(
            footer,
            text="Organizar",
            width=120,
            height=32,
            command=self._organize,
            fg_color=theme.color("accent"),
            hover_color=theme.color("accent_hover"),
            text_color=theme.color("accent_text"),
        )
        self._organize_button.grid(row=0, column=1, padx=(8, 0))

        self._create_button = ctk.CTkButton(
            footer,
            text="Crear carpetas y mover",
            width=180,
            height=32,
            command=self._create_and_move,
            fg_color=theme.color("panel_alt"),
            hover_color=theme.color("border"),
            border_width=1,
            border_color=theme.color("border"),
            text_color=theme.color("text"),
        )
        self._create_button.grid(row=0, column=2, padx=(8, 0))

    # -- filtros -----------------------------------------------------------
    def _on_category_change(self) -> None:
        self._selected_categories = {
            key
            for key, variable in self._category_vars.items()
            if variable.get()
        }
        self._clear_plan()
        self._show_message(
            "Filtro actualizado. Vuelve a escanear.", "warning"
        )

    def _clear_categories(self) -> None:
        for variable in self._category_vars.values():
            variable.set(False)
        self._selected_categories.clear()
        self._clear_plan()
        self._show_message(
            "Sin filtro: se incluirán todos los tipos.", "muted"
        )

    # -- escaneo -----------------------------------------------------------
    def _scan(self) -> None:
        if self._busy:
            return
        if self._model is None:
            self._show_message(
                "Las carpetas de Drive todavía no están cargadas.",
                "warning",
            )
            return

        model = self._model
        store = self._store
        categories = set(self._selected_categories)

        self._busy = True
        self._clear_plan()
        generation = self._generation
        self._show_message("Escaneando archivos de Drive…", "warning")
        self._update_buttons()

        threading.Thread(
            target=self._scan_worker,
            args=(categories, model, store, generation),
            daemon=True,
        ).start()

    def _scan_worker(
        self,
        categories: set[str],
        model: FolderTreeModel,
        store: ProgramStore,
        generation: int,
    ) -> None:
        """Lista, filtra y planifica sin tocar la interfaz."""
        try:
            credentials = get_credentials(
                browser_provider=self._browser_provider
            )
            service = get_service(credentials)
            files = list_files(service, QUERY_OWNED)
            files = [
                file
                for file in files
                if not bool(file.get("shared", False))
            ]
            files = filter_files(files, categories or None)
            plan = build_plan(files, model, store)
        except Exception as exc:
            self._schedule(self._on_scan_error, exc, generation)
            return
        self._schedule(self._on_scan_done, plan, generation)

    def _on_scan_done(
        self, plan: OrganizationPlan, generation: int
    ) -> None:
        self._busy = False
        if generation != self._generation:
            self._update_buttons()
            return
        self._plan = plan
        self._refresh_table()
        self._update_summary()
        self._update_buttons()
        self._show_message(
            f"Análisis completado: {len(plan.files)} archivos revisados.",
            "success",
        )

    def _on_scan_error(self, exc: Exception, generation: int) -> None:
        self._busy = False
        self._update_buttons()
        if generation != self._generation:
            return
        if isinstance(exc, AuthenticationCancelled):
            self._show_message(
                "Autenticación cancelada. No se generó el token.", "warning"
            )
            return
        self._show_message(f"No se pudo escanear Drive: {exc}", "danger")

    # -- ejecución ---------------------------------------------------------
    def _organize(self) -> None:
        if self._busy or self._plan is None:
            return
        ready = len(self._plan.ready)
        if ready == 0:
            self._show_message(
                "No hay archivos listos para mover.", "warning"
            )
            return
        if not self._settings.dry_run:
            confirmed = messagebox.askyesno(
                "Organizar archivos",
                f"¿Mover {ready} archivos a sus subcarpetas?",
                parent=self.winfo_toplevel(),
            )
            if not confirmed:
                return
        self._start_execution(create_missing=False)

    def _create_and_move(self) -> None:
        if self._busy or self._plan is None:
            return
        missing = len(self._plan.missing_folders)
        pending = len(self._plan.missing)
        total = pending + len(self._plan.ready)
        if missing == 0:
            self._show_message(
                "No faltan carpetas por crear.", "muted"
            )
            return
        if not self._settings.dry_run:
            confirmed = messagebox.askyesno(
                "Crear carpetas y mover",
                f"¿Crear {missing} carpetas y mover {total} archivos?",
                parent=self.winfo_toplevel(),
            )
            if not confirmed:
                return
        self._start_execution(create_missing=True)

    def _start_execution(self, create_missing: bool) -> None:
        plan = self._plan
        if plan is None:
            return
        dry_run = self._settings.dry_run
        self._busy = True
        self._show_message(
            "Simulando la organización…"
            if dry_run
            else "Organizando archivos…",
            "warning",
        )
        self._update_buttons()
        generation = self._generation
        threading.Thread(
            target=self._execute_worker,
            args=(create_missing, plan, generation, dry_run),
            daemon=True,
        ).start()

    def _execute_worker(
        self,
        create_missing: bool,
        plan: OrganizationPlan,
        generation: int,
        dry_run: bool,
    ) -> None:
        """Crea carpetas (si hace falta) y mueve los archivos."""
        try:
            service = None
            if not dry_run:
                credentials = get_credentials(
                    browser_provider=self._browser_provider
                )
                service = get_service(credentials)

            if create_missing and dry_run:
                # En simulación se usan ids ficticios para que el reporte
                # cuente también los archivos cuya carpeta se crearía.
                creation = FolderCreationResult(
                    created={
                        (missing.parent_id, missing.name): (
                            f"dry-run:{index}"
                        )
                        for index, missing in enumerate(
                            plan.missing_folders
                        )
                    },
                    errors=(),
                )
            elif create_missing:
                creation = create_missing_folders(
                    service, plan, dry_run=False
                )
            else:
                creation = FolderCreationResult(created={}, errors=())

            folder_errors = {
                (error.parent_id, error.name): error.message
                for error in creation.errors
            }
            report = execute_plan(
                service,
                plan,
                folder_ids=dict(creation.created),
                dry_run=dry_run,
                folder_errors=folder_errors,
            )
        except Exception as exc:
            self._schedule(
                self._on_execute_error, exc, generation, dry_run
            )
            return
        self._schedule(
            self._on_execute_done, report, creation, generation
        )

    def _on_execute_done(
        self,
        report: OrganizationReport,
        creation: FolderCreationResult,
        generation: int,
    ) -> None:
        self._busy = False
        if not report.dry_run:
            # Una ejecución real siempre vuelve al modo seguro.
            self._set_dry_run(True)
        if generation != self._generation:
            self._update_buttons()
            return

        self._refresh_table(report)
        self._update_summary()
        self._update_buttons()

        moved = len(report.moved)
        errors = len(report.errors)
        created = len(creation.created)
        failed = len(creation.errors)
        if report.dry_run:
            if created:
                message = (
                    f"Simulación: se crearían {created} carpetas y se "
                    f"moverían {moved} archivos."
                )
            else:
                message = f"Simulación: se moverían {moved} archivos."
        else:
            message = f"Se movieron {moved} archivos."
            if created:
                message += f" Se crearon {created} carpetas."
        if failed:
            message += f" No se pudieron crear {failed} carpetas."
        if errors:
            message += f" {errors} errores."

        if creation.errors:
            self._show_folder_errors(creation.errors)

        if (
            not report.dry_run
            and (report.moved or creation.created)
            and self._on_reload is not None
        ):
            self._on_reload()

        self._show_message(
            message,
            "success" if not errors and not failed else "warning",
        )

    def _show_folder_errors(
        self, errors: tuple[FolderError, ...]
    ) -> None:
        """Muestra un aviso con las carpetas que no se pudieron crear."""
        lines = [
            f"• {error.name} ({error.parent_path})\n"
            f"  Motivo: {error.message}"
            for error in errors
        ]
        messagebox.showwarning(
            "Carpetas no creadas",
            "No se pudieron crear estas carpetas:\n\n"
            + "\n\n".join(lines),
            parent=self.winfo_toplevel(),
        )

    def _on_execute_error(
        self, exc: Exception, generation: int, dry_run: bool
    ) -> None:
        self._busy = False
        if not dry_run:
            # La ejecución real falló, pero el modo seguro debe recuperarse.
            self._set_dry_run(True)
        self._update_buttons()
        if generation != self._generation:
            return
        if isinstance(exc, AuthenticationCancelled):
            self._show_message(
                "Autenticación cancelada. No se generó el token.", "warning"
            )
            return
        if not dry_run and self._on_reload is not None:
            # Una creación parcial pudo dejar carpetas nuevas en Drive.
            self._on_reload()
        if dry_run:
            message = f"Simulación fallida: {exc}"
        else:
            message = f"No se pudo organizar: {exc}"
        self._show_message(message, "danger")

    # -- tabla y resumen ---------------------------------------------------
    def _refresh_table(
        self, report: OrganizationReport | None = None
    ) -> None:
        rows = self.tree.get_children("")
        if rows:
            self.tree.delete(*rows)

        if self._plan is None or not self._plan.files:
            self._empty_label.place(
                relx=0.5, rely=0.5, anchor="center"
            )
            return

        results: dict[str, PlannedFile] = {}
        if report is not None:
            for group in (
                report.moved,
                report.pending,
                report.errors,
                report.already_in_place,
                report.ambiguous,
                report.unmatched,
            ):
                for item in group:
                    if item.file_id:
                        results[item.file_id] = item

        self._empty_label.place_forget()
        for index, item in enumerate(self._plan.files):
            shown = results.get(item.file_id, item)
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    shown.file_name,
                    shown.program or "",
                    shown.folder_name or "",
                    STATUS_LABELS.get(shown.status, shown.status),
                    shown.message or "",
                ),
            )

    def _update_summary(self) -> None:
        if self._plan is None:
            self._summary_label.configure(text="")
            return
        plan = self._plan
        parts = [
            f"{len(plan.ready)} listos",
            f"{len(plan.missing_folders)} carpetas faltantes",
            f"{len(plan.already_in_place)} ya están",
            f"{len(plan.ambiguous)} ambiguos",
            f"{len(plan.unmatched)} sin patrón",
        ]
        if plan.errors:
            parts.append(f"{len(plan.errors)} errores")
        self._summary_label.configure(text=" · ".join(parts))

    def _update_buttons(self) -> None:
        if not hasattr(self, "_scan_button"):
            return
        has_model = self._model is not None
        has_plan = self._plan is not None
        ready = len(self._plan.ready) if has_plan else 0
        missing = (
            len(self._plan.missing_folders) if has_plan else 0
        )

        self._scan_button.configure(
            state=(
                "normal"
                if has_model and not self._busy
                else "disabled"
            )
        )
        filters_state = "normal" if not self._busy else "disabled"
        for check in self._category_checks:
            check.configure(state=filters_state)
        self._clear_categories_button.configure(state=filters_state)
        self._organize_button.configure(
            state=(
                "normal"
                if ready and not self._busy
                else "disabled"
            )
        )
        self._create_button.configure(
            state=(
                "normal"
                if missing and not self._busy
                else "disabled"
            )
        )
        self._dry_run_switch.configure(
            state="disabled" if self._busy else "normal"
        )

    def _clear_plan(self) -> None:
        self._generation += 1
        self._plan = None
        if hasattr(self, "tree"):
            rows = self.tree.get_children("")
            if rows:
                self.tree.delete(*rows)
            self._empty_label.place(
                relx=0.5, rely=0.5, anchor="center"
            )
        if hasattr(self, "_summary_label"):
            self._summary_label.configure(text="")

    # -- mensajes e hilos --------------------------------------------------
    def _show_message(self, text: str, kind: str = "muted") -> None:
        key = kind if kind in ("danger", "success", "warning") else "muted"
        self._status_label.configure(
            text=text,
            text_color=self._theme.color(key),
        )

    def _schedule(self, callback, *args) -> None:
        """Encola una actualización en el hilo principal."""
        try:
            self.after(0, callback, *args)
        except Exception:
            pass
