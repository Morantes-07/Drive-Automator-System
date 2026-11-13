"""Explorador de carpetas con carga diferida sobre un ``ttk.Treeview``.

Patrón validado en la fase de pruebas (``sandbox/ui_spike``):

- La carga se dispara con ``<<TreeviewOpen>>``. Ese evento no trae
  coordenadas, así que el nodo abierto se identifica con ``tree.focus()`` y un
  binding propio de ``<Button-1>`` se encarga de asignar el foco a la fila
  pulsada.
- Cada nodo con hijos nace con un hijo "placeholder" para que se dibuje la
  flecha. Al expandirlo se insertan los hijos reales en lote y después se
  borra el placeholder.
- Los nodos sin hijos no llevan placeholder, de modo que nunca muestran flecha.
- El trabajo pesado se hace en un hilo y el resultado se aplica en el hilo
  principal con ``after(0, ...)``. El nodo se marca como "en vuelo" en el hilo
  principal antes de lanzar el hilo, para que dos expansiones rápidas no
  disparen dos cargas.
"""

from __future__ import annotations

import threading
import tkinter as tk
from typing import Callable

import customtkinter as ctk
from tkinter import ttk

from src.drive.folder_tree import FolderNode, FolderTreeModel

from .theme import DEFAULT_THEME, TREE_STYLE, Theme

#: Sufijo de los identificadores internos de los placeholders.
PLACEHOLDER_SUFFIX = "::__ph__"

#: Identificador de la fila que se muestra cuando no hay modelo.
EMPTY_IID = "__sin_drive__"

#: Prefijo de todos los identificadores internos (nunca son ids de Drive).
INTERNAL_PREFIX = "__"

#: Icono de carpeta. S8 comprobó que se dibuja en Windows con Tk 9, aunque
#: GDI lo pinta en monocromo (no soporta fuentes de emoji en color).
FOLDER_ICON = "\U0001F4C1"

SelectionCallback = Callable[[FolderNode | None], None]
ErrorCallback = Callable[[str], None]


