"""Pruebas para src.ui.icon."""

from pathlib import Path
from types import SimpleNamespace

from src.ui import icon
from src.ui.icon import (
    APP_USER_MODEL_ID,
    ICON_FILENAME,
    apply_window_icon,
    icon_path,
    set_app_user_model_id,
)


def test_icon_path_apunta_al_recurso_del_proyecto():
    path = icon_path()

    assert path.name == ICON_FILENAME
    assert path.parent.name == "assets"
    assert path.is_file()


def test_icono_incluye_tamanio_de_barra_de_tareas():
    # La cabecera ICO indica cuántas entradas tiene; el primer byte de cada
    # entrada es el ancho, con 0 para representar 256 píxeles.
    data = icon_path().read_bytes()
    total = int.from_bytes(data[4:6], "little")
    anchos = [data[6 + i * 16] or 256 for i in range(total)]

    assert 16 in anchos
    assert 32 in anchos


def test_set_app_user_model_id_en_windows(monkeypatch):
    registros = []
    shell32 = SimpleNamespace(
        SetCurrentProcessExplicitAppUserModelID=lambda value: registros.append(value) or 0
    )
    monkeypatch.setattr(icon.sys, "platform", "win32")
    monkeypatch.setattr(icon.ctypes, "windll", SimpleNamespace(shell32=shell32), raising=False)

    assert set_app_user_model_id() is True
    assert registros == [APP_USER_MODEL_ID]


def test_set_app_user_model_id_fuera_de_windows(monkeypatch):
    monkeypatch.setattr(icon.sys, "platform", "linux")

    assert set_app_user_model_id() is False


def test_apply_window_icon_registra_icono_grande_y_pequeno(tk_root, monkeypatch):
    llamadas = []
    monkeypatch.setattr(tk_root, "iconbitmap", lambda path: llamadas.append(path))

    assert apply_window_icon(tk_root) is True
    assert llamadas == [str(icon_path())]


def test_apply_window_icon_sin_archivo_no_lanza(monkeypatch, tk_root):
    monkeypatch.setattr(icon, "icon_path", lambda: Path("icono_inexistente.ico"))

    assert apply_window_icon(tk_root) is False


def test_run_app_registra_identidad_antes_de_crear_la_ventana(monkeypatch):
    from src.ui import app as app_module

    orden = []
    monkeypatch.setattr(
        app_module, "set_app_user_model_id", lambda: orden.append("identidad")
    )
    monkeypatch.setattr(
        app_module,
        "DriveOrganizerApp",
        lambda: orden.append("ventana") or SimpleNamespace(mainloop=lambda: None),
    )

    app_module.run_app()

    assert orden == ["identidad", "ventana"]
