"""Persistencia de los perfiles de cuenta en ``data/profiles.json``."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from src.utils.json_io import (
    JsonFileError,
    backup_corrupt_file,
    read_json_object,
    write_json_atomic,
)

from .models import AccountProfile, ProfileValidationError
from .paths import (
    ProfilePathError,
    ProfilePaths,
    default_data_directory,
    validate_profile_id,
)

#: Versión del formato de ``profiles.json``.
PROFILES_VERSION = 1


class ProfileStoreError(ValueError):
    """Operación inválida sobre el registro de perfiles."""


class ProfileStore:
    """Registro en disco de las cuentas configuradas.

    El archivo solo guarda metadatos: los tokens y credenciales viven en la
    carpeta de cada perfil y nunca se incluyen en el JSON.
    """

    def __init__(self, data_directory: Path | None = None) -> None:
        self._data_directory = (
            Path(data_directory)
            if data_directory is not None
            else default_data_directory()
        )
        self._path = self._data_directory / "profiles.json"
        self._profiles: list[AccountProfile] = []
        self._active_id: str | None = None
        self.last_load_error: str | None = None
        self.load()

    # -- lectura -----------------------------------------------------------
    @property
    def data_directory(self) -> Path:
        """Carpeta ``data/`` usada por la aplicación."""
        return self._data_directory

    @property
    def path(self) -> Path:
        """Archivo ``profiles.json``."""
        return self._path

    @property
    def profiles(self) -> tuple[AccountProfile, ...]:
        """Copia inmutable de los perfiles registrados."""
        return tuple(self._profiles)

    def __len__(self) -> int:
        return len(self._profiles)

    def __iter__(self) -> Iterator[AccountProfile]:
        return iter(tuple(self._profiles))

    @property
    def active_id(self) -> str | None:
        """Id del perfil activo, o ``None`` si no hay ninguno."""
        return self._active_id

    @property
    def active(self) -> AccountProfile | None:
        """Perfil activo, o ``None``."""
        if self._active_id is None:
            return None
        return self.get(self._active_id)

    def get(self, profile_id: str) -> AccountProfile:
        """Perfil con ese id.

        Raises:
            KeyError: Si no existe.
        """
        clean = str(profile_id).strip()
        for profile in self._profiles:
            if profile.id == clean:
                return profile
        raise KeyError(f"No existe el perfil '{profile_id}'.")

    def find_by_email(self, email: str | None) -> AccountProfile | None:
        """Perfil que ya usa ese correo, sin distinguir mayúsculas."""
        if not email:
            return None
        key = email.strip().casefold()
        for profile in self._profiles:
            if profile.email and profile.email.casefold() == key:
                return profile
        return None

    def find_by_client_id(self, client_id: str | None) -> AccountProfile | None:
        """Perfil que ya usa ese cliente OAuth."""
        if not client_id:
            return None
        for profile in self._profiles:
            if profile.client_id == client_id:
                return profile
        return None

    def paths_for(self, profile_id: str) -> ProfilePaths:
        """Rutas administradas del perfil.

        Raises:
            ProfilePathError: Si el id no es seguro.
        """
        validate_profile_id(profile_id)
        return ProfilePaths(self._data_directory, profile_id)

    # -- escritura ---------------------------------------------------------
    def load(self) -> None:
        """Carga el registro desde disco.

        Si el archivo está corrupto se guarda una copia y se arranca vacío.
        Los perfiles inválidos se omiten para que un error aislado no impida
        usar el resto.
        """
        self._profiles = []
        self._active_id = None
        self.last_load_error = None

        try:
            data = read_json_object(self._path)
        except FileNotFoundError:
            return
        except JsonFileError as exc:
            backup = backup_corrupt_file(self._path)
            self.last_load_error = str(exc)
            if backup is not None:
                self.last_load_error += f" Se guardó una copia en '{backup.name}'."
            return

        version = data.get("version", PROFILES_VERSION)
        if not isinstance(version, int) or version > PROFILES_VERSION:
            self.last_load_error = (
                "La versión de profiles.json no es compatible."
            )
            return

        entries = data.get("profiles", [])
        if not isinstance(entries, list):
            self.last_load_error = "La lista de perfiles no es válida."
            return

        errors: list[str] = []
        seen: set[str] = set()
        for index, entry in enumerate(entries):
            try:
                profile = AccountProfile.from_dict(entry)
                validate_profile_id(profile.id)
            except (ProfileValidationError, ProfilePathError) as exc:
                errors.append(f"Perfil {index + 1}: {exc}")
                continue
            if profile.id in seen:
                errors.append(
                    f"Perfil {index + 1}: id duplicado '{profile.id}'."
                )
                continue
            seen.add(profile.id)
            self._profiles.append(profile)

        active_id = data.get("active_id")
        if isinstance(active_id, str) and active_id in seen:
            self._active_id = active_id

        if errors:
            self.last_load_error = " ".join(errors)

    def save(self) -> None:
        """Escribe el registro completo de forma atómica."""
        write_json_atomic(
            self._path,
            {
                "version": PROFILES_VERSION,
                "active_id": self._active_id,
                "profiles": [profile.to_dict() for profile in self._profiles],
            },
        )

    def add(self, profile: AccountProfile) -> AccountProfile:
        """Añade un perfil nuevo.

        Raises:
            ProfileStoreError: Si el id ya existe o el perfil no es válido.
        """
        if not isinstance(profile, AccountProfile):
            raise ProfileStoreError("Se esperaba un perfil de cuenta.")
        if any(item.id == profile.id for item in self._profiles):
            raise ProfileStoreError(
                f"Ya existe un perfil con el id '{profile.id}'."
            )
        self._profiles.append(profile)
        self.save()
        return profile

    def update(self, profile: AccountProfile) -> AccountProfile:
        """Reemplaza los datos de un perfil existente."""
        if not isinstance(profile, AccountProfile):
            raise ProfileStoreError("Se esperaba un perfil de cuenta.")
        for index, item in enumerate(self._profiles):
            if item.id == profile.id:
                self._profiles[index] = profile
                self.save()
                return profile
        raise ProfileStoreError(f"No existe el perfil '{profile.id}'.")

    def remove(self, profile_id: str) -> AccountProfile:
        """Elimina un perfil del registro y devuelve sus datos.

        Si era el activo, el registro queda sin cuenta activa. Los archivos
        administrados se borran en ``AccountService``.
        """
        for index, item in enumerate(self._profiles):
            if item.id == profile_id:
                removed = self._profiles.pop(index)
                if self._active_id == removed.id:
                    self._active_id = None
                self.save()
                return removed
        raise ProfileStoreError(f"No existe el perfil '{profile_id}'.")

    def set_active(self, profile_id: str) -> AccountProfile:
        """Marca un perfil como activo y guarda el cambio."""
        profile = self.get(profile_id)
        self._active_id = profile.id
        self.save()
        return profile
