"""Pruebas para la persistencia de programas por cuenta."""

import json

import pytest

from src.programs import (
    ProgramDefinition,
    ProgramPersistenceError,
    ProgramRepository,
    ProgramStore,
    ProgramStoreError,
)
from src.programs import persistence as persistence_module


def _definition(program="Power BI", pattern="G{número}-Power BI"):
    return ProgramDefinition(
        program=program,
        pattern=pattern,
        destination_path=f"Mi Drive/{program}",
        destination_id=f"id-{program}",
    )


def test_guarda_y_relee_programas(tmp_path):
    path = tmp_path / "programs.json"
    repository = ProgramRepository(path)
    item = _definition()

    repository.save([item])

    result = repository.load()
    assert result.items == (item,)
    assert result.errors == ()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["programs"][0]["program"] == "Power BI"


def test_archivo_inexistente_devuelve_vacio(tmp_path):
    result = ProgramRepository(tmp_path / "programs.json").load()
    assert result.items == ()
    assert result.errors == ()


def test_archivo_corrupto_se_respalda(tmp_path):
    path = tmp_path / "programs.json"
    path.write_text("{roto", encoding="utf-8")

    result = ProgramRepository(path).load()

    assert result.items == ()
    assert result.errors
    assert list(tmp_path.glob("programs.json.corrupt-*"))


def test_omite_entradas_invalidas_y_conserva_las_buenas(tmp_path):
    path = tmp_path / "programs.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "programs": [
                    _definition().to_dict(),
                    {"program": "", "pattern": "X", "destination_path": "Y"},
                    {"program": "Excel", "pattern": "X{fecha}", "destination_path": "Y"},
                    {"program": "Power BI", "pattern": "Otro", "destination_path": "Z"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = ProgramRepository(path).load()

    assert len(result.items) == 1
    assert len(result.errors) == 3
    assert "duplicado" in result.errors[2]


def test_lista_de_programas_invalida(tmp_path):
    path = tmp_path / "programs.json"
    path.write_text(json.dumps({"programs": "no"}), encoding="utf-8")
    result = ProgramRepository(path).load()
    assert result.items == ()
    assert result.errors


def test_version_no_soportada(tmp_path):
    path = tmp_path / "programs.json"
    path.write_text(json.dumps({"version": 99, "programs": []}), encoding="utf-8")
    result = ProgramRepository(path).load()
    assert result.errors


def test_save_rechaza_elementos_que_no_son_definiciones(tmp_path):
    with pytest.raises(ProgramPersistenceError):
        ProgramRepository(tmp_path / "programs.json").save([object()])


def test_save_envuelve_errores_de_escritura(tmp_path, monkeypatch):
    monkeypatch.setattr(
        persistence_module,
        "write_json_atomic",
        lambda *_args: (_ for _ in ()).throw(OSError("sin espacio")),
    )
    with pytest.raises(ProgramPersistenceError, match="guardar"):
        ProgramRepository(tmp_path / "programs.json").save([_definition()])


def test_replace_sustituye_todo_el_registro():
    store = ProgramStore()
    store.add(_definition())
    nuevo = _definition(program="Excel", pattern="Excel - G{número}")

    store.replace([nuevo])

    assert store.items() == (nuevo,)


def test_replace_valida_duplicados_y_deja_el_registro_intacto():
    store = ProgramStore()
    original = _definition()
    store.add(original)

    with pytest.raises(ProgramStoreError, match="Ya existe"):
        store.replace(
            [
                _definition(program="Uno", pattern="A{número}"),
                _definition(program="uno", pattern="B{número}"),
            ]
        )

    assert store.items() == (original,)


def test_replace_valida_el_patron_y_deja_el_registro_intacto():
    store = ProgramStore()
    original = _definition()
    store.add(original)

    with pytest.raises(ProgramStoreError, match="desconocido"):
        store.replace([_definition(pattern="G{fecha}")])

    assert store.items() == (original,)


def test_replace_rechaza_objetos_que_no_son_definiciones():
    with pytest.raises(ProgramStoreError, match="definición"):
        ProgramStore().replace([object()])
