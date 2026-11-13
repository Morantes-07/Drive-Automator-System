"""Modal para elegir una carpeta de Drive.

Comportamiento validado en S7:

- ``grab_set()`` en un ``Toplevel`` crea un *grab local*: bloquea la ventana
  padre (que es lo que se busca) sin secuestrar el resto del escritorio.
- ``wait_window()`` bloquea el hilo principal, pero el bucle de eventos sigue
  vivo.
- Escape, el botón Cancelar y la X devuelven ``None``; seleccionar devuelve
  ``(id, ruta)``.
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from src.drive.folder_tree import AmbiguousPathError, FolderTreeModel

from .folder_explorer import FolderExplorer
from .theme import DEFAULT_THEME, Theme

#: Tamaño del modal, en píxeles.
DIALOG_WIDTH = 700
DIALOG_HEIGHT = 600


class FolderPickerDialog(ctk.CTkToplevel):
    """Ventana modal que devuelve la carpeta elegida.

    Args:
        parent: Ventana sobre la que se centra y a la que bloquea.
        model: Árbol de carpetas ya cargado.
        title: Título de la ventana.
        initial_path: Ruta lógica que se selecciona al abrir.
        theme: Tema compartido de la aplicación.
    """

    def __init__(
        self,
        parent,
        model: FolderTreeModel,
        *,
        title: str = "Seleccionar carpeta",
        initial_path: str | None = None,
        theme: Theme = DEFAULT_THEME,
    ):
        super().__init__(parent)

        self._parent = parent
        self._theme = theme
        self._model = model
        self._result: tuple[str, str] | None = None

        self.withdraw()  # evita el parpadeo de un Toplevel a medio construir
        self.title(title)
        self.geometry(f"{DIALOG_WIDTH}x{DIALOG_HEIGHT}")
        self.minsize(560, 420)
        self.configure(fg_color=theme.pair("window"))
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Elige la carpeta de destino",
            font=theme.font(18, "bold"),
            text_color=theme.pair("text"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Se guardará la ruta lógica de la carpeta, no su id.",
            font=theme.font(11),
            text_color=theme.pair("muted"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        panel = ctk.CTkFrame(
            self,
            fg_color=theme.pair("panel"),
            border_color=theme.pair("border"),
            border_width=1,
            corner_radius=10,
        )
        panel.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=1)

        self.explorer = FolderExplorer(
            panel,
            model,
            theme=theme,
            height=16,
            async_load=False,
            show_label=False,
            on_select=self._on_select,
        )
        self.explorer.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.explorer.tree.bind("<Double-Button-1>", self._on_double_click)
        self.explorer.tree.bind("<Return>", lambda _event: self._accept())

        self._path_label = ctk.CTkLabel(
            self,
            text="Selección: (ninguna)",
            font=theme.font(11),
            text_color=theme.pair("muted"),
            anchor="w",
            justify="left",
            wraplength=DIALOG_WIDTH - 60,
        )
        self._path_label.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 0))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=18, pady=(8, 16))
        footer.grid_columnconfigure(0, weight=1)

        self._message_label = ctk.CTkLabel(
            footer,
            text="",
            font=theme.font(11),
            text_color=theme.pair("danger"),
            anchor="w",
        )
        self._message_label.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            footer,
            text="Cancelar",
            width=110,
            command=self._cancel,
            fg_color=theme.pair("panel_alt"),
            hover_color=theme.pair("border"),
            text_color=theme.pair("text"),
        ).grid(row=0, column=1, padx=(8, 0))

        self._accept_button = ctk.CTkButton(
            footer,
            text="Seleccionar",
            width=120,
            command=self._accept,
            fg_color=theme.pair("accent"),
            hover_color=theme.pair("accent_hover"),
            text_color=theme.pair("accent_text"),
        )
        self._accept_button.grid(row=0, column=2, padx=(8, 0))

        self._preselect(initial_path)

    # -- API pública -------------------------------------------------------
    @property
    def result(self) -> tuple[str, str] | None:
        """``(id, ruta)`` elegido, o ``None`` si se canceló."""
        return self._result

    def show(self) -> tuple[str, str] | None:
        """Muestra el modal de forma bloqueante y devuelve la selección."""
        self.deiconify()
        self.update_idletasks()
        self._center()
        self.transient(self._parent)
        self.grab_set()
        self.focus_force()
        self.explorer.tree.focus_set()
        self.wait_window()
        return self._result

    # -- selección ---------------------------------------------------------
    def _preselect(self, initial_path: str | None) -> None:
        """Intenta abrir el modal en la carpeta guardada."""
        revealed = False
        if initial_path:
            try:
                node = self._model.resolve_path(initial_path)
            except AmbiguousPathError as exc:
                self._message_label.configure(text=str(exc))
                node = None
            if node is not None:
                revealed = self.explorer.reveal(node.id)
        if not revealed:
            self.explorer.select_root()
        self._refresh_path_label()

    def _refresh_path_label(self) -> None:
        path = self.explorer.selected_path()
        if path is None:
            self._path_label.configure(text="Selección: (ninguna)")
        else:
            self._path_label.configure(text=f"Selección: {path}")

    def _on_select(self, _node) -> None:
        self._message_label.configure(text="")
        self._refresh_path_label()

    def _on_double_click(self, event: tk.Event) -> None:
        """Doble clic sobre el texto de una fila: seleccionar y cerrar."""
        element = self.explorer.tree.identify("element", event.x, event.y)
        if str(element).endswith("indicator"):
            return  # el doble clic sobre la flecha solo expande
        if self.explorer.tree.identify_row(event.y):
            self._accept()

    # -- acciones ----------------------------------------------------------
    def _accept(self) -> None:
        node = self.explorer.selected_node()
        if node is None:
            self._message_label.configure(text="Selecciona una carpeta de la lista.")
            return
        self._result = (node.id, self._model.path_of(node.id))
        self.destroy()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()

    # -- geometría ---------------------------------------------------------
    def _center(self) -> None:
        """Centra el modal sobre la ventana padre, sin salirse de la pantalla.

        Se usan los tamaños reales del widget (ya escalados por DPI) y se mueve
        la ventana con una geometría solo-posición, que CTk no vuelve a escalar.
        """
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            width, height = DIALOG_WIDTH, DIALOG_HEIGHT

        parent_width = self._parent.winfo_width()
        parent_height = self._parent.winfo_height()
        if parent_width <= 1 or parent_height <= 1:
            parent_width, parent_height = 1100, 720

        x = self._parent.winfo_rootx() + (parent_width - width) // 2
        y = self._parent.winfo_rooty() + (parent_height - height) // 2
        x = max(0, min(x, self.winfo_screenwidth() - width))
        y = max(0, min(y, self.winfo_screenheight() - height))
        self.geometry(f"+{x}+{y}")


def pick_folder(
    parent,
    model: FolderTreeModel | None,
    *,
    initial_path: str | None = None,
    title: str = "Seleccionar carpeta",
    theme: Theme = DEFAULT_THEME,
) -> tuple[str, str] | None:
    """Abre el modal y devuelve la carpeta elegida (o ``None``)."""
    if model is None:
        return None
    dialog = FolderPickerDialog(
        parent,
        model,
        title=title,
        initial_path=initial_path,
        theme=theme,
    )
    return dialog.show()
