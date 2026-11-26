"""Pruebas de la ventana principal con tema oscuro exclusivo."""

import customtkinter as ctk

from src.ui import app as app_module


def test_ventana_no_ofrece_cambio_de_modo(monkeypatch):
    """La cabecera no incluye el selector claro/oscuro ni su evento."""
    # La ventana programa reload_drive a los 250 ms; se anula para que la
    # prueba no abra el flujo de autenticación de Google.
    monkeypatch.setattr(
        app_module.DriveOrganizerApp, "reload_drive", lambda self: None
    )

    app = app_module.DriveOrganizerApp()
    try:
        app.update()
        assert not hasattr(app, "_mode_control")
        assert not hasattr(app, "_on_mode_change")
        assert ctk.get_appearance_mode().lower() == "dark"
    finally:
        app.destroy()
