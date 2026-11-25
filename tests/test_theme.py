"""Pruebas para src.ui.theme."""

from unittest.mock import Mock

from src.ui import theme as theme_module
from src.ui.theme import (
    DEFAULT_FONT_SIZE,
    FONT_FAMILY,
    FONT_SIZE_OFFSET,
    PALETTE,
    Theme,
)


def test_offset_global_es_dos():
    assert FONT_SIZE_OFFSET == 2


def test_tk_font_suma_el_offset():
    assert Theme.tk_font(10) == (FONT_FAMILY, 12, "normal")
    assert Theme.tk_font(10, "bold") == (FONT_FAMILY, 12, "bold")


def test_tk_font_por_defecto_suma_el_offset():
    assert Theme.tk_font() == (FONT_FAMILY, 12, "normal")


def test_color_devuelve_la_paleta_oscura():
    theme = Theme()

    for key, value in PALETTE.items():
        assert theme.color(key) == value


def test_no_queda_paleta_clara_ni_api_de_modos():
    assert not hasattr(theme_module, "LIGHT")
    assert not hasattr(theme_module, "DARK")

    theme = Theme()
    for obsolete in ("mode", "is_dark", "set_mode", "toggle", "pair"):
        assert not hasattr(theme, obsolete)


def test_apply_fija_el_modo_oscuro(monkeypatch):
    set_appearance = Mock()
    apply_ttk = Mock()
    monkeypatch.setattr(theme_module.ctk, "set_appearance_mode", set_appearance)
    monkeypatch.setitem(
        theme_module.ctk.ThemeManager.theme["CTkFont"], "size", DEFAULT_FONT_SIZE
    )
    monkeypatch.setattr(Theme, "apply_ttk", apply_ttk)

    Theme().apply()

    set_appearance.assert_called_once_with("dark")
    assert (
        theme_module.ctk.ThemeManager.theme["CTkFont"]["size"]
        == DEFAULT_FONT_SIZE + FONT_SIZE_OFFSET
    )
    apply_ttk.assert_called_once_with()
