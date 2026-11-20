"""Pruebas para src.drive.drive_client (sin llamar a la API real)."""

from unittest.mock import MagicMock

import pytest

from src.drive.drive_client import (
    FIELDS,
    create_folder,
    move_file,
)


def test_fields_incluye_owners_parents_y_shared():
    assert "owners" in FIELDS
    assert "parents" in FIELDS
    assert "shared" in FIELDS


def test_create_folder_llama_a_la_api():
    service = MagicMock()
    service.files.return_value.create.return_value.execute.return_value = {
        "id": "nueva",
        "name": "G1-Power BI",
        "parents": ["destino"],
    }

    result = create_folder(service, " G1-Power BI ", " destino ")

    service.files.return_value.create.assert_called_once_with(
        body={
            "name": "G1-Power BI",
            "mimeType": "application/vnd.google-apps.folder",
            "parents": ["destino"],
        },
        fields="id, name, parents",
    )
    assert result["id"] == "nueva"


def test_create_folder_valida_el_nombre():
    with pytest.raises(ValueError, match="nombre"):
        create_folder(MagicMock(), "   ", "destino")


def test_create_folder_valida_el_padre():
    with pytest.raises(ValueError, match="padre"):
        create_folder(MagicMock(), "G1-Power BI", "   ")


def test_move_file_llama_a_la_api():
    service = MagicMock()
    service.files.return_value.update.return_value.execute.return_value = {
        "id": "archivo",
        "name": "G1-Power BI.mp4",
        "parents": ["destino"],
    }

    result = move_file(service, "archivo", "destino", ["origen"])

    service.files.return_value.update.assert_called_once_with(
        fileId="archivo",
        addParents="destino",
        removeParents="origen",
        fields="id, name, parents",
    )
    assert result["id"] == "archivo"


def test_move_file_sin_padres_anteriores_no_pasa_remove_parents():
    service = MagicMock()
    service.files.return_value.update.return_value.execute.return_value = {}

    move_file(service, "archivo", "destino", [])

    service.files.return_value.update.assert_called_once_with(
        fileId="archivo",
        addParents="destino",
        fields="id, name, parents",
    )


def test_move_file_no_quita_el_padre_nuevo_de_los_anteriores():
    service = MagicMock()
    service.files.return_value.update.return_value.execute.return_value = {}

    move_file(service, "archivo", "destino", ["origen", "destino"])

    service.files.return_value.update.assert_called_once_with(
        fileId="archivo",
        addParents="destino",
        removeParents="origen",
        fields="id, name, parents",
    )


def test_move_file_valida_el_archivo():
    with pytest.raises(ValueError, match="archivo"):
        move_file(MagicMock(), "   ", "destino", ["origen"])


def test_move_file_valida_el_destino():
    with pytest.raises(ValueError, match="destino"):
        move_file(MagicMock(), "archivo", "   ", ["origen"])
