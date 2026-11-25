"""Autenticación OAuth con Google Drive.

El flujo de navegador solo se ejecuta cuando no hay un token válido ni se
puede refrescar. En ese momento se pregunta al usuario qué navegador abrir.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable
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


class AuthenticationCancelled(Exception):
    """El usuario cerró el selector sin elegir un navegador."""


def load_token():
    """Retorna credenciales del token.json (None si no existen o están rotas)."""
    if not TOKEN_FILE.exists():
        return None
    try:
        return Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    except ValueError:
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


def browser_flow(browser: BrowserOption | None = None):
    """Abre el navegador elegido para el flujo de autenticación completo."""
    selected = browser or SYSTEM_DEFAULT
    executable = selected.executable
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)

    if executable is None:
        # ``browser=None`` deja que Windows use el navegador predeterminado.
        return flow.run_local_server(port=0, prompt="select_account")

    webbrowser.register(
        BROWSER_REGISTRY_NAME,
        None,
        webbrowser.BackgroundBrowser([executable, "%s"]),
    )
    return flow.run_local_server(
        port=0,
        browser=BROWSER_REGISTRY_NAME,
        prompt="select_account",
    )


def get_credentials(browser_provider: BrowserProvider | None = None):
    """Devuelve credenciales válidas, regenerando el token si hace falta.

    Args:
        browser_provider: Se llama solo cuando hay que abrir el navegador.
            Debe devolver el navegador elegido o ``None`` si el usuario
            canceló. Si se omite, se usa el navegador predeterminado.
    """
    creds = load_token()

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
        creds = browser_flow(browser)

    TOKEN_FILE.write_text(creds.to_json())  # Sobreescribe el token.json
    return creds  # Retorna las credenciales
