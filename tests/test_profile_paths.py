"""Pruebas para las rutas administradas de un perfil."""

import pytest

from src.profiles.paths import (
    PROFILE_ID_PATTERN,
    ProfilePathError,
    ProfilePaths,
    default_data_directory,
    generate_profile_id,
    validate_profile_id,
)


def test_generate_profile_id_es_seguro():
    profile_id = generate_profile_id()
    assert PROFILE_ID_PATTERN.fullmatch(profile_id)
    assert len(profile_id) == 32


def test_validate_profile_id_acepta_y_normaliza():
    value = "A" * 32
    assert validate_profile_id(value) == "a" * 32


@pytest.mark.parametrize(
    "value",
    ["", "   ", "../fuera", "a" * 31, "g" * 32, "a" * 33],
)
def test_validate_profile_id_rechaza_valores_inseguros(value):
    with pytest.raises(ProfilePathError):
        validate_profile_id(value)


def test_profile_paths_deriva_los_archivos(tmp_path):
    paths = ProfilePaths(tmp_path, "b" * 32)

    assert paths.directory == tmp_path / "profiles" / ("b" * 32)
    assert paths.credentials == paths.directory / "credentials.json"
    assert paths.token == paths.directory / "token.json"
    assert paths.programs == paths.directory / "programs.json"


def test_ensure_directory_crea_la_carpeta(tmp_path):
    paths = ProfilePaths(tmp_path, "c" * 32)
    assert paths.ensure_directory() == paths.directory
    assert paths.directory.is_dir()


def test_data_por_defecto_es_la_carpeta_data_del_proyecto():
    assert default_data_directory().name == "data"
