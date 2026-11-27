"""Pruebas para el registro persistente de perfiles."""

import json

import pytest

from src.profiles.models import AccountProfile
from src.profiles.store import ProfileStore, ProfileStoreError

ID1 = "a" * 32
ID2 = "b" * 32
ID3 = "c" * 32


def _profile(profile_id=ID1, name="Trabajo", **extra):
    return AccountProfile(
        id=profile_id,
        name=name,
        email=extra.get("email"),
        client_id=extra.get("client_id"),
        project_id=extra.get("project_id"),
        created_at="2026-01-01T00:00:00+00:00",
        last_used_at=extra.get("last_used_at"),
    )


def test_store_vacio_sin_archivo(tmp_path):
    store = ProfileStore(tmp_path)
    assert store.profiles == ()
    assert store.active is None
    assert store.last_load_error is None


def test_add_guarda_y_relee(tmp_path):
    store = ProfileStore(tmp_path)
    store.add(_profile())
    store.set_active(ID1)

    reloaded = ProfileStore(tmp_path)

    assert reloaded.profiles == (_profile(),)
    assert reloaded.active_id == ID1
    assert reloaded.active == _profile()


def test_add_rechaza_id_duplicado(tmp_path):
    store = ProfileStore(tmp_path)
    store.add(_profile())
    with pytest.raises(ProfileStoreError, match="id"):
        store.add(_profile())


def test_update_reemplaza_y_rechaza_inexistente(tmp_path):
    store = ProfileStore(tmp_path)
    store.add(_profile())
    updated = _profile(name="Personal")
    assert store.update(updated) == updated
    assert store.get(ID1).name == "Personal"
    with pytest.raises(ProfileStoreError, match="No existe"):
        store.update(_profile(ID2))


def test_get_rechaza_inexistente(tmp_path):
    store = ProfileStore(tmp_path)
    with pytest.raises(KeyError):
        store.get(ID1)


def test_remove_limpia_el_activo(tmp_path):
    store = ProfileStore(tmp_path)
    store.add(_profile())
    store.set_active(ID1)

    removed = store.remove(ID1)

    assert removed.id == ID1
    assert store.profiles == ()
    assert store.active_id is None
    assert ProfileStore(tmp_path).active_id is None


def test_remove_rechaza_inexistente(tmp_path):
    with pytest.raises(ProfileStoreError, match="No existe"):
        ProfileStore(tmp_path).remove(ID1)


def test_set_active_rechaza_inexistente(tmp_path):
    with pytest.raises(KeyError):
        ProfileStore(tmp_path).set_active(ID1)


def test_busquedas_por_correo_y_cliente(tmp_path):
    store = ProfileStore(tmp_path)
    store.add(
        _profile(email="User@Example.com", client_id="cliente-1")
    )

    assert store.find_by_email("user@example.com").id == ID1
    assert store.find_by_email(None) is None
    assert store.find_by_email("otro@example.com") is None
    assert store.find_by_client_id("cliente-1").id == ID1
    assert store.find_by_client_id(None) is None
    assert store.find_by_client_id("otro") is None


def test_paths_for_valida_el_id(tmp_path):
    store = ProfileStore(tmp_path)
    assert store.paths_for(ID1).directory == tmp_path / "profiles" / ID1
    with pytest.raises(Exception):
        store.paths_for("../fuera")


def test_archivo_corrupto_se_respalda(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("{roto", encoding="utf-8")

    store = ProfileStore(tmp_path)

    assert store.profiles == ()
    assert store.last_load_error
    backups = list(tmp_path.glob("profiles.json.corrupt-*"))
    assert len(backups) == 1


def test_entradas_invalidas_se_omiten(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "active_id": ID2,
                "profiles": [
                    {"id": ID1, "name": "Trabajo"},
                    {"id": "../fuera", "name": "Malicioso"},
                    {"id": ID2},
                    {"id": ID1, "name": "Duplicado"},
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ProfileStore(tmp_path)

    assert len(store) == 1
    assert store.profiles[0].id == ID1
    assert store.active_id is None
    assert store.last_load_error


def test_version_no_soportada(tmp_path):
    (tmp_path / "profiles.json").write_text(
        json.dumps({"version": 99, "profiles": []}), encoding="utf-8"
    )
    store = ProfileStore(tmp_path)
    assert store.profiles == ()
    assert "versión" in store.last_load_error


def test_lista_de_perfiles_invalida(tmp_path):
    (tmp_path / "profiles.json").write_text(
        json.dumps({"version": 1, "profiles": "no"}), encoding="utf-8"
    )
    store = ProfileStore(tmp_path)
    assert store.last_load_error


def test_iteracion_y_longitud(tmp_path):
    store = ProfileStore(tmp_path)
    store.add(_profile(ID1, "Uno"))
    store.add(_profile(ID2, "Dos"))
    assert len(store) == 2
    assert [item.name for item in store] == ["Uno", "Dos"]
