"""Pruebas para src.patterns.matcher."""

import pytest

from src.patterns.compiler import PatternSpec, compile_patterns
from src.patterns.matcher import match_file, match_files


def _patrones():
    return compile_patterns([
        PatternSpec(program="Power BI", pattern="G{número}-Power BI"),
        PatternSpec(program="Excel", pattern="Excel - G{número}"),
        PatternSpec(
            program="Python",
            pattern="Python-{letra}{número}-{palabra}-G1",
        ),
        PatternSpec(program="Java", pattern="JVM Level {letra}"),
    ])


def test_match_devuelve_programa_y_valores():
    pats = _patrones()
    res = match_file("G12-Power BI.xlsx", pats)
    assert res.status == "matched"
    assert res.program == "Power BI"
    assert res.values == {"numero": "12"}


def test_match_case_insensitive():
    pats = _patrones()
    res = match_file("excel - g3.csv", pats)
    assert res.status == "matched"
    assert res.program == "Excel"
    assert res.values == {"numero": "3"}


def test_match_en_medio_del_nombre():
    pats = _patrones()
    res = match_file("reporte G7-Power BI final.pdf", pats)
    assert res.status == "matched"
    assert res.program == "Power BI"


def test_sin_coincidencia_devuelve_unmatched():
    pats = _patrones()
    res = match_file("archivo_aleatorio.txt", pats)
    assert res.status == "unmatched"
    assert res.program is None
    assert res.values == {}


def test_match_con_letras_y_palabra():
    pats = _patrones()
    res = match_file("Python-A3-curso2024-G1.py", pats)
    assert res.status == "matched"
    assert res.program == "Python"
    assert res.values == {"letra": "A", "numero": "3", "palabra": "curso2024"}


def test_ambiguedad_no_asigna_programa_y_guarda_candidatos():
    pats = compile_patterns([
        PatternSpec(program="A", pattern="X{número}"),
        PatternSpec(program="B", pattern="X{número}"),
    ])
    res = match_file("X5.txt", pats)
    assert res.status == "ambiguous"
    assert res.program is None
    assert res.candidates == ("A", "B")


def test_match_files_agrupa_resultados():
    pats = _patrones()
    report = match_files(
        ["G1-Power BI.xlsx", "archivo.txt", "Excel - G2.csv"], pats
    )
    assert len(report.results) == 3
    assert len(report.matched) == 2
    assert len(report.unmatched) == 1
    assert len(report.ambiguous) == 0


def test_match_files_reporta_archivos_ambiguos():
    pats = compile_patterns([
        PatternSpec(program="A", pattern="X{número}"),
        PatternSpec(program="B", pattern="X{número}"),
    ])
    report = match_files(["X5.txt", "Y1.doc"], pats)
    assert len(report.ambiguous) == 1
    assert report.ambiguous[0].file_name == "X5.txt"


def test_match_incluye_el_texto_encontrado_y_la_subcarpeta():
    pats = _patrones()
    res = match_file("G12-Power BI.xlsx", pats)
    assert res.matched_text == "G12-Power BI"
    assert res.folder_name == "G12-Power BI"


def test_match_normaliza_la_subcarpeta_desde_el_patron():
    pats = _patrones()
    res = match_file("g2-power bi.xlsx", pats)
    assert res.matched_text == "g2-power bi"
    assert res.folder_name == "G2-Power BI"


def test_match_en_medio_del_nombre_genera_subcarpeta_con_el_match():
    pats = _patrones()
    res = match_file("reporte G7-Power BI final.pdf", pats)
    assert res.matched_text == "G7-Power BI"
    assert res.folder_name == "G7-Power BI"


def test_match_con_letra_y_palabra_genera_subcarpeta():
    pats = _patrones()
    res = match_file("Python-A3-curso2024-G1.py", pats)
    assert res.folder_name == "Python-A3-curso2024-G1"


def test_unmatched_no_tiene_texto_ni_subcarpeta():
    pats = _patrones()
    res = match_file("archivo_aleatorio.txt", pats)
    assert res.matched_text is None
    assert res.folder_name is None


def test_ambiguous_no_tiene_texto_ni_subcarpeta():
    pats = compile_patterns([
        PatternSpec(program="A", pattern="X{número}"),
        PatternSpec(program="B", pattern="X{número}"),
    ])
    res = match_file("X5.txt", pats)
    assert res.matched_text is None
    assert res.folder_name is None
