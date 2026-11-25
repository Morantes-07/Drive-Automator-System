"""Pruebas para src.authentication.browsers."""

from pathlib import Path

import pytest

from src.authentication import browsers
from src.authentication.browsers import BrowserOption, SYSTEM_DEFAULT


def _create_exe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


class _FakeKey:
    """Clave mínima del registro para las pruebas."""

    def __init__(self, values=None, subkeys=None):
        self.values = values or {}
        self.subkeys = subkeys or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _FakeWinreg:
    """Sustituto de ``winreg`` con la misma interfaz que usa el módulo."""

    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"

    def __init__(self, roots):
        self._roots = roots

    def OpenKey(self, key, path):
        current = key if isinstance(key, _FakeKey) else self._roots.get(key)
        if current is None:
            raise OSError
        for part in path.split("\\"):
            if not part:
                continue
            current = current.subkeys.get(part)
            if current is None:
                raise OSError
        return current

    def QueryInfoKey(self, key):
        return (len(key.subkeys), 0, 0)

    def EnumKey(self, key, index):
        try:
            return list(key.subkeys)[index]
        except IndexError as exc:
            raise OSError from exc

    def QueryValueEx(self, key, name):
        try:
            return (key.values[name], 1)
        except KeyError as exc:
            raise OSError from exc

    def CloseKey(self, _key):
        pass


def _registry_tree(command: str):
    """Construye la jerarquía SOFTWARE\\Clients\\StartMenuInternet."""
    command_key = _FakeKey(values={"": command})
    open_key = _FakeKey(subkeys={"command": command_key})
    shell_key = _FakeKey(subkeys={"open": open_key})
    browser_key = _FakeKey(
        values={"": "Google Chrome"}, subkeys={"shell": shell_key}
    )
    start_menu = _FakeKey(subkeys={"Google Chrome": browser_key})
    clients = _FakeKey(subkeys={"StartMenuInternet": start_menu})
    software = _FakeKey(subkeys={"Clients": clients})
    return _FakeKey(subkeys={"SOFTWARE": software})


# -- parse_registry_command -------------------------------------------------
def test_parsea_comando_con_comillas():
    command = r'"C:\Program Files\Google\Chrome\Application\chrome.exe" -- "%1"'
    assert (
        browsers.parse_registry_command(command)
        == r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    )


def test_parsea_comando_sin_comillas():
    command = r"C:\Firefox\firefox.exe %1"
    assert browsers.parse_registry_command(command) == r"C:\Firefox\firefox.exe"


def test_rechaza_comando_sin_exe():
    assert browsers.parse_registry_command('"C:\\Ruta\\programa" %1') is None


def test_rechaza_comillas_sin_cerrar():
    assert browsers.parse_registry_command('"C:\\Ruta\\chrome.exe') is None


@pytest.mark.parametrize("value", [None, "", "   "])
def test_rechaza_comando_vacio(value):
    assert browsers.parse_registry_command(value) is None


# -- fuentes de detección ---------------------------------------------------
def test_registry_entries_lee_el_comando(monkeypatch):
    command = r'"C:\Chrome\chrome.exe" -- "%1"'
    fake = _FakeWinreg({"HKCU": _registry_tree(command)})
    monkeypatch.setattr(browsers, "winreg", fake)

    assert browsers._registry_entries() == [
        ("Google Chrome", r"C:\Chrome\chrome.exe")
    ]


def test_known_entries_expande_variables(tmp_path):
    exe = _create_exe(
        tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    )

    entries = browsers._known_entries({"PROGRAMFILES": str(tmp_path)})

    assert ("Google Chrome", str(exe)) in entries


def test_path_entries_usa_which():
    paths = {
        "chrome": r"C:\Chrome\chrome.exe",
        "firefox": r"C:\Firefox\firefox.exe",
    }

    entries = browsers._path_entries(which=paths.get)

    assert entries == [
        ("Google Chrome", r"C:\Chrome\chrome.exe"),
        ("Mozilla Firefox", r"C:\Firefox\firefox.exe"),
    ]


# -- detect_browsers --------------------------------------------------------
def test_detecta_filtra_y_deduplica(tmp_path):
    chrome = _create_exe(tmp_path / "chrome.exe")
    firefox = _create_exe(tmp_path / "firefox.exe")

    options = browsers.detect_browsers(
        registry_entries=[
            ("Google Chrome", str(chrome)),
            ("Google Chrome", str(chrome)),
        ],
        known_entries=[("Google Chrome", str(firefox))],
        path_entries=[],
    )

    assert options == [
        BrowserOption("Google Chrome", str(chrome)),
        BrowserOption("Mozilla Firefox", str(firefox)),
    ]


def test_ignora_ejecutables_inexistentes(tmp_path):
    options = browsers.detect_browsers(
        registry_entries=[("Google Chrome", str(tmp_path / "no.exe"))],
        known_entries=[],
        path_entries=[],
    )

    assert options == []


def test_usa_el_nombre_recibido_si_es_desconocido(tmp_path):
    exe = _create_exe(tmp_path / "navegador.exe")

    options = browsers.detect_browsers(
        registry_entries=[("Mi Navegador", str(exe))],
        known_entries=[],
        path_entries=[],
    )

    assert options == [BrowserOption("Mi Navegador", str(exe))]


def test_browser_choices_incluye_el_predeterminado(monkeypatch):
    custom = BrowserOption("Navegador X", r"C:\NavegadorX\navegador.exe")
    monkeypatch.setattr(browsers, "detect_browsers", lambda: [custom])

    assert browsers.browser_choices() == [SYSTEM_DEFAULT, custom]
