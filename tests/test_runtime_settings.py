"""Pruebas para src.runtime_settings."""

from src.runtime_settings import RuntimeSettings


def test_dry_run_activo_por_defecto():
    settings = RuntimeSettings()
    assert settings.dry_run is True


def test_dry_run_se_puede_desactivar_en_caliente():
    settings = RuntimeSettings()
    settings.dry_run = False
    assert settings.dry_run is False


def test_dry_run_se_puede_reactivar():
    settings = RuntimeSettings(dry_run=False)
    settings.dry_run = True
    assert settings.dry_run is True


def test_instancias_independientes():
    first = RuntimeSettings()
    second = RuntimeSettings()
    first.dry_run = False
    assert second.dry_run is True
