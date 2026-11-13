"""Pruebas para src.programs (definiciones y registro de programas)."""

import pytest

from src.programs import ProgramDefinition, ProgramStore, ProgramStoreError


def definicion(program="Power BI", pattern="G{número}-Power BI", destination="Mi Drive/Power BI"):
    return ProgramDefinition(
        program=program,
        pattern=pattern,
        destination_path=destination,
    )


def test_la_definicion_normaliza_los_espacios():
    item = ProgramDefinition(
        program="  Power BI  ",
        pattern="  G{número}-Power BI ",
        destination_path="  Mi Drive/Power BI ",
    )
    assert item.program == "Power BI"
    assert item.pattern == "G{número}-Power BI"
    assert item.destination_path == "Mi Drive/Power BI"


def test_to_spec_devuelve_el_patron_del_compilador():
    spec = definicion().to_spec()
    assert spec.program == "Power BI"
    assert spec.pattern == "G{número}-Power BI"


def test_add_registra_el_programa():
    store = ProgramStore()
    guardado = store.add(definicion())
    assert len(store) == 1
    assert store.get(0) is guardado
    assert store.items() == (guardado,)


def test_add_rechaza_programas_duplicados_sin_distinguir_mayusculas():
    store = ProgramStore()
    store.add(definicion())
    with pytest.raises(ProgramStoreError, match="Ya existe"):
        store.add(definicion(program="power bi", pattern="Otro{número}"))


def test_add_valida_programa_patron_y_destino():
    store = ProgramStore()
    with pytest.raises(ProgramStoreError, match="nombre del programa"):
        store.add(definicion(program="   "))
    with pytest.raises(ProgramStoreError, match="patrón"):
        store.add(definicion(program="Excel", pattern="  "))
    with pytest.raises(ProgramStoreError, match="carpeta destino"):
        store.add(definicion(program="Excel", destination="  "))


def test_add_valida_el_patron_con_el_compilador():
    store = ProgramStore()
    with pytest.raises(ProgramStoreError, match="desconocido"):
        store.add(definicion(program="Excel", pattern="G{fecha}"))
    assert len(store) == 0


def test_update_permite_conservar_el_mismo_programa():
    store = ProgramStore()
    store.add(definicion())
    store.update(0, definicion(pattern="Otro{número}", destination="Mi Drive/Otro"))
    assert store.get(0).pattern == "Otro{número}"


def test_update_rechaza_el_nombre_de_otro_programa():
    store = ProgramStore()
    store.add(definicion())
    store.add(definicion(program="Excel", pattern="Excel - G{número}"))
    with pytest.raises(ProgramStoreError, match="Ya existe"):
        store.update(1, definicion(program="Power BI", pattern="X{número}"))


def test_update_y_remove_comprueban_el_rango():
    store = ProgramStore()
    with pytest.raises(IndexError):
        store.update(0, definicion())
    with pytest.raises(IndexError):
        store.remove(0)


def test_remove_devuelve_el_programa_y_lo_quita():
    store = ProgramStore()
    guardado = store.add(definicion())
    assert store.remove(0) is guardado
    assert len(store) == 0


def test_index_of_ignora_mayusculas_y_espacios():
    store = ProgramStore()
    store.add(definicion())
    assert store.index_of("power bi") == 0
    assert store.index_of("  POWER BI  ") == 0
    assert store.index_of("Excel") is None


def test_specs_y_compiled_usan_todos_los_programas():
    store = ProgramStore()
    store.add(definicion())
    store.add(definicion(program="Excel", pattern="Excel - G{número}"))
    assert [spec.program for spec in store.specs()] == ["Power BI", "Excel"]
    compilados = store.compiled()
    assert len(compilados) == 2
    assert compilados[0].regex.search("G7-Power BI.xlsx") is not None


def test_clear_vacia_el_registro():
    store = ProgramStore()
    store.add(definicion())
    store.clear()
    assert len(store) == 0
    assert store.items() == ()
