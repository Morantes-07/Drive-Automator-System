"""Fixtures compartidas para las pruebas de interfaz."""

import tkinter as tk

import pytest


@pytest.fixture(scope="session")
def tk_root():
    """Raíz de Tk oculta para las pruebas que construyen widgets reales."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk no está disponible en este entorno")
    root.withdraw()
    yield root
    root.destroy()
