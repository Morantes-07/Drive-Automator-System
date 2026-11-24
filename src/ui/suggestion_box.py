"""Desplegable de sugerencias de placeholders para el campo de patrón.

El widget solo se ocupa del contenido y de la selección. La pestaña decide
cuándo mostrarlo y en qué posición colocarlo.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from src.patterns.placeholders import PLACEHOLDER_INFOS, PlaceholderInfo
from src.patterns.suggestions import move_selection as next_selection

from .theme import DEFAULT_THEME, Theme

PickCallback = Callable[[PlaceholderInfo], None]


class PlaceholderSuggestionBox(ctk.CTkFrame):
    """Lista de placeholders que coincide con el texto escrito tras ``{``.

    Args:
        master: Widget contenedor; normalmente la tarjeta del formulario.
        theme: Tema compartido de la aplicación.
        on_pick: Se llama con el placeholder elegido por clic o teclado.
    """

    def __init__(
        self,
        master,
        *,
        theme: Theme = DEFAULT_THEME,
        on_pick: PickCallback | None = None,
    ):
        super().__init__(
            master,
            fg_color=theme.pair("panel"),
            border_color=theme.pair("border"),
            border_width=1,
            corner_radius=10,
        )
        self._theme = theme
        self._on_pick = on_pick
        self._items: list[PlaceholderInfo] = []
        self._rows: dict[str, ctk.CTkFrame] = {}
        self._selected = 0
        self._visible = False

        self._build_rows()

    # -- API pública -------------------------------------------------------
    @property
    def is_visible(self) -> bool:
        """Indica si la lista está desplegada."""
        return self._visible

    @property
    def items(self) -> tuple[PlaceholderInfo, ...]:
        """Placeholders que se están mostrando."""
        return tuple(self._items)

    @property
    def selected_index(self) -> int:
        """Índice de la fila resaltada."""
        return self._selected

    def show(self, items: list[PlaceholderInfo]) -> None:
        """Muestra las sugerencias indicadas, o se oculta si no hay ninguna."""
        if not items:
            self.hide()
            return

        self._items = list(items)
        self._selected = 0
        self._visible = True
        for row in self._rows.values():
            row.pack_forget()
        for item in self._items:
            self._rows[item.key].pack(fill="x", padx=6, pady=2)
        self._apply_highlight()
        self.lift()

    def hide(self) -> None:
        """Oculta la lista y limpia el estado de selección."""
        self._visible = False
        self._items = []
        self._selected = 0
        self.place_forget()

    def move_selection(self, delta: int) -> None:
        """Mueve la fila resaltada sin salirse de los límites."""
        if not self._visible:
            return
        self._selected = next_selection(
            self._selected, delta, len(self._items)
        )
        self._apply_highlight()

    def accept(self) -> None:
        """Acepta la fila resaltada y avisa por ``on_pick``."""
        if not self._visible or not self._items:
            return
        item = self._items[self._selected]
        self.hide()
        if self._on_pick is not None:
            self._on_pick(item)

    # -- construcción ------------------------------------------------------
    def _build_rows(self) -> None:
        for info in PLACEHOLDER_INFOS:
            row = ctk.CTkFrame(self, fg_color="transparent", corner_radius=6)
            label = ctk.CTkLabel(
                row,
                text=info.label,
                font=self._theme.font(11, "bold"),
                text_color=self._theme.pair("accent"),
                anchor="w",
            )
            label.pack(side="left", padx=(10, 8), pady=4)

            description = ctk.CTkLabel(
                row,
                text=info.description,
                font=self._theme.font(11),
                text_color=self._theme.pair("muted"),
                anchor="w",
            )
            description.pack(side="left", padx=(0, 10), pady=4)

            for widget in (row, label, description):
                widget.bind(
                    "<ButtonPress-1>",
                    lambda _event, item=info: self._pick(item),
                )
                widget.bind(
                    "<Enter>",
                    lambda _event, item=info: self._hover(item),
                )
            self._rows[info.key] = row

    # -- eventos -----------------------------------------------------------
    def _hover(self, item: PlaceholderInfo) -> None:
        if not self._visible:
            return
        try:
            self._selected = self._items.index(item)
        except ValueError:
            return
        self._apply_highlight()

    def _pick(self, item: PlaceholderInfo) -> None:
        if not self._visible:
            return
        self.hide()
        if self._on_pick is not None:
            self._on_pick(item)

    def _apply_highlight(self) -> None:
        for index, item in enumerate(self._items):
            self._rows[item.key].configure(
                fg_color=(
                    self._theme.pair("panel_alt")
                    if index == self._selected
                    else "transparent"
                )
            )
