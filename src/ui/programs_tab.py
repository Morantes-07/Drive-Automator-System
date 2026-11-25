"""Pestaña para definir programas, patrones y carpeta destino.

Cada fila del registro asocia un programa con un patrón de nombre de archivo y
una carpeta de Drive. La carpeta se guarda como ruta lógica y puede escribirse
a mano o elegirse con el modal de selección.
"""

from __future__ import annotations

from tkinter import TclError, messagebox, ttk
from typing import Callable

import customtkinter as ctk

from src.drive.folder_tree import AmbiguousPathError, FolderTreeModel
from src.patterns import (
    PlaceholderInfo,
    PlaceholderQuery,
    apply_suggestion,
    find_placeholder_query,
    suggest_placeholders,
)
from src.programs import ProgramDefinition, ProgramStore, ProgramStoreError

from .folder_picker import pick_folder
from .suggestion_box import PlaceholderSuggestionBox
from .theme import DEFAULT_THEME, TREE_STYLE, Theme

ChangeCallback = Callable[[ProgramStore], None]


class ProgramsTab(ctk.CTkFrame):
    """Formulario y listado de programas configurados.

    Args:
        master: Widget contenedor (normalmente una pestaña de CTkTabview).
        store: Registro compartido; si no se pasa, se crea uno vacío.
        theme: Tema compartido de la aplicación.
        on_change: Se llama con el registro después de cada cambio.
    """

    def __init__(
        self,
        master,
        store: ProgramStore | None = None,
        *,
        theme: Theme = DEFAULT_THEME,
        on_change: ChangeCallback | None = None,
    ):
        super().__init__(master, fg_color="transparent")

        self._store = store if store is not None else ProgramStore()
        self._theme = theme
        self._on_change = on_change
        self._model: FolderTreeModel | None = None
        self._edit_index: int | None = None
        self._suggestion_query: PlaceholderQuery | None = None
        self._suggestion_text: str | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_form()
        self._build_table()
        self._refresh_table()

    # -- API pública -------------------------------------------------------
    @property
    def store(self) -> ProgramStore:
        """Registro de programas que edita la pestaña."""
        return self._store

    def set_model(self, model: FolderTreeModel | None) -> None:
        """Informa el árbol de carpetas disponible (None si no hay conexión)."""
        self._model = model
        self._update_buttons()

    def focus_form(self) -> None:
        """Pone el foco en el campo del nombre del programa."""
        self._program_entry.focus_set()

    def apply_theme(self) -> None:
        """Reaplica los estilos que no se actualizan solos (ttk)."""
        self.tree.configure(style=TREE_STYLE)

    # -- construcción de la interfaz --------------------------------------
    def _build_form(self) -> None:
        theme = self._theme
        card = ctk.CTkFrame(
            self,
            fg_color=theme.color("panel"),
            border_color=theme.color("border"),
            border_width=1,
            corner_radius=12,
        )
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            card,
            text="Definir programa",
            font=theme.font(15, "bold"),
            text_color=theme.color("text"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(14, 0))

        ctk.CTkLabel(
            card,
            text="Asocia un patrón de nombre de archivo con la carpeta donde debe quedar.",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            card,
            text="Programa",
            font=theme.font(11, "bold"),
            text_color=theme.color("muted"),
            anchor="w",
        ).grid(row=2, column=0, sticky="w", padx=(16, 6), pady=(0, 4))

        ctk.CTkLabel(
            card,
            text="Patrón",
            font=theme.font(11, "bold"),
            text_color=theme.color("muted"),
            anchor="w",
        ).grid(row=2, column=2, sticky="w", padx=(12, 6), pady=(0, 4))

        self._program_entry = ctk.CTkEntry(
            card,
            height=34,
            font=theme.font(12),
            placeholder_text="Power BI",
            border_color=theme.color("border"),
            fg_color=theme.color("panel_alt"),
            text_color=theme.color("text"),
        )
        self._program_entry.grid(
            row=3, column=1, sticky="ew", padx=(0, 12), pady=(0, 2)
        )

        self._pattern_entry = ctk.CTkEntry(
            card,
            height=34,
            font=theme.font(12),
            placeholder_text="G{número}-Power BI",
            border_color=theme.color("border"),
            fg_color=theme.color("panel_alt"),
            text_color=theme.color("text"),
        )
        self._pattern_entry.grid(
            row=3, column=3, sticky="ew", padx=(0, 16), pady=(0, 2)
        )

        ctk.CTkLabel(
            card,
            text="Carpeta destino",
            font=theme.font(11, "bold"),
            text_color=theme.color("muted"),
            anchor="w",
        ).grid(row=4, column=0, columnspan=4, sticky="w", padx=16, pady=(10, 4))

        self._destination_entry = ctk.CTkEntry(
            card,
            height=34,
            font=theme.font(12),
            placeholder_text="Mi Drive/Power BI/2024",
            border_color=theme.color("border"),
            fg_color=theme.color("panel_alt"),
            text_color=theme.color("text"),
        )
        self._destination_entry.grid(
            row=5, column=0, columnspan=3, sticky="ew", padx=(16, 12)
        )

        self._destination_button = ctk.CTkButton(
            card,
            text="Elegir carpeta…",
            width=150,
            height=34,
            command=self._choose_destination,
            fg_color=theme.color("panel_alt"),
            hover_color=theme.color("border"),
            border_width=1,
            border_color=theme.color("border"),
            text_color=theme.color("text"),
        )
        self._destination_button.grid(
            row=5, column=3, sticky="ew", padx=(0, 16)
        )

        hint = ctk.CTkLabel(
            card,
            text=(
                "El patrón admite {número}, {letra} y {palabra}. "
                "Escribe \'{\' para ver qué captura cada uno.\n"
                "La carpeta destino se guarda como ruta lógica."
            ),
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
            justify="left",
            wraplength=540,
        )
        hint.grid(
            row=6, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 14)
        )

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(
            row=6,
            column=2,
            columnspan=2,
            sticky="e",
            padx=16,
            pady=(12, 14),
        )

        self._clear_button = ctk.CTkButton(
            actions,
            text="Limpiar",
            width=90,
            height=34,
            command=self._new,
            fg_color=theme.color("panel_alt"),
            hover_color=theme.color("border"),
            text_color=theme.color("text"),
        )
        self._clear_button.pack(side="left", padx=(0, 8))

        self._submit_button = ctk.CTkButton(
            actions,
            text="Añadir programa",
            width=160,
            height=34,
            command=self._submit,
            fg_color=theme.color("accent"),
            hover_color=theme.color("accent_hover"),
            text_color=theme.color("accent_text"),
        )
        self._submit_button.pack(side="left")

        self._message_label = ctk.CTkLabel(
            card,
            text="",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        )
        self._message_label.grid(
            row=7, column=0, columnspan=4, sticky="w", padx=16, pady=(0, 12)
        )

        for entry in (self._program_entry, self._destination_entry):
            entry.bind("<Return>", lambda _event: self._submit())

        self._suggestions = PlaceholderSuggestionBox(
            card,
            theme=theme,
            on_pick=self._insert_suggestion,
        )
        self._pattern_entry.bind("<Return>", self._on_pattern_return)
        self._pattern_entry.bind("<KeyRelease>", self._on_pattern_key_release)
        self._pattern_entry.bind("<ButtonRelease-1>", self._on_pattern_click)
        self._pattern_entry.bind("<Down>", self._on_pattern_down)
        self._pattern_entry.bind("<Up>", self._on_pattern_up)
        self._pattern_entry.bind("<Tab>", self._on_pattern_tab)
        self._pattern_entry.bind("<Escape>", self._on_pattern_escape)
        self._pattern_entry.bind("<FocusOut>", self._on_pattern_focus_out)
        self._pattern_entry.bind("<Configure>", self._on_pattern_configure)

    # -- sugerencias de placeholders --------------------------------------
    def _update_suggestions(self) -> None:
        """Recalcula y muestra las sugerencias para el cursor actual."""
        text = self._pattern_entry.get()
        query = find_placeholder_query(
            text,
            self._pattern_entry.index("insert"),
        )
        if query is None:
            self._hide_suggestions()
            return

        items = suggest_placeholders(query)
        if not items:
            self._hide_suggestions()
            return

        self._suggestion_query = query
        self._suggestion_text = text
        self._suggestions.show(items)
        self._position_suggestions()

    def _position_suggestions(self) -> None:
        """Coloca la lista justo debajo del campo de patrón."""
        if not self._suggestions.is_visible:
            return
        card = self._pattern_entry.master
        card_width = card.winfo_width()
        relwidth = (
            self._pattern_entry.winfo_width() / card_width
            if card_width > 0
            else 1.0
        )
        self._suggestions.place(
            x=self._pattern_entry.winfo_x(),
            y=(
                self._pattern_entry.winfo_y()
                + self._pattern_entry.winfo_height()
                + 2
            ),
            relwidth=relwidth,
        )
        self._suggestions.lift()

    def _hide_suggestions(self) -> None:
        self._suggestion_query = None
        self._suggestion_text = None
        self._suggestions.hide()

    def _insert_suggestion(self, info: PlaceholderInfo) -> None:
        """Sustituye el placeholder en curso por el elegido."""
        query = self._suggestion_query
        text = self._suggestion_text
        if query is None or text is None:
            return

        new_text, caret = apply_suggestion(text, query, info)
        self._hide_suggestions()
        self._pattern_entry.delete(0, "end")
        self._pattern_entry.insert(0, new_text)
        self._pattern_entry.icursor(caret)
        self._pattern_entry.focus_set()

    def _on_pattern_key_release(self, event) -> None:
        if event.keysym in {"Up", "Down", "Tab", "Escape", "Return"}:
            return
        self._update_suggestions()

    def _on_pattern_click(self, _event) -> None:
        self.after_idle(self._update_suggestions)

    def _on_pattern_down(self, _event):
        if not self._suggestions.is_visible:
            return None
        self._suggestions.move_selection(1)
        return "break"

    def _on_pattern_up(self, _event):
        if not self._suggestions.is_visible:
            return None
        self._suggestions.move_selection(-1)
        return "break"

    def _on_pattern_tab(self, _event):
        if not self._suggestions.is_visible:
            return None
        self._suggestions.accept()
        return "break"

    def _on_pattern_escape(self, _event):
        if not self._suggestions.is_visible:
            return None
        self._hide_suggestions()
        return "break"

    def _on_pattern_return(self, _event):
        if self._suggestions.is_visible:
            self._suggestions.accept()
            return "break"
        self._submit()
        return "break"

    def _on_pattern_focus_out(self, _event) -> None:
        # Se retrasa el cierre para que un clic en una sugerencia llegue antes
        # de que el campo pierda el foco.
        self.after(120, self._hide_suggestions_if_unfocused)

    def _hide_suggestions_if_unfocused(self) -> None:
        try:
            focused = self.focus_get()
            if focused is not self._pattern_entry._entry:
                self._hide_suggestions()
        except TclError:
            return

    def _on_pattern_configure(self, _event) -> None:
        self._position_suggestions()

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
            text="Programas definidos",
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

        tree_frame = ctk.CTkFrame(card, fg_color="transparent")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=16)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("programa", "patron", "destino"),
            show="headings",
            selectmode="browse",
            style=TREE_STYLE,
            height=6,
        )
        self.tree.heading("programa", text="Programa", anchor="w")
        self.tree.heading("patron", text="Patrón", anchor="w")
        self.tree.heading("destino", text="Carpeta destino", anchor="w")
        self.tree.column("programa", width=190, minwidth=120, stretch=False, anchor="w")
        self.tree.column("patron", width=300, minwidth=180, stretch=False, anchor="w")
        self.tree.column("destino", width=420, minwidth=200, stretch=True, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_row_selected)

        self._table_scrollbar = ctk.CTkScrollbar(
            tree_frame, command=self.tree.yview, width=12
        )
        self._table_scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        self.tree.configure(yscrollcommand=self._table_scrollbar.set)

        self._empty_label = ctk.CTkLabel(
            tree_frame,
            text=(
                "Aún no hay programas definidos.\n"
                "Completa el formulario para añadir el primero."
            ),
            font=theme.font(12),
            text_color=theme.color("muted"),
            justify="center",
        )

        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=16, pady=(10, 14))
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            footer,
            text="Selecciona un programa de la lista para editarlo.",
            font=theme.font(11),
            text_color=theme.color("muted"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._delete_button = ctk.CTkButton(
            footer,
            text="Eliminar",
            width=100,
            height=30,
            command=self._delete,
            fg_color="transparent",
            hover_color=theme.color("panel_alt"),
            border_width=1,
            border_color=theme.color("danger"),
            text_color=theme.color("danger"),
        )
        self._delete_button.grid(row=0, column=1, sticky="e")

    # -- tabla -------------------------------------------------------------
    def _refresh_table(self) -> None:
        current = self.tree.selection()
        if current:
            self.tree.selection_remove(*current)
        rows = self.tree.get_children("")
        if rows:
            self.tree.delete(*rows)

        for index, item in enumerate(self._store.items()):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(item.program, item.pattern, item.destination_path),
            )

        total = len(self._store)
        self._count_label.configure(
            text=f"{total} programa" if total == 1 else f"{total} programas"
        )
        if total:
            self._empty_label.place_forget()
        else:
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")

        if self._edit_index is not None and 0 <= self._edit_index < total:
            iid = str(self._edit_index)
            self.tree.selection_set(iid)
            self.tree.see(iid)

        self._update_buttons()

    def _on_row_selected(self, _event) -> None:
        selection = self.tree.selection()
        if not selection:
            self._update_buttons()
            return
        index = int(selection[0])
        if not 0 <= index < len(self._store):
            return

        item = self._store.get(index)
        self._edit_index = index
        self._hide_suggestions()
        self._set_entry(self._program_entry, item.program)
        self._set_entry(self._pattern_entry, item.pattern)
        self._set_entry(self._destination_entry, item.destination_path)
        self._show_message("Editando el programa seleccionado.", "muted")
        self._update_buttons()

    @staticmethod
    def _set_entry(entry: ctk.CTkEntry, value: str) -> None:
        entry.delete(0, "end")
        entry.insert(0, value)

    # -- acciones ----------------------------------------------------------
    def _submit(self) -> None:
        self._hide_suggestions()
        definition = ProgramDefinition(
            program=self._program_entry.get(),
            pattern=self._pattern_entry.get(),
            destination_path=self._destination_entry.get(),
        )

        destination_id = None
        if self._model is not None and definition.destination_path:
            try:
                node = self._model.resolve_path(definition.destination_path)
            except AmbiguousPathError as exc:
                self._show_message(str(exc), "danger")
                return
            if node is None:
                self._show_message(
                    f"La carpeta destino no existe en Drive: "
                    f"'{definition.destination_path}'.",
                    "danger",
                )
                return
            destination_id = node.id

        definition = ProgramDefinition(
            program=definition.program,
            pattern=definition.pattern,
            destination_path=definition.destination_path,
            destination_id=destination_id,
        )

        try:
            if self._edit_index is None:
                self._store.add(definition)
                message = f"Programa '{definition.program}' añadido."
            else:
                self._store.update(self._edit_index, definition)
                message = f"Programa '{definition.program}' actualizado."
        except ProgramStoreError as exc:
            self._show_message(str(exc), "danger")
            return

        self._edit_index = None
        self._refresh_table()
        self._clear_form()
        self._show_message(message, "success")
        self._notify_change()

    def _new(self) -> None:
        """Sale del modo edición y vacía el formulario."""
        self._edit_index = None
        self._clear_form()
        self._show_message("", "muted")

    def _clear_form(self) -> None:
        self._hide_suggestions()
        for entry in (
            self._program_entry,
            self._pattern_entry,
            self._destination_entry,
        ):
            self._reset_entry(entry)
        self._update_buttons()
        self._program_entry.focus_set()

    @staticmethod
    def _reset_entry(entry: ctk.CTkEntry) -> None:
        """Vacía el campo y vuelve a mostrar su placeholder.

        ``CTkEntry.delete`` solo reactiva el placeholder cuando el campo no
        tiene el foco, y su bandera interna arranca en ``True``; por eso se
        fuerza aquí la reactivación.
        """
        try:
            focused = entry.focus_get() is entry._entry
        except Exception:
            focused = False
        entry.delete(0, "end")
        if not focused:
            activate = getattr(entry, "_activate_placeholder", None)
            if activate is not None:
                activate()

    def _delete(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        index = int(selection[0])
        item = self._store.get(index)
        confirmed = messagebox.askyesno(
            "Eliminar programa",
            f"¿Eliminar el programa '{item.program}'?",
            parent=self.winfo_toplevel(),
        )
        if not confirmed:
            return

        self._store.remove(index)
        self._edit_index = None
        self._refresh_table()
        self._clear_form()
        self._show_message(f"Programa '{item.program}' eliminado.", "success")
        self._notify_change()

    def _choose_destination(self) -> None:
        if self._model is None:
            self._show_message(
                "Las carpetas de Drive todavía no están cargadas.", "warning"
            )
            return

        initial = self._destination_entry.get().strip() or None
        result = pick_folder(
            self.winfo_toplevel(),
            self._model,
            initial_path=initial,
            theme=self._theme,
        )
        if result is None:
            return

        _folder_id, path = result
        self._set_entry(self._destination_entry, path)
        self._show_message(f"Destino elegido: {path}", "success")

    # -- estado ------------------------------------------------------------
    def _update_buttons(self) -> None:
        if not hasattr(self, "_submit_button"):
            return
        editing = self._edit_index is not None
        self._submit_button.configure(
            text="Guardar cambios" if editing else "Añadir programa"
        )
        selected = bool(self.tree.selection()) if hasattr(self, "tree") else False
        self._delete_button.configure(state="normal" if selected else "disabled")
        self._destination_button.configure(
            state="normal" if self._model is not None else "disabled"
        )

    def _show_message(self, text: str, kind: str = "muted") -> None:
        key = kind if kind in ("danger", "success", "warning") else "muted"
        self._message_label.configure(
            text=text,
            text_color=self._theme.color(key),
        )

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change(self._store)
