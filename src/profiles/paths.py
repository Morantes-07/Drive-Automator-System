"""Rutas de los archivos que pertenecen a un perfil de cuenta."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from src.utils.path_management import find_root_project

#: Los ids se generan con ``uuid4().hex`` y se validan antes de usarlos en
#: una ruta para impedir que un ``profiles.json`` manipulado escape de data/.
PROFILE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class ProfilePathError(ValueError):
    """El identificador del perfil no es seguro para construir una ruta."""


def generate_profile_id() -> str:
    """Genera un identificador nuevo y seguro para un perfil."""
    return uuid.uuid4().hex


def validate_profile_id(profile_id: str) -> str:
    """Comprueba que el id solo contiene caracteres seguros.

    Raises:
        ProfilePathError: Si el id está vacío o no tiene el formato esperado.
    """
    clean = str(profile_id or "").strip().lower()
    if not PROFILE_ID_PATTERN.fullmatch(clean):
        raise ProfilePathError(
            "El identificador del perfil no es válido."
        )
    return clean


def default_data_directory() -> Path:
    """Carpeta de datos de la aplicación dentro de la raíz del proyecto."""
    return find_root_project() / "data"


@dataclass(frozen=True, slots=True)
class ProfilePaths:
    """Archivos administrados por un perfil.

    Args:
        data_directory: Carpeta ``data/`` de la aplicación.
        profile_id: Identificador seguro del perfil.
    """

    data_directory: Path
    profile_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "profile_id", validate_profile_id(self.profile_id)
        )

    @property
    def directory(self) -> Path:
        """Carpeta exclusiva del perfil."""
        return self.data_directory / "profiles" / self.profile_id

    @property
    def credentials(self) -> Path:
        """Copia administrada de ``credentials.json``."""
        return self.directory / "credentials.json"

    @property
    def token(self) -> Path:
        """Token de la sesión autorizada de este perfil."""
        return self.directory / "token.json"

    @property
    def programs(self) -> Path:
        """Definiciones de programas propias de la cuenta."""
        return self.directory / "programs.json"

    def ensure_directory(self) -> Path:
        """Crea la carpeta del perfil si todavía no existe."""
        self.directory.mkdir(parents=True, exist_ok=True)
        return self.directory