class FolderExplorer(ctk.CTkFrame):
    """Árbol de carpetas de Drive con expansión y carga diferida.

    Args:
        master: Widget contenedor.
        model: Árbol de carpetas; puede ser ``None`` mientras no hay conexión.
        theme: Tema compartido de la aplicación.
        on_select: Se llama con la carpeta seleccionada (o al limpiar la
            selección, con ``None``).
        on_error: Se llama con un mensaje legible si falla una carga.
        height: Altura inicial del árbol, en filas.
        async_load: Si es ``True``, los hijos se cargan en un hilo. Con
            ``False`` se cargan de forma síncrona (útil en pruebas).
        show_label: Si es ``True``, muestra una cabecera con el nombre y el
            número de carpetas.
        label_text: Texto de la cabecera.
    """

    def __init__(
        self,
        master,
        model: FolderTreeModel | None = None,
        *,
        theme: Theme = DEFAULT_THEME,
        on_select: SelectionCallback | None = None,
        on_error: ErrorCallback | None = None,
        height: int = 14,
        async_load: bool = True,
        show_label: bool = True,
        label_text: str = "Carpetas de Drive",
    ):
        super().__init__(master, fg_color="transparent")

        self._model = model
        self._theme = theme
        self._on_select = on_select
        self._on_error = on_error
        self._async_load = async_load

        self._loaded: set[str] = set()
        self._loading: set[str] = set()
        self._generation = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1 if show_label else 0, weight=1)

        if show_label:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
            header.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                header,
                text=label_text,
                font=self._theme.font(12, "bold"),
                text_color=self._theme.pair("text"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            self._count_label = ctk.CTkLabel(
                header,
                text="",
                font=self._theme.font(11),
                text_color=self._theme.pair("muted"),
                anchor="e",
            )
            self._count_label.grid(row=0, column=1, sticky="e")
        else:
            self._count_label = None

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(
            row=1 if show_label else 0,
            column=0,
            sticky="nsew",
        )
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            body,
            columns=(),
            show="tree",
            selectmode="browse",
            style=TREE_STYLE,
            height=height,
        )
        self.tree.column("#0", width=360, minwidth=180, stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew")

        self.scrollbar = ctk.CTkScrollbar(body, command=self.tree.yview, width=12)
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        self.tree.bind("<<TreeviewOpen>>", self._on_open)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_event)
        self.tree.bind("<Button-1>", self._on_click)

        self._reset()

    # -- API pública -------------------------------------------------------
    @property
    def model(self) -> FolderTreeModel | None:
        """Modelo que está mostrando el explorador."""
        return self._model

    def set_model(self, model: FolderTreeModel | None) -> None:
        """Cambia el árbol de carpetas y reconstruye la vista."""
        self._model = model
        self._reset()

    def refresh(self) -> None:
        """Vuelve a construir la vista con el modelo actual."""
        self._reset()

    def apply_theme(self) -> None:
        """Reaplica el color de los elementos auxiliares tras cambiar de modo."""
        self.tree.configure(style=TREE_STYLE)

    def selected_node(self) -> FolderNode | None:
        """Carpeta seleccionada, o None si no hay selección válida."""
        selection = self.tree.selection()
        if not selection:
            return None
        folder_id = selection[0]
        if folder_id.startswith(INTERNAL_PREFIX) or self._model is None:
            return None
        return self._model.get(folder_id)

    def selected_path(self) -> str | None:
        """Ruta lógica de la carpeta seleccionada, o None."""
        node = self.selected_node()
        if node is None or self._model is None:
            return None
        return self._model.path_of(node.id)

    def select_root(self) -> None:
        """Selecciona la carpeta raíz."""
        if self._model is None:
            return
        root_id = self._model.root_id
        if self.tree.exists(root_id):
            self.tree.selection_set(root_id)
            self.tree.focus(root_id)
            self.tree.see(root_id)

    def reveal(self, folder_id: str) -> bool:
        """Expande los ancestros y selecciona la carpeta indicada.

        La carga se hace de forma síncrona porque el modelo ya está en memoria;
        así el modal puede abrirse directamente en la carpeta guardada.

        Returns:
            ``True`` si la carpeta quedó visible y seleccionada.
        """
        if self._model is None or folder_id not in self._model:
            return False

        # Cadena de ancestros desde la raíz hasta el padre de la carpeta.
        chain: list[str] = []
        visited = {folder_id}
        current = self._model.get(folder_id)
        while current is not None and current.id != self._model.root_id:
            parent = self._model.parent_of(current.id)
            if parent is None or parent.id in visited:
                break
            visited.add(parent.id)
            chain.append(parent.id)
            current = parent

        for ancestor_id in reversed(chain):
            self._fill(ancestor_id)
            if self.tree.exists(ancestor_id):
                self.tree.item(ancestor_id, open=True)

        if not self.tree.exists(folder_id):
            return False
        self.tree.selection_set(folder_id)
        self.tree.focus(folder_id)
        self.tree.see(folder_id)
        return True

    # -- construcción de la vista -----------------------------------------
    def _reset(self) -> None:
        """Vacía el árbol y lo reconstruye desde la raíz."""
        self._generation += 1
        self._loaded.clear()
        self._loading.clear()

        children = self.tree.get_children("")
        if children:
            self.tree.delete(*children)

        if self._model is None:
            self.tree.insert(
                "",
                "end",
                iid=EMPTY_IID,
                text="Sin conexión con Drive",
            )
            self._update_count()
            return

        root = self._model.root
        self.tree.insert("", "end", iid=root.id, text=self._display_name(root), open=True)
        self._add_placeholder(root.id)
        self._update_count()

        if self._async_load:
            self._request_load(root.id)
        else:
            self._fill(root.id)

    def _update_count(self) -> None:
        if self._count_label is None:
            return
        if self._model is None:
            self._count_label.configure(text="—")
        else:
            total = len(self._model)
            self._count_label.configure(text=f"{total} carpetas")

    @staticmethod
    def _display_name(node: FolderNode) -> str:
        return f"{FOLDER_ICON}  {node.name}"

    def _placeholder_id(self, folder_id: str) -> str:
        return f"{folder_id}{PLACEHOLDER_SUFFIX}"

    def _add_placeholder(self, folder_id: str) -> None:
        """Añade el hijo vacío que dibuja la flecha, si la carpeta tiene hijos."""
        if self._model is None or not self._model.has_children(folder_id):
            return
        placeholder = self._placeholder_id(folder_id)
        if not self.tree.exists(placeholder):
            self.tree.insert(folder_id, "end", iid=placeholder, text="")

    def _remove_placeholder(self, folder_id: str) -> None:
        placeholder = self._placeholder_id(folder_id)
        if self.tree.exists(placeholder):
            self.tree.delete(placeholder)

    def _fill(
        self,
        folder_id: str,
        children: tuple[FolderNode, ...] | None = None,
    ) -> None:
        """Inserta los hijos reales de un nodo (siempre en el hilo principal)."""
        if not self._exists():
            return
        if folder_id in self._loaded or not self.tree.exists(folder_id):
            return
        if children is None:
            children = self._model.children_of(folder_id) if self._model else ()

        self._remove_placeholder(folder_id)
        # Los hijos se insertan en lote: trocear la inserción es mucho más
        # lento (S5) y aquí no aporta nada.
        for child in children:
            if not self.tree.exists(child.id):
                self.tree.insert(
                    folder_id,
                    "end",
                    iid=child.id,
                    text=self._display_name(child),
                )
                self._add_placeholder(child.id)

        self._loaded.add(folder_id)
        self._loading.discard(folder_id)

    # -- eventos -----------------------------------------------------------
    def _on_click(self, event: tk.Event) -> None:
        """Asigna el foco a la fila pulsada antes de que ttk la expanda."""
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.focus(row)

    def _on_open(self, _event: tk.Event) -> None:
        """Carga el nodo que se acaba de expandir."""
        self._request_load(self.tree.focus())

    def _request_load(self, folder_id: str) -> None:
        """Pide la carga de un nodo (o la hace al momento si es síncrona)."""
        if not folder_id:
            return
        if folder_id.startswith(INTERNAL_PREFIX):
            return
        if self._model is None:
            return
        if folder_id in self._loaded or folder_id in self._loading:
            return
        if not self._model.has_children(folder_id):
            self._loaded.add(folder_id)
            return

        if not self._async_load:
            self._fill(folder_id)
            return

        # El marcado se hace en el hilo principal, antes de lanzar el hilo.
        self._loading.add(folder_id)
        generation = self._generation
        threading.Thread(
            target=self._load_worker,
            args=(folder_id, generation),
            daemon=True,
        ).start()

    def _on_select_event(self, _event: tk.Event) -> None:
        selection = self.tree.selection()
        if selection and selection[0].startswith(INTERNAL_PREFIX):
            self.tree.selection_remove(selection[0])
            return
        if self._on_select is not None:
            self._on_select(self.selected_node())

    # -- hilo --------------------------------------------------------------
    def _load_worker(self, folder_id: str, generation: int) -> None:
        """Lee los hijos en segundo plano; nunca toca la interfaz."""
        try:
            children = self._model.children_of(folder_id) if self._model else ()
        except Exception as exc:  # pragma: no cover - defensivo
            self._schedule(self._apply_error, folder_id, generation, exc)
            return
        self._schedule(self._apply_children, folder_id, generation, children)

    def _schedule(self, callback, *args) -> None:
        """Encola una actualización en el hilo principal.

        Si la ventana ya se cerró, ``after`` falla y el resultado se descarta.
        """
        try:
            self.after(0, callback, *args)
        except Exception:
            pass

    def _apply_children(
        self,
        folder_id: str,
        generation: int,
        children: tuple[FolderNode, ...],
    ) -> None:
        if generation != self._generation:
            return
        self._loading.discard(folder_id)
        if not self._exists():
            return
        self._fill(folder_id, children)

    def _apply_error(
        self,
        folder_id: str,
        generation: int,
        exc: Exception,
    ) -> None:
        if generation != self._generation:
            return
        self._loading.discard(folder_id)
        if not self._exists():
            return
        if self._on_error is not None:
            self._on_error(f"No se pudieron cargar las carpetas: {exc}")

    def _exists(self) -> bool:
        """Comprueba que el widget siga vivo (el hilo puede llegar tarde)."""
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False
