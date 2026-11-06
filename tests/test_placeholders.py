"""Pruebas para src.patterns.placeholders."""

import pytest

from src.patterns.placeholders import (
    PLACEHOLDERS,
    UnknownPlaceholderError,
    normalize,
    fragment,
    tokenize,
)


def test_normalize_quita_tildes_y_pasa_a_minusculas():
    assert normalize("Número") == "numero"
    assert normalize("LETRA") == "letra"
    assert normalize("  Palabra  ") == "palabra"


def test_placeholders_built_in():
    assert "numero" in PLACEHOLDERS
    assert PLACEHOLDERS["numero"] == r"\d+"
    assert PLACEHOLDERS["letra"] == r"[A-Za-z]"
    assert PLACEHOLDERS["palabra"] == r"[A-Za-z0-9]+"


def test_fragment_devuelve_regex_correcta():
    assert fragment("número") == r"\d+"
    assert fragment("numero") == r"\d+"  # con o sin tilde
    assert fragment("letra") == r"[A-Za-z]"
    assert fragment("palabra") == r"[A-Za-z0-9]+"


def test_fragment_desconocido_lanza_error():
    with pytest.raises(UnknownPlaceholderError, match="desconocido"):
        fragment("fecha")


def test_tokenize_separa_literales_y_placeholders():
    tokens = tokenize("G{número}-Power BI")
    assert tokens == [
        ("literal", "G"),
        ("placeholder", "número"),
        ("literal", "-Power BI"),
    ]


def test_tokenize_sin_placeholders():
    assert tokenize("Excel - G3") == [("literal", "Excel - G3")]


def test_tokenize_vacio():
    assert tokenize("") == []
