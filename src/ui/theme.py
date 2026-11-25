"""Tema visual de la aplicación (CustomTkinter + ttk.Treeview).

Decisiones tomadas en fase de pruebas:

- El tema ttk ``clam`` es el único que respeta los colores configurados del
  ``Treeview`` en Windows; ``vista`` ignora la cabecera y deja en blanco el
  campo vacío bajo la última fila.
- La fuente por defecto de CustomTkinter es Roboto, que no está instalada en
  Windows: se usa Segoe UI explícita.
- La aplicación usa una sola paleta, así que los widgets reciben un color
  directo en lugar del par de colores que acepta CustomTkinter.
"""

from __future__ import annotations

import customtkinter as ctk
from tkinter import ttk

FONT_FAMILY = "Segoe UI"

#: Puntos que se suman a todos los tamaños de fuente de la aplicación.
FONT_SIZE_OFFSET = 2

#: Tamaño que CustomTkinter usa cuando un widget no recibe ``font``.
DEFAULT_FONT_SIZE = ctk.ThemeManager.theme["CTkFont"]["size"]

#: Estilo ttk que usan todas las tablas y árboles de la aplicación.
TREE_STYLE = "Organizador.Treeview"

#: Altura de fila de las tablas, en píxeles (medida en la fase de pruebas).
ROW_HEIGHT = 34

#: Tamaño inicial y mínimo de la ventana principal. El tamaño inicial se
#: recorta al espacio disponible de la pantalla al construir la ventana.
WINDOW_WIDTH = 1120
WINDOW_HEIGHT = 820
WINDOW_MIN_SIZE = (960, 640)

#: Única paleta de colores de la aplicación (modo oscuro).
PALETTE: dict[str, str] = {
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

    # -- colores -----------------------------------------------------------
    def color(self, key: str) -> str:
        """Color de la paleta oscura (para widgets, ttk y canvas)."""
        return PALETTE[key]

    # -- tipografía --------------------------------------------------------
    def font(self, size: int = 12, weight: str = "normal") -> ctk.CTkFont:
        """Fuente para un widget de CustomTkinter."""
        return ctk.CTkFont(
            family=FONT_FAMILY,
            size=size + FONT_SIZE_OFFSET,
            weight=weight,
        )

    @staticmethod
    def tk_font(size: int = 10, weight: str = "normal") -> tuple[str, int, str]:
        """Fuente para un widget ttk (no admite CTkFont)."""
        return (FONT_FAMILY, size + FONT_SIZE_OFFSET, weight)

    # -- aplicación --------------------------------------------------------
    def apply(self) -> None:
        """Fija el modo oscuro en CustomTkinter e instala el estilo del árbol."""
        ctk.set_appearance_mode("dark")
        # Los widgets que no reciben ``font`` usan el tamaño por defecto de
        # CustomTkinter; también se les suma el desplazamiento global.
        ctk.ThemeManager.theme["CTkFont"]["size"] = (
            DEFAULT_FONT_SIZE + FONT_SIZE_OFFSET
        )
        self.apply_ttk()

    def apply_ttk(self) -> None:
        """Configura el tema ``clam`` y el estilo de tablas y árboles."""
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


#: Tema compartido por toda la aplicación. La ventana principal lo aplica al
#: construirse y el resto de widgets leen de aquí sus colores.
DEFAULT_THEME = Theme()
