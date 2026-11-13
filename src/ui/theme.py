"""Tema visual de la aplicación (CustomTkinter + ttk.Treeview).

Decisiones tomadas en fase de pruebas:

- El tema ttk ``clam`` es el único que respeta los colores configurados del
  ``Treeview`` en Windows; ``vista`` ignora la cabecera y deja en blanco el
  campo vacío bajo la última fila.
- La fuente por defecto de CustomTkinter es Roboto, que no está instalada en
  Windows: se usa Segoe UI explícita.
- Los colores que reciben los widgets de CustomTkinter se pasan como pares
  (claro, oscuro) para que el cambio de modo sea automático.
"""

from __future__ import annotations

import customtkinter as ctk
from tkinter import ttk

FONT_FAMILY = "Segoe UI"

#: Estilo ttk que usan todas las tablas y árboles de la aplicación.
TREE_STYLE = "Organizador.Treeview"

#: Altura de fila de las tablas, en píxeles (medida en la fase de pruebas).
ROW_HEIGHT = 34

#: Tamaño inicial y mínimo de la ventana principal. El tamaño inicial se
#: recorta al espacio disponible de la pantalla al construir la ventana.
WINDOW_WIDTH = 1120
WINDOW_HEIGHT = 820
WINDOW_MIN_SIZE = (960, 640)

#: Paletas por modo. Las claves se comparten entre ambos modos.
LIGHT: dict[str, str] = {
    "window": "#f2f2f5",
    "panel": "#ffffff",
    "panel_alt": "#ededf1",
    "border": "#d8d8de",
    "text": "#1a1a20",
    "muted": "#5f5f6b",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "accent_text": "#ffffff",
    "success": "#15803d",
    "danger": "#b91c1c",
    "warning": "#b45309",
    "tree_bg": "#ffffff",
    "tree_fg": "#1a1a20",
    "tree_selection_bg": "#cfe3fb",
    "tree_selection_fg": "#0f172a",
    "tree_heading_bg": "#ededf1",
    "tree_heading_fg": "#33333a",
}

DARK: dict[str, str] = {
    "window": "#1a1a1e",
    "panel": "#232327",
    "panel_alt": "#2b2b31",
    "border": "#38383f",
    "text": "#f0f0f2",
    "muted": "#a0a0ab",
    "accent": "#2f6fed",
    "accent_hover": "#1d4ed8",
    "accent_text": "#ffffff",
    "success": "#34d399",
    "danger": "#f87171",
    "warning": "#fbbf24",
    "tree_bg": "#232327",
    "tree_fg": "#e8e8ec",
    "tree_selection_bg": "#2f5d8a",
    "tree_selection_fg": "#ffffff",
    "tree_heading_bg": "#2b2b31",
    "tree_heading_fg": "#cfcfd6",
}


class Theme:
    """Paleta y estilos de la aplicación.

    El objeto no toca Tk hasta que se llama a ``apply()``, que debe ejecutarse
    cuando ya existe una ventana raíz.
    """

    def __init__(self, mode: str = "dark"):
        self._mode = mode if mode in ("dark", "light") else "dark"

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_dark(self) -> bool:
        return self._mode == "dark"

    def set_mode(self, mode: str) -> None:
        """Cambia el modo de apariencia (``"dark"`` o ``"light"``)."""
        if mode not in ("dark", "light"):
            raise ValueError(f"Modo de apariencia desconocido: {mode!r}")
        self._mode = mode

    def toggle(self) -> str:
        """Alterna entre claro y oscuro y devuelve el modo resultante."""
        self.set_mode("light" if self.is_dark else "dark")
        return self._mode

    # -- colores -----------------------------------------------------------
    def color(self, key: str) -> str:
        """Color concreto del modo actual (para ttk y canvas)."""
        palette = DARK if self.is_dark else LIGHT
        return palette[key]

    def pair(self, key: str) -> tuple[str, str]:
        """Par (claro, oscuro) para los widgets de CustomTkinter."""
        return (LIGHT[key], DARK[key])

    # -- tipografía --------------------------------------------------------
    def font(self, size: int = 12, weight: str = "normal") -> ctk.CTkFont:
        """Fuente para un widget de CustomTkinter."""
        return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)

    @staticmethod
    def tk_font(size: int = 10, weight: str = "normal") -> tuple[str, int, str]:
        """Fuente para un widget ttk (no admite CTkFont)."""
        return (FONT_FAMILY, size, weight)

    # -- aplicación --------------------------------------------------------
    def apply(self) -> None:
        """Aplica el modo a CustomTkinter y reinstala el estilo del árbol."""
        ctk.set_appearance_mode(self._mode)
        self.apply_ttk()

    def apply_ttk(self) -> None:
        """Configura el tema ``clam`` y el estilo de tablas y árboles.

        Se puede llamar varias veces (por ejemplo, al cambiar de modo): ttk
        vuelve a pintar todos los widgets que usan ``TREE_STYLE``.
        """
        style = ttk.Style()
        style.theme_use("clam")

        background = self.color("tree_bg")
        foreground = self.color("tree_fg")
        selection_bg = self.color("tree_selection_bg")
        selection_fg = self.color("tree_selection_fg")

        style.configure(
            TREE_STYLE,
            background=background,
            fieldbackground=background,
            foreground=foreground,
            bordercolor=background,
            lightcolor=background,
            darkcolor=background,
            borderwidth=0,
            relief="flat",
            rowheight=ROW_HEIGHT,
            font=self.tk_font(10),
        )
        style.map(
            TREE_STYLE,
            background=[("selected", selection_bg)],
            foreground=[("selected", selection_fg)],
        )
        style.configure(
            f"{TREE_STYLE}.Heading",
            background=self.color("tree_heading_bg"),
            foreground=self.color("tree_heading_fg"),
            bordercolor=self.color("border"),
            lightcolor=self.color("tree_heading_bg"),
            darkcolor=self.color("tree_heading_bg"),
            relief="flat",
            borderwidth=0,
            padding=(10, 8),
            font=self.tk_font(10, "bold"),
        )
        style.map(
            f"{TREE_STYLE}.Heading",
            background=[("active", self.color("tree_heading_bg"))],
            foreground=[("active", self.color("tree_heading_fg"))],
        )


#: Tema compartido por toda la aplicación. La ventana principal lo actualiza
#: al cambiar de modo y el resto de widgets leen de aquí sus colores.
DEFAULT_THEME = Theme()
