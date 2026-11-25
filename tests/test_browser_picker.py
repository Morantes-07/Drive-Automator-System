"""Pruebas para src.ui.browser_picker."""

import threading
import tkinter as tk
from unittest.mock import Mock

import pytest

from src.authentication.auth import AuthenticationCancelled
from src.authentication.browsers import BrowserOption, SYSTEM_DEFAULT
from src.ui import app as app_module
from src.ui import browser_picker
from src.ui.app import DriveOrganizerApp
from src.ui.browser_picker import BrowserPickerDialog, pick_browser
from src.ui.theme import DEFAULT_THEME

CHROME = BrowserOption("Google Chrome", r"C:\Chrome\chrome.exe")


@pytest.fixture
def dialog(tk_root):
    widget = BrowserPickerDialog(tk_root, [SYSTEM_DEFAULT, CHROME])
    yield widget
    try:
        if widget.winfo_exists():
            widget.destroy()
    except tk.TclError:
        pass


# -- selección en el modal --------------------------------------------------
def test_predeterminado_seleccionado_por_defecto(dialog):
    assert dialog._selected.get() == browser_picker.DEFAULT_KEY

    dialog._accept()

    assert dialog.result is SYSTEM_DEFAULT


def test_selecciona_un_navegador_detectado(dialog):
    dialog._selected.set(CHROME.executable)

    dialog._accept()

    assert dialog.result == CHROME


def test_cancelar_devuelve_none(dialog):
    dialog._cancel()

    assert dialog.result is None


def test_elige_ejecutable_personalizado(dialog, tmp_path, monkeypatch):
    exe = tmp_path / "navegador.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(
        browser_picker.filedialog,
        "askopenfilename",
        lambda **_kwargs: str(exe),
    )

    dialog._choose_custom()
    dialog._accept()

    assert dialog.result == BrowserOption(
        "Navegador personalizado", str(exe)
    )


def test_rechaza_ruta_personalizada_inexistente(dialog, tmp_path, monkeypatch):
    monkeypatch.setattr(
        browser_picker.filedialog,
        "askopenfilename",
        lambda **_kwargs: str(tmp_path / "no.exe"),
    )

    dialog._choose_custom()

    assert dialog._selected.get() == browser_picker.DEFAULT_KEY
    assert "válido" in dialog._message_label.cget("text")


def test_cancelar_explorador_mantiene_la_seleccion(dialog, monkeypatch):
    monkeypatch.setattr(
        browser_picker.filedialog, "askopenfilename", lambda **_kwargs: ""
    )

    dialog._choose_custom()

    assert dialog._selected.get() == browser_picker.DEFAULT_KEY


# -- apertura desde distintos hilos ----------------------------------------
def test_pick_browser_en_hilo_principal(monkeypatch):
    seen: dict[str, object] = {}

    class FakeDialog:
        def __init__(self, parent, options, *, theme):
            seen["options"] = list(options)
            seen["theme"] = theme

        def show(self):
            return CHROME

    monkeypatch.setattr(browser_picker, "BrowserPickerDialog", FakeDialog)

    assert pick_browser(object(), [SYSTEM_DEFAULT, CHROME]) == CHROME
    assert seen["options"] == [SYSTEM_DEFAULT, CHROME]
    assert seen["theme"] is DEFAULT_THEME


def test_pick_browser_desde_un_hilo(monkeypatch):
    class FakeDialog:
        def __init__(self, _parent, _options, *, theme):
            self.theme = theme

        def show(self):
            return CHROME

    class FakeParent:
        def after(self, _delay, callback):
            callback()

    monkeypatch.setattr(browser_picker, "BrowserPickerDialog", FakeDialog)

    result: dict[str, object] = {}

    def run():
        result["value"] = pick_browser(
            FakeParent(), [SYSTEM_DEFAULT, CHROME]
        )

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert result["value"] == CHROME


def test_pick_browser_sin_opciones_usa_predeterminado(monkeypatch):
    seen: dict[str, object] = {}

    class FakeDialog:
        def __init__(self, _parent, options, *, theme):
            seen["options"] = list(options)

        def show(self):
            return SYSTEM_DEFAULT

    monkeypatch.setattr(browser_picker, "BrowserPickerDialog", FakeDialog)

    assert pick_browser(object(), []) is SYSTEM_DEFAULT
    assert seen["options"] == [SYSTEM_DEFAULT]


def test_pick_browser_si_falla_la_deteccion(monkeypatch):
    seen: dict[str, object] = {}

    class FakeDialog:
        def __init__(self, _parent, options, *, theme):
            seen["options"] = list(options)

        def show(self):
            return SYSTEM_DEFAULT

    monkeypatch.setattr(
        browser_picker,
        "browser_choices",
        Mock(side_effect=RuntimeError("registro no disponible")),
    )
    monkeypatch.setattr(browser_picker, "BrowserPickerDialog", FakeDialog)

    assert pick_browser(object()) is SYSTEM_DEFAULT
    assert seen["options"] == [SYSTEM_DEFAULT]


# -- integración con la ventana principal ----------------------------------
def test_provide_browser_delega_en_el_selector(monkeypatch):
    sentinel = object()
    calls: dict[str, object] = {}

    def fake_pick(parent, *, theme):
        calls["parent"] = parent
        calls["theme"] = theme
        return sentinel

    class FakeSelf:
        _theme = DEFAULT_THEME

    monkeypatch.setattr(app_module, "pick_browser", fake_pick)
    fake_self = FakeSelf()

    assert DriveOrganizerApp._provide_browser(fake_self) is sentinel
    assert calls["parent"] is fake_self
    assert calls["theme"] is DEFAULT_THEME


def test_on_drive_error_muestra_autenticacion_cancelada():
    class FakeWidget:
        def set_model(self, model):
            self.model = model

    class FakeButton:
        def configure(self, **_kwargs):
            pass

    class FakeSelf:
        model = object()
        programs_tab = FakeWidget()
        organize_tab = FakeWidget()
        _reload_button = FakeButton()

        def _set_status(self, text, kind="muted"):
            self.status = (text, kind)

    fake_self = FakeSelf()

    DriveOrganizerApp._on_drive_error(
        fake_self, AuthenticationCancelled("cancelado")
    )

    assert fake_self.status[1] == "warning"
    assert "cancelada" in fake_self.status[0].lower()
