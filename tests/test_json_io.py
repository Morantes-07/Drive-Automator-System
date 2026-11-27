"""Pruebas para src.utils.json_io."""

import pytest

from src.utils.json_io import (
    JsonFileError,
    backup_corrupt_file,
    read_json_object,
    write_json_atomic,
)


def test_escribe_y_lee_un_objeto(tmp_path):
    path = tmp_path / "sub" / "datos.json"
    write_json_atomic(path, {"version": 1, "nombre": "Trabajo"})

    assert read_json_object(path) == {"version": 1, "nombre": "Trabajo"}
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_sobrescribe_el_archivo(tmp_path):
    path = tmp_path / "datos.json"
    write_json_atomic(path, {"a": 1})
    write_json_atomic(path, {"a": 2})
    assert read_json_object(path)["a"] == 2


def test_archivo_inexistente_lanza_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_json_object(tmp_path / "no-existe.json")


def test_json_invalido_lanza_error(tmp_path):
    path = tmp_path / "roto.json"
    path.write_text("{no es json", encoding="utf-8")
    with pytest.raises(JsonFileError, match="JSON válido"):
        read_json_object(path)


def test_raiz_que_no_es_objeto_lanza_error(tmp_path):
    path = tmp_path / "lista.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(JsonFileError, match="objeto JSON"):
        read_json_object(path)


def test_backup_renombra_el_archivo_corrupto(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("{roto", encoding="utf-8")

    backup = backup_corrupt_file(path)

    assert backup is not None
    assert not path.exists()
    assert backup.read_text(encoding="utf-8") == "{roto"


def test_backup_de_archivo_inexistente_devuelve_none(tmp_path):
    assert backup_corrupt_file(tmp_path / "no-existe.json") is None


def test_backup_no_pisa_una_copia_anterior(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("{roto", encoding="utf-8")

    first = backup_corrupt_file(path)
    path.write_text("{otro roto", encoding="utf-8")
    second = backup_corrupt_file(path)

    assert first is not None and second is not None
    assert first != second
    assert first.read_text(encoding="utf-8") == "{roto"
    assert second.read_text(encoding="utf-8") == "{otro roto"
