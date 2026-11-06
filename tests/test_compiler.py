"""Pruebas para src.patterns.compiler."""

import pytest

from src.patterns.compiler import (
    PatternSpec,
    CompiledPattern,
    CompileError,
    compile_pattern,
    compile_patterns,
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
