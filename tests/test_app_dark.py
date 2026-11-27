"""Pruebas de la ventana principal con tema oscuro exclusivo."""

import customtkinter as ctk

from src.profiles.service import AccountService
from src.profiles.store import ProfileStore
from src.ui import app as app_module


def test_ventana_no_ofrece_cambio_de_modo(tmp_path, monkeypatch):
    """La cabecera no incluye el selector claro/oscuro ni su evento."""
    # La ventana programa reload_drive a los 250 ms; se anula para que la
    # prueba no abra el flujo de autenticación de Google.
    monkeypatch.setattr(
        app_module.DriveOrganizerApp, "reload_drive", lambda self: None
    )
    # Los datos reales del usuario nunca deben tocarse desde las pruebas.
    profiles = ProfileStore(tmp_path / "data")
    accounts = AccountService(
        profiles,
        legacy_credentials=tmp_path / "sin-credenciales.json",
        legacy_token=tmp_path / "sin-token.json",
    )

    app = app_module.DriveOrganizerApp(profiles=profiles, accounts=accounts)
    try:
        app.update()
        assert not hasattr(app, "_mode_control")
        assert not hasattr(app, "_on_mode_change")
        assert ctk.get_appearance_mode().lower() == "dark"
    finally:
        app._closing = True
        app.destroy()
