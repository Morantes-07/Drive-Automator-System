"""Pruebas para el modelo de perfiles de cuenta."""

import pytest

from src.profiles.models import (
    AccountProfile,
    ProfileValidationError,
    now_iso,
)


def test_normaliza_y_serializa_un_perfil():
    profile = AccountProfile(
        id="a" * 32,
        name="  Trabajo  ",
        email=" user@example.com ",
        account_name=" User ",
        client_id=" cliente ",
        project_id=" proyecto ",
    )

    data = profile.to_dict()

    assert profile.name == "Trabajo"
    assert data["email"] == "user@example.com"
    assert AccountProfile.from_dict(data) == profile


def test_campos_opcionales_vacios_quedan_en_none():
    profile = AccountProfile(id="a" * 32, name="Trabajo", email="   ")
    assert profile.email is None


def test_id_y_nombre_son_obligatorios():
    with pytest.raises(ProfileValidationError, match="id"):
        AccountProfile(id="  ", name="Trabajo")
    with pytest.raises(ProfileValidationError, match="nombre"):
        AccountProfile(id="a" * 32, name="  ")


def test_from_dict_rechaza_entradas_invalidas():
    with pytest.raises(ProfileValidationError, match="objeto JSON"):
        AccountProfile.from_dict([])
    with pytest.raises(ProfileValidationError, match="id"):
        AccountProfile.from_dict({"name": "Trabajo"})
    with pytest.raises(ProfileValidationError, match="nombre"):
        AccountProfile.from_dict({"id": "a" * 32})


def test_from_dict_rechaza_campos_opcionales_que_no_son_texto():
    with pytest.raises(ProfileValidationError, match="email"):
        AccountProfile.from_dict(
            {"id": "a" * 32, "name": "Trabajo", "email": 123}
        )


def test_from_dict_rellena_created_at_si_falta():
    profile = AccountProfile.from_dict({"id": "a" * 32, "name": "Trabajo"})
    assert profile.created_at


def test_now_iso_tiene_formato_iso():
    assert "T" in now_iso()
