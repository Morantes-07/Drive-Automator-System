"""Lectura y validación de archivos de credenciales de Google."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.utils.json_io import JsonFileError, read_json_object


class ClientSecretsError(ValueError):
    """El archivo no es un ``credentials.json`` de aplicación de escritorio."""


@dataclass(frozen=True, slots=True)
class ClientSecretsInfo:
    """Datos relevantes de un archivo de credenciales OAuth.

    Attributes:
        client_id: Identificador del cliente OAuth.
        client_secret: Secreto del cliente. No debe registrarse ni mostrarse.
        project_id: Proyecto de Google Cloud, si el archivo lo incluye.
        auth_type: Tipo de cliente declarado en el archivo.
    """

    client_id: str
    client_secret: str
    project_id: str | None
    auth_type: str


def read_client_secrets(path: Path) -> ClientSecretsInfo:
    """Lee un ``credentials.json`` y comprueba que sea utilizable.

    Solo se aceptan clientes de tipo *Aplicación de escritorio* (clave
    ``installed``), porque el flujo usa un servidor local. Los clientes web
    necesitan una URI de redirección registrada y suelen fallar en este flujo.

    Raises:
        ClientSecretsError: Si el archivo no existe, no es JSON válido o no
            tiene la estructura esperada.
    """
    try:
        data = read_json_object(Path(path))
    except FileNotFoundError as exc:
        raise ClientSecretsError(
            "El archivo de credenciales no existe."
        ) from exc
    except JsonFileError as exc:
        raise ClientSecretsError(str(exc)) from exc

    if "web" in data:
        raise ClientSecretsError(
            "Este archivo es de un cliente web. Crea un cliente de tipo "
            "'Aplicación de escritorio' en Google Cloud."
        )
    if "installed" not in data:
        raise ClientSecretsError(
            "El archivo no contiene credenciales de aplicación de Google."
        )

    installed = data["installed"]
    if not isinstance(installed, dict):
        raise ClientSecretsError(
            "La sección 'installed' del archivo no es válida."
        )

    client_id = installed.get("client_id")
    client_secret = installed.get("client_secret")
    if not isinstance(client_id, str) or not client_id.strip():
        raise ClientSecretsError(
            "El archivo de credenciales no tiene 'client_id'."
        )
    if not isinstance(client_secret, str) or not client_secret.strip():
        raise ClientSecretsError(
            "El archivo de credenciales no tiene 'client_secret'."
        )

    project_id = installed.get("project_id")
    if project_id is not None and not isinstance(project_id, str):
        raise ClientSecretsError(
            "El campo 'project_id' del archivo no es texto."
        )

    return ClientSecretsInfo(
        client_id=client_id.strip(),
        client_secret=client_secret.strip(),
        project_id=(project_id.strip() or None) if project_id else None,
        auth_type="installed",
    )
