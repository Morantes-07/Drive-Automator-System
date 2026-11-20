"""Pruebas para src.patterns.compiler."""

import re

import pytest

from src.patterns.compiler import (
    PatternSpec,
    CompiledPattern,
    CompileError,
    RenderError,
    compile_pattern,
    compile_patterns,
    render_folder_name,
)


def test_compila_patron_sin_placeholders():
    spec = PatternSpec(program="Excel", pattern="Excel - G3")
    compiled = compile_pattern(spec)
    assert isinstance(compiled, CompiledPattern)
    assert compiled.program == "Excel"
    assert compiled.source == "Excel - G3"
    assert compiled.placeholders == ()
    assert compiled.regex.search("reporte Excel - G3.xlsx") is not None


def test_compila_patron_con_numeros():
    spec = PatternSpec(program="Power BI", pattern="G{número}-Power BI")
    compiled = compile_pattern(spec)
    assert compiled.placeholders == ("numero",)
    assert compiled.regex.search("G12-Power BI.xlsx") is not None
    assert compiled.regex.search("otro G7-Power BI final.pdf") is not None
    assert compiled.regex.search("G-Power BI.xlsx") is None  # requiere >=1 dígito


def test_case_insensitive_por_defecto():
    spec = PatternSpec(program="Power BI", pattern="G{número}-Power BI")
    compiled = compile_pattern(spec)
    assert compiled.regex.search("g12-power bi.xlsx") is not None


def test_programa_vacio_lanza_error():
    with pytest.raises(CompileError, match="programa"):
        compile_pattern(PatternSpec(program="", pattern="X{número}"))


def test_patron_vacio_lanza_error():
    with pytest.raises(CompileError, match="patrón"):
        compile_pattern(PatternSpec(program="X", pattern=""))


def test_placeholder_desconocido_lanza_error():
    with pytest.raises(CompileError, match="desconocido"):
        compile_pattern(PatternSpec(program="X", pattern="G{fecha}"))


def test_programa_duplicado_lanza_error():
    specs = [
        PatternSpec(program="Power BI", pattern="G{número}-Power BI"),
        PatternSpec(program="Power BI", pattern="Otro{número}"),
    ]
    with pytest.raises(CompileError, match="duplicado"):
        compile_patterns(specs)


def test_compile_patterns_devuelve_lista():
    specs = [
        PatternSpec(program="Power BI", pattern="G{número}-Power BI"),
        PatternSpec(program="Excel", pattern="Excel - G{número}"),
    ]
    compiladas = compile_patterns(specs)
    assert len(compiladas) == 2
    assert compiladas[0].program == "Power BI"
    assert compiladas[1].program == "Excel"


def test_render_folder_name_reconstruye_desde_el_patron():
    compiled = compile_pattern(
        PatternSpec(program="Power BI", pattern="G{número}-Power BI")
    )
    assert render_folder_name(compiled, {"numero": "2"}) == "G2-Power BI"


def test_render_folder_name_admite_placeholder_sin_tilde():
    compiled = compile_pattern(
        PatternSpec(program="Power BI", pattern="G{numero}-Power BI")
    )
    assert render_folder_name(compiled, {"numero": "12"}) == "G12-Power BI"


def test_render_folder_name_con_letra_y_palabra():
    compiled = compile_pattern(
        PatternSpec(
            program="Python",
            pattern="Python-{letra}{número}-{palabra}-G1",
        )
    )
    assert (
        render_folder_name(
            compiled,
            {"letra": "A", "numero": "3", "palabra": "curso2024"},
        )
        == "Python-A3-curso2024-G1"
    )


def test_render_folder_name_sin_placeholders():
    compiled = compile_pattern(
        PatternSpec(program="Excel", pattern="Excel - G3")
    )
    assert render_folder_name(compiled, {}) == "Excel - G3"


def test_render_folder_name_falta_un_valor():
    compiled = compile_pattern(
        PatternSpec(program="Power BI", pattern="G{número}-Power BI")
    )
    with pytest.raises(RenderError, match="Falta el valor"):
        render_folder_name(compiled, {})


def test_render_folder_name_rechaza_tipo_incorrecto():
    with pytest.raises(RenderError, match="CompiledPattern"):
        render_folder_name("no es un patrón", {})


def test_render_folder_name_rechaza_separador_en_el_resultado():
    compiled = CompiledPattern(
        program="X",
        source="A/B",
        regex=re.compile("A/B"),
        placeholders=(),
    )
    with pytest.raises(RenderError, match="separador"):
        render_folder_name(compiled, {})


def test_render_folder_name_rechaza_nombre_vacio():
    compiled = CompiledPattern(
        program="X",
        source="   ",
        regex=re.compile("   "),
        placeholders=(),
    )
    with pytest.raises(RenderError, match="vacío"):
        render_folder_name(compiled, {})


@pytest.mark.parametrize("pattern", ["A/B", "A\\B"])
def test_el_patron_no_puede_contener_separadores_de_ruta(pattern):
    with pytest.raises(CompileError, match="no puede contener"):
        compile_pattern(PatternSpec(program="X", pattern=pattern))
