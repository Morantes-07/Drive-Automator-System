"""Autenticación OAuth con Google Drive.

El flujo de navegador solo se ejecuta cuando no hay un token válido ni se
puede refrescar. En ese momento se pregunta al usuario qué navegador abrir.

Cada perfil de cuenta tiene su propio ``credentials.json`` y su propio
``token.json``. ``AuthPaths`` permite indicarlos explícitamente sin modificar
variables globales, de modo que varios hilos no se pisan entre sí.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from src.authentication.browsers import SYSTEM_DEFAULT, BrowserOption
from src.config import SCOPES
from src.utils.path_management import find_root_project

BASE_DIR = find_root_project()  # Obtiene la ruta de la raíz
CREDENTIALS_FILE = BASE_DIR / "credentials.json"  # Guarda la info de credentials.json
TOKEN_FILE = BASE_DIR / "token.json"  # Guarda la info de token.json

#: Nombre con el que se registra el ejecutable elegido en ``webbrowser``.
BROWSER_REGISTRY_NAME = "drive-automator"

#: Función que devuelve el navegador elegido, o ``None`` si se canceló.
BrowserProvider = Callable[[], Optional[BrowserOption]]

#: Estados locales de la sesión de un perfil.
TOKEN_STATUS_MISSING = "missing"
TOKEN_STATUS_INVALID = "invalid"
TOKEN_STATUS_VALID = "valid"
TOKEN_STATUS_REFRESHABLE = "refreshable"
TOKEN_STATUS_RECONNECT_REQUIRED = "reconnect_required"


@dataclass(frozen=True, slots=True)
class AuthPaths:
    """Archivos de autenticación de un perfil.

    Attributes:
        client_secrets: Copia administrada de ``credentials.json``.
        token: Token autorizado del perfil.
    """

    client_secrets: Path
    token: Path


class AuthenticationCancelled(Exception):
    """El usuario cerró el selector sin elegir un navegador."""


def default_auth_paths() -> AuthPaths:
    """Rutas antiguas de la raíz, usadas por la CLI y los tests."""
    return AuthPaths(CREDENTIALS_FILE, TOKEN_FILE)


def _resolve_paths(paths: AuthPaths | None) -> AuthPaths:
    """Devuelve las rutas indicadas o las de compatibilidad."""
    return paths if paths is not None else default_auth_paths()


def load_token(paths: AuthPaths | None = None):
    """Retorna credenciales del token.json (None si no existen o están rotas)."""
    token_file = _resolve_paths(paths).token
    if not token_file.exists():
        return None
    try:
        return Credentials.from_authorized_user_file(str(token_file), SCOPES)
    except (ValueError, OSError):
        # El archivo existe pero no tiene el formato esperado: se trata como
        # ausente para que el usuario pueda regenerarlo.
        return None


def refresh(creds):
    """Intentar renovar el token. Retorna las creds (None si falla)"""
    try:
        creds.refresh(Request())
        return creds
    except RefreshError:  # Invalida el permiso: refresh token vencido o revocado
        return None


def browser_flow(
    browser: BrowserOption | None = None,
    *,
    client_secrets: Path | None = None,
    login_hint: str | None = None,
):
    """Abre el navegador elegido para el flujo de autenticación completo.

    Args:
        browser: Navegador que se abrirá. Si se omite, se usa el del sistema.
        client_secrets: Archivo de credenciales del perfil. Si se omite, se
            usa el de la raíz por compatibilidad.
        login_hint: Correo que Google debe preseleccionar al reconectar.
    """
    selected = browser or SYSTEM_DEFAULT
    executable = selected.executable
    secrets_file = (
        Path(client_secrets) if client_secrets is not None else CREDENTIALS_FILE
    )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(secrets_file), SCOPES
    )

    options: dict[str, object] = {
        "port": 0,
        "prompt": "select_account",
    }
    if login_hint:
        options["login_hint"] = login_hint

    if executable is None:
        # ``browser=None`` deja que Windows use el navegador predeterminado.
        return flow.run_local_server(**options)

    webbrowser.register(
        BROWSER_REGISTRY_NAME,
        None,
        webbrowser.BackgroundBrowser([executable, "%s"]),
    )
    return flow.run_local_server(
        browser=BROWSER_REGISTRY_NAME,
        **options,
    )


def get_credentials(
    browser_provider: BrowserProvider | None = None,
    paths: AuthPaths | None = None,
    login_hint: str | None = None,
):
    """Devuelve credenciales válidas, regenerando el token si hace falta.

    Args:
        browser_provider: Se llama solo cuando hay que abrir el navegador.
            Debe devolver el navegador elegido o ``None`` si el usuario
            canceló. Si se omite, se usa el navegador predeterminado.
        paths: Archivos del perfil. Si se omite, se usan los de la raíz.
        login_hint: Correo que Google debe preseleccionar al reconectar.
    """
    resolved = _resolve_paths(paths)
    creds = load_token(resolved)

    if creds and creds.valid:
        return creds  # Retorna las credenciales si existen y aún son válidas

    if creds and creds.expired and creds.refresh_token:
        creds = refresh(creds)  # Refresca las credenciales si aún es posible

    if not creds or not creds.valid:
        browser = SYSTEM_DEFAULT
        if browser_provider is not None:
            selected = browser_provider()
            if selected is None:
                raise AuthenticationCancelled(
                    "No se eligió ningún navegador para iniciar sesión."
                )
            browser = selected
        creds = browser_flow(
            browser,
            client_secrets=resolved.client_secrets,
            login_hint=login_hint,
        )

    resolved.token.parent.mkdir(parents=True, exist_ok=True)
    resolved.token.write_text(creds.to_json(), encoding="utf-8")
    return creds  # Retorna las credenciales


def token_status(paths: AuthPaths | None = None) -> str:
    """Estado local del token de un perfil, sin abrir el navegador.

    No garantiza que el permiso siga vigente en Google: solo describe lo que
    se puede saber leyendo el archivo.
    """
    resolved = _resolve_paths(paths)
    if not resolved.token.exists():
        return TOKEN_STATUS_MISSING

    creds = load_token(resolved)
    if creds is None:
        return TOKEN_STATUS_INVALID
    if getattr(creds, "valid", False):
        return TOKEN_STATUS_VALID
    if getattr(creds, "expired", False) and getattr(
        creds, "refresh_token", None
    ):
        return TOKEN_STATUS_REFRESHABLE
    return TOKEN_STATUS_RECONNECT_REQUIRED
