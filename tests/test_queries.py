"""Pruebas para src.drive.queries."""

from src.drive.queries import QUERY_OWNED, QUERY_SHARED


def test_query_owned_solo_archivos_propios():
    assert "'me' in owners" in QUERY_OWNED
    assert "trashed = false" in QUERY_OWNED
    assert "application/vnd.google-apps.folder" in QUERY_OWNED


def test_query_owned_no_usa_filtros_que_la_api_rechaza():
    # La API devuelve 400 "Invalid Value" con shared = false y
    # sharedWithMe = false; el filtro shared se aplica en el cliente.
    assert "sharedWithMe" not in QUERY_OWNED
    assert "shared =" not in QUERY_OWNED


def test_query_shared_solo_archivos_compartidos():
    assert "sharedWithMe = true" in QUERY_SHARED
    assert "trashed = false" in QUERY_SHARED
    assert "application/vnd.google-apps.folder" in QUERY_SHARED
