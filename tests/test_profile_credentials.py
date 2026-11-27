"""Pruebas para la lectura de archivos de credenciales de Google."""

import json

import pytest

from src.profiles.credentials import ClientSecretsError, read_client_secrets


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_lee_un_cliente_de_escritorio(tmp_path):
    path = _write(
        tmp_path / "credentials.json",
        {
            "installed": {
                "client_id": " cliente ",
                "client_secret": " secreto ",
                "project_id": " proyecto ",
            }
        },
    )

    info = read_client_secrets(path)

    assert info.client_id == "cliente"
    assert info.client_secret == "secreto"
    assert info.project_id == "proyecto"
    assert info.auth_type == "installed"


def test_project_id_es_opcional(tmp_path):
    path = _write(
        tmp_path / "credentials.json",
        {"installed": {"client_id": "c", "client_secret": "s"}},
    )
    assert read_client_secrets(path).project_id is None


def test_rechaza_un_cliente_web(tmp_path):
    path = _write(
        tmp_path / "credentials.json",
        {"web": {"client_id": "c", "client_secret": "s"}},
    )
    with pytest.raises(ClientSecretsError, match="cliente web"):
        read_client_secrets(path)


def test_rechaza_un_json_sin_seccion_installed(tmp_path):
    path = _write(tmp_path / "credentials.json", {"otra": {}})
    with pytest.raises(ClientSecretsError, match="aplicación"):
        read_client_secrets(path)


def test_rechaza_installed_que_no_es_objeto(tmp_path):
    path = _write(tmp_path / "credentials.json", {"installed": []})
    with pytest.raises(ClientSecretsError, match="installed"):
        read_client_secrets(path)


@pytest.mark.parametrize("campo", ["client_id", "client_secret"])
def test_rechaza_campos_obligatorios_vacios(tmp_path, campo):
    datos = {"client_id": "c", "client_secret": "s"}
    datos[campo] = "   "
    path = _write(tmp_path / "credentials.json", {"installed": datos})
    with pytest.raises(ClientSecretsError, match=campo):
        read_client_secrets(path)


def test_rechaza_project_id_que_no_es_texto(tmp_path):
    path = _write(
        tmp_path / "credentials.json",
        {"installed": {"client_id": "c", "client_secret": "s", "project_id": 1}},
    )
    with pytest.raises(ClientSecretsError, match="project_id"):
        read_client_secrets(path)


def test_rechaza_archivo_inexistente(tmp_path):
    with pytest.raises(ClientSecretsError, match="no existe"):
        read_client_secrets(tmp_path / "no-existe.json")


def test_rechaza_json_corrupto(tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text("{roto", encoding="utf-8")
    with pytest.raises(ClientSecretsError, match="JSON"):
        read_client_secrets(path)
