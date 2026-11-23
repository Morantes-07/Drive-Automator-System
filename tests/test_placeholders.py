"""Pruebas para src.patterns.placeholders."""

import re

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
    assert PLACEHOLDERS["palabra"] == r"[^\W_]+"


def test_fragment_devuelve_regex_correcta():
    assert fragment("número") == r"\d+"
    assert fragment("numero") == r"\d+"  # con o sin tilde
    assert fragment("letra") == r"[A-Za-z]"
    assert fragment("palabra") == r"[^\W_]+"


def test_fragment_palabra_acepta_letras_acentuadas():
    regex = fragment("palabra")
    assert re.fullmatch(regex, "automatización")
    assert re.fullmatch(regex, "Automatización")
    assert re.fullmatch(regex, "niño123")


def test_fragment_palabra_no_acepta_guion_bajo():
    assert not re.fullmatch(fragment("palabra"), "texto_random")


def test_fragment_letra_solo_acepta_ascii():
    regex = fragment("letra")
    assert re.fullmatch(regex, "A")
    assert re.fullmatch(regex, "ñ") is None
    assert re.fullmatch(regex, "á") is None
    assert not re.fullmatch(regex, "1")


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
