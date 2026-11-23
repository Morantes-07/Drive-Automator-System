"""Pruebas para src.ui.theme."""

from src.ui.theme import FONT_FAMILY, FONT_SIZE_OFFSET, Theme


def test_offset_global_es_dos():
    assert FONT_SIZE_OFFSET == 2


def test_tk_font_suma_el_offset():
    assert Theme.tk_font(10) == (FONT_FAMILY, 12, "normal")
    assert Theme.tk_font(10, "bold") == (FONT_FAMILY, 12, "bold")


def test_tk_font_por_defecto_suma_el_offset():
    assert Theme.tk_font() == (FONT_FAMILY, 12, "normal")
