"""Detección de los navegadores instalados en Windows.

El módulo solo describe navegadores; no abre ninguno. La apertura se hace en
``src.authentication.auth`` con ``webbrowser``.
"""

from __future__ import annotations

import itertools
import os
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - Windows siempre tiene winreg
    winreg = None


@dataclass(frozen=True)
class BrowserOption:
    """Navegador que puede abrir el flujo de autorización.

    Attributes:
        name: Nombre que se muestra al usuario.
        executable: Ruta del ejecutable, o ``None`` para el navegador
            predeterminado del sistema.
    """

    name: str
    executable: str | None


#: Opción que deja la elección en manos de Windows.
SYSTEM_DEFAULT = BrowserOption("Navegador predeterminado del sistema", None)

#: Nombres amigables según el ejecutable.
BROWSER_DISPLAY_NAMES: dict[str, str] = {
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Mozilla Firefox",
    "brave.exe": "Brave",
    "opera.exe": "Opera",
    "vivaldi.exe": "Vivaldi",
    "chromium.exe": "Chromium",
}

#: Orden en el que se muestran los navegadores detectados.
_EXECUTABLE_ORDER = {
    name: index
    for index, name in enumerate(
        (
            "chrome.exe",
            "msedge.exe",
            "firefox.exe",
            "brave.exe",
            "opera.exe",
            "vivaldi.exe",
            "chromium.exe",
        )
    )
}

#: Rutas relativas conocidas de instalaciones típicas.
KNOWN_BROWSER_PATHS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Google Chrome", (r"Google\Chrome\Application\chrome.exe",)),
    ("Microsoft Edge", (r"Microsoft\Edge\Application\msedge.exe",)),
    ("Mozilla Firefox", (r"Mozilla Firefox\firefox.exe",)),
    ("Brave", (r"BraveSoftware\Brave-Browser\Application\brave.exe",)),
    ("Opera", (r"Programs\Opera\opera.exe", r"Opera\opera.exe")),
    ("Vivaldi", (r"Vivaldi\Application\vivaldi.exe",)),
    ("Chromium", (r"Chromium\Application\chrome.exe",)),
)

#: Comandos que se buscan en el ``PATH``.
PATH_BROWSER_COMMANDS: tuple[tuple[str, str], ...] = (
    ("Google Chrome", "chrome"),
    ("Microsoft Edge", "msedge"),
    ("Mozilla Firefox", "firefox"),
    ("Brave", "brave"),
    ("Opera", "opera"),
    ("Vivaldi", "vivaldi"),
    ("Chromium", "chromium"),
)

#: Clave del registro donde Windows anuncia los navegadores instalados.
_START_MENU_INTERNET = r"SOFTWARE\Clients\StartMenuInternet"


def parse_registry_command(command: str | None) -> str | None:
    """Extrae la ruta del ejecutable de un comando del registro.

    Los comandos suelen tener la forma ``"C:\\ruta\\chrome.exe" -- "%1"`` o
    ``C:\\ruta\\chrome.exe %1``. Si el valor está vacío o no apunta a un
    ejecutable, retorna ``None``.
    """
    if not command:
        return None

    text = str(command).strip()
    if not text:
        return None

    if text.startswith('"'):
        closing = text.find('"', 1)
        if closing == -1:
            return None
        candidate = text[1:closing]
    else:
        candidate = text.split(maxsplit=1)[0]

    candidate = os.path.expandvars(candidate.strip().strip('"'))
    if not candidate.casefold().endswith(".exe"):
        return None
    return candidate


def _read_registry_browser(root, subkey_name: str) -> tuple[str, str] | None:
    """Lee un navegador de una clave ``StartMenuInternet``."""
    if winreg is None:  # pragma: no cover - solo en plataformas sin winreg
        return None

    try:
        with winreg.OpenKey(root, subkey_name) as browser_key:
            try:
                display_name = winreg.QueryValueEx(browser_key, "")[0]
            except OSError:
                display_name = subkey_name
            try:
                with winreg.OpenKey(
                    browser_key, r"shell\open\command"
                ) as command_key:
                    command = winreg.QueryValueEx(command_key, "")[0]
            except OSError:
                return None
    except OSError:
        return None

    executable = parse_registry_command(command)
    if executable is None:
        return None
    return str(display_name or subkey_name), executable


