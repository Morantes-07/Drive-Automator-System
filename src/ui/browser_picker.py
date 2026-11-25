"""Modal para elegir el navegador que abrirá la autorización de Google.

El modal se puede invocar desde el hilo principal o desde un hilo de trabajo.
En el segundo caso se programa con ``after`` y se espera el resultado con un
``Event``: Tkinter no debe manipularse fuera del hilo principal.
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from src.authentication.browsers import (
    SYSTEM_DEFAULT,
    BrowserOption,
    browser_choices,
)

from .theme import DEFAULT_THEME, Theme

#: Tamaño del modal, en píxeles.
DIALOG_WIDTH = 600
DIALOG_HEIGHT = 480

#: Claves internas para el ``StringVar`` de las opciones.
DEFAULT_KEY = "__default__"
CUSTOM_KEY = "__custom__"


def _option_key(option: BrowserOption) -> str:
    """Clave única de una opción dentro del modal."""
    return option.executable or DEFAULT_KEY


class BrowserPickerDialog(ctk.CTkToplevel):
    """Ventana modal que devuelve el navegador elegido.

    Args:
        parent: Ventana sobre la que se centra y a la que bloquea.
        options: Opciones que se muestran; normalmente ``browser_choices()``.
        theme: Tema compartido de la aplicación.
    """

    def __init__(
        self,
        parent,
        options: list[BrowserOption],
        *,
        theme: Theme = DEFAULT_THEME,
    ):
        super().__init__(parent)

        self._parent = parent
        self._theme = theme
        self._options_by_key = {_option_key(option): option for option in options}
        self._custom_option: BrowserOption | None = None
        self._result: BrowserOption | None = None
        self._last_key = next(iter(self._options_by_key), DEFAULT_KEY)
        self._selected = tk.StringVar(master=self, value=self._last_key)

        self.withdraw()  # evita el parpadeo de un Toplevel a medio construir
        self.title("Elegir navegador")
        self.geometry(f"{DIALOG_WIDTH}x{DIALOG_HEIGHT}")
        self.minsize(500, 380)
        self.configure(fg_color=theme.pair("window"))
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_options(options)
        self._build_path_label()
        self._build_footer()
        self._refresh_path_label()

    # -- construcción de la interfaz --------------------------------------
    def _build_header(self) -> None:
        theme = self._theme
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Elige el navegador para iniciar sesión",
            font=theme.font(18, "bold"),
            text_color=theme.pair("text"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text=(
                "Se necesita generar un token nuevo. El navegador elegido se "
                "abrirá para autorizar la cuenta de Google."
            ),
            font=theme.font(11),
            text_color=theme.pair("muted"),
            anchor="w",
            justify="left",
            wraplength=DIALOG_WIDTH - 60,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _build_options(self, options: list[BrowserOption]) -> None:
        theme = self._theme
        panel = ctk.CTkScrollableFrame(
            self,
            fg_color=theme.pair("panel"),
            border_color=theme.pair("border"),
            border_width=1,
            corner_radius=10,
        )
        panel.grid(row=1, column=0, sticky="nsew", padx=18, pady=4)
        panel.grid_columnconfigure(0, weight=1)

        for index, option in enumerate(options):
            self._build_option(panel, index, option)

        next_row = len(options)
        self._custom_radio = ctk.CTkRadioButton(
            panel,
            text="Otro navegador…",
            variable=self._selected,
            value=CUSTOM_KEY,
            command=self._on_radio_change,
            font=theme.font(12),
            text_color=theme.pair("text"),
            fg_color=theme.pair("accent"),
            hover_color=theme.pair("accent_hover"),
        )
        self._custom_radio.grid(
            row=next_row * 2,
            column=0,
            sticky="w",
            padx=12,
            pady=(12, 0),
        )

        ctk.CTkButton(
            panel,
            text="Examinar…",
            width=110,
            command=self._choose_custom,
            fg_color=theme.pair("panel_alt"),
            hover_color=theme.pair("border"),
            border_width=1,
            border_color=theme.pair("border"),
            text_color=theme.pair("text"),
        ).grid(
            row=next_row * 2 + 1,
            column=0,
            sticky="w",
            padx=(42, 12),
            pady=(4, 12),
        )

    def _build_option(
        self, parent, index: int, option: BrowserOption
    ) -> None:
        theme = self._theme
        ctk.CTkRadioButton(
            parent,
            text=option.name,
            variable=self._selected,
            value=_option_key(option),
            command=self._on_radio_change,
            font=theme.font(12),
            text_color=theme.pair("text"),
            fg_color=theme.pair("accent"),
            hover_color=theme.pair("accent_hover"),
        ).grid(
            row=index * 2,
            column=0,
            sticky="w",
            padx=12,
            pady=(8, 0),
        )

        detail = (
            "Se usará el navegador configurado en Windows."
            if option.executable is None
            else option.executable
        )
        ctk.CTkLabel(
            parent,
            text=detail,
            font=theme.font(10),
            text_color=theme.pair("muted"),
            anchor="w",
            justify="left",
            wraplength=DIALOG_WIDTH - 100,
        ).grid(
            row=index * 2 + 1,
            column=0,
            sticky="w",
            padx=(42, 12),
            pady=(2, 0),
        )

    def _build_path_label(self) -> None:
        self._path_label = ctk.CTkLabel(
            self,
            text="",
            font=self._theme.font(10),
            text_color=self._theme.pair("muted"),
            anchor="w",
            justify="left",
            wraplength=DIALOG_WIDTH - 60,
        )
        self._path_label.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 0))

    def _build_footer(self) -> None:
        theme = self._theme
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 16))
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

        ctk.CTkButton(
            footer,
            text="Continuar",
            width=120,
            command=self._accept,
            fg_color=theme.pair("accent"),
            hover_color=theme.pair("accent_hover"),
            text_color=theme.pair("accent_text"),
        ).grid(row=0, column=2, padx=(8, 0))

    # -- API pública -------------------------------------------------------
    @property
    def result(self) -> BrowserOption | None:
        """Navegador elegido, o ``None`` si se canceló."""
        return self._result

    def show(self) -> BrowserOption | None:
        """Muestra el modal de forma bloqueante y devuelve la selección."""
        self.deiconify()
        self.update_idletasks()
        self._center()
        self.transient(self._parent)
        self.grab_set()
        self.focus_force()
        self.wait_window()
        return self._result

    # -- selección ---------------------------------------------------------
    def _on_radio_change(self) -> None:
        key = self._selected.get()
        if key == CUSTOM_KEY and self._custom_option is None:
            self._choose_custom()
            return
        self._last_key = key
        self._message_label.configure(text="")
        self._refresh_path_label()

    def _choose_custom(self) -> None:
        """Abre el selector de archivos para elegir un navegador concreto."""
        path = filedialog.askopenfilename(
            parent=self,
            title="Elegir navegador",
            filetypes=[("Ejecutables de Windows", "*.exe")],
        )
        if not path:
            self._restore_selection()
            return

        candidate = Path(path)
        try:
            is_file = candidate.is_file()
        except OSError:
            is_file = False

        if not is_file or candidate.suffix.casefold() != ".exe":
            self._message_label.configure(
                text="Selecciona un archivo .exe válido."
            )
            self._restore_selection()
            return

        self._custom_option = BrowserOption(
            "Navegador personalizado", str(candidate)
        )
        self._options_by_key[CUSTOM_KEY] = self._custom_option
        self._custom_radio.configure(text=f"Otro: {candidate.name}")
        self._selected.set(CUSTOM_KEY)
        self._last_key = CUSTOM_KEY
        self._message_label.configure(text="")
        self._refresh_path_label()

    def _restore_selection(self) -> None:
        """Vuelve a la última opción válida si se cancela el explorador."""
        if self._selected.get() == CUSTOM_KEY and self._custom_option is None:
            self._selected.set(self._last_key)
        self._refresh_path_label()

    def _refresh_path_label(self) -> None:
        option = self._options_by_key.get(self._selected.get())
        if option is None:
            text = "Selecciona un ejecutable."
        elif option.executable is None:
            text = "Se usará el navegador configurado en Windows."
        else:
            text = f"Ruta: {option.executable}"
        self._path_label.configure(text=text)

    # -- acciones ----------------------------------------------------------
    def _accept(self) -> None:
        option = self._options_by_key.get(self._selected.get())
        if option is None:
            self._message_label.configure(
                text="Elige un navegador para continuar."
            )
            return
        self._result = option
        self.destroy()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()

    # -- geometría ---------------------------------------------------------
    def _center(self) -> None:
        """Centra el modal sobre la ventana padre, sin salirse de la pantalla."""
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


def pick_browser(
    parent,
    options: list[BrowserOption] | None = None,
    *,
    theme: Theme = DEFAULT_THEME,
) -> BrowserOption | None:
    """Abre el selector y devuelve el navegador elegido (o ``None``).

    Se puede llamar desde el hilo principal o desde un hilo de trabajo.
    """
    try:
        choices = list(options) if options is not None else browser_choices()
    except Exception:
        # Si la detección falla, el predeterminado siempre está disponible.
        choices = [SYSTEM_DEFAULT]
    if not choices:
        choices = [SYSTEM_DEFAULT]

    if threading.current_thread() is threading.main_thread():
        return BrowserPickerDialog(parent, choices, theme=theme).show()

    return _pick_browser_from_worker(parent, choices, theme)


def _pick_browser_from_worker(
    parent, choices: list[BrowserOption], theme: Theme
) -> BrowserOption | None:
    """Pide el modal al hilo principal y espera su resultado."""
    result: dict[str, BrowserOption | None] = {}
    done = threading.Event()

    def ask() -> None:
        try:
            result["value"] = BrowserPickerDialog(
                parent, choices, theme=theme
            ).show()
        except Exception:
            result["value"] = None
        finally:
            done.set()

    try:
        parent.after(0, ask)
    except Exception:
        return None

    done.wait()
    return result.get("value")