def _registry_entries() -> list[tuple[str, str]]:
    """Navegadores anunciados en el registro de Windows."""
    if winreg is None:  # pragma: no cover - solo en plataformas sin winreg
        return []

    entries: list[tuple[str, str]] = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            root = winreg.OpenKey(hive, _START_MENU_INTERNET)
        except OSError:
            continue
        try:
            count = winreg.QueryInfoKey(root)[0]
            for index in range(count):
                try:
                    subkey_name = winreg.EnumKey(root, index)
                except OSError:
                    continue
                entry = _read_registry_browser(root, subkey_name)
                if entry is not None:
                    entries.append(entry)
        finally:
            winreg.CloseKey(root)
    return entries


def _known_entries(
    environment: Mapping[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Rutas de instalación habituales, expandidas con las variables de entorno."""
    values = os.environ if environment is None else environment
    bases: list[Path] = []
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        value = values.get(variable)
        if value:
            bases.append(Path(value))

    entries: list[tuple[str, str]] = []
    for name, relatives in KNOWN_BROWSER_PATHS:
        for base in bases:
            for relative in relatives:
                entries.append(
                    (name, str(base.joinpath(*relative.split("\\"))))
                )
    return entries


def _path_entries(which=shutil.which) -> list[tuple[str, str]]:
    """Navegadores que se pueden localizar por el ``PATH``."""
    entries: list[tuple[str, str]] = []
    for name, command in PATH_BROWSER_COMMANDS:
        path = which(command)
        if path:
            entries.append((name, path))
    return entries


def _make_option(name: str, candidate: str) -> BrowserOption | None:
    """Convierte una ruta candidata en opción, si el archivo existe."""
    if not candidate:
        return None

    path = Path(os.path.expandvars(str(candidate))).expanduser()
    try:
        if not path.is_file():
            return None
    except OSError:
        return None

    friendly = BROWSER_DISPLAY_NAMES.get(path.name.casefold())
    if not friendly:
        friendly = str(name).strip() or path.stem.title()
    return BrowserOption(name=friendly, executable=str(path))


def _dedupe_key(executable: str) -> str:
    """Clave para no repetir el mismo ejecutable detectado por varias vías."""
    try:
        path = Path(executable).resolve()
    except OSError:
        path = Path(executable).absolute()
    return os.path.normcase(str(path))


def _sort_key(option: BrowserOption) -> tuple[int, str]:
    """Ordena primero los navegadores más habituales."""
    if option.executable is None:
        return (-1, option.name.casefold())
    filename = Path(option.executable).name.casefold()
    return (_EXECUTABLE_ORDER.get(filename, len(_EXECUTABLE_ORDER)), option.name.casefold())


def detect_browsers(
    *,
    registry_entries: Iterable[tuple[str, str]] | None = None,
    known_entries: Iterable[tuple[str, str]] | None = None,
    path_entries: Iterable[tuple[str, str]] | None = None,
) -> list[BrowserOption]:
    """Detecta navegadores y devuelve una lista sin duplicados.

    Los parámetros permiten sustituir las fuentes de detección en las pruebas.
    """
    registry = (
        _registry_entries() if registry_entries is None else registry_entries
    )
    known = _known_entries() if known_entries is None else known_entries
    path = _path_entries() if path_entries is None else path_entries

    found: dict[str, BrowserOption] = {}
    for name, candidate in itertools.chain(registry, known, path):
        option = _make_option(name, candidate)
        if option is None:
            continue
        found.setdefault(_dedupe_key(option.executable), option)

    return sorted(found.values(), key=_sort_key)


def browser_choices() -> list[BrowserOption]:
    """Opciones que ofrece el modal: el predeterminado y los detectados."""
    return [SYSTEM_DEFAULT, *detect_browsers()]
