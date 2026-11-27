"""Operaciones de alto nivel sobre los perfiles de cuenta.

``AccountService`` coordina el registro persistente con la autenticación y
la identidad de Google. No toca Tkinter: la interfaz lo llama desde hilos de
trabajo y aplica los resultados en el hilo principal.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import replace
from pathlib import Path

from src.authentication.auth import (
    AuthPaths,
    get_credentials,
    load_token,
    refresh,
)
from src.drive.drive_client import get_service, get_user_profile
from src.utils.path_management import find_root_project

from .credentials import ClientSecretsInfo, read_client_secrets
from .models import AccountProfile, now_iso
from .store import ProfileStore


class AccountServiceError(ValueError):
    """La operación solicitada sobre una cuenta no se pudo completar."""


class AccountService:
    """Importa, conecta, valida y elimina perfiles de cuenta."""

    def __init__(
        self,
        store: ProfileStore,
        *,
        legacy_credentials: Path | None = None,
        legacy_token: Path | None = None,
    ) -> None:
        self._store = store
        base = find_root_project()
        self._legacy_credentials = (
            Path(legacy_credentials)
            if legacy_credentials is not None
            else base / "credentials.json"
        )
        self._legacy_token = (
            Path(legacy_token)
            if legacy_token is not None
            else base / "token.json"
        )
        #: Aviso no bloqueante de la última importación.
        self.last_warning: str | None = None

    # -- lectura -----------------------------------------------------------
    @property
    def store(self) -> ProfileStore:
        """Registro persistente que administra el servicio."""
        return self._store

    @property
    def active(self) -> AccountProfile | None:
        """Perfil activo, o ``None``."""
        return self._store.active

    def paths_for(self, profile_id: str) -> AuthPaths:
        """Archivos de autenticación del perfil."""
        profile = self._store.get(profile_id)
        paths = self._store.paths_for(profile.id)
        return AuthPaths(client_secrets=paths.credentials, token=paths.token)

    def active_paths(self) -> AuthPaths | None:
        """Archivos del perfil activo, si hay uno."""
        profile = self._store.active
        if profile is None:
            return None
        return self.paths_for(profile.id)

    # -- importación -------------------------------------------------------
    def import_client_secrets(
        self,
        source: Path,
        name: str | None = None,
    ) -> AccountProfile:
        """Copia un ``credentials.json`` y crea un perfil sin sesión.

        Args:
            source: Archivo elegido por el usuario. No se modifica.
            name: Nombre visible. Si se omite, se usa el proyecto o el
                nombre del archivo.

        Raises:
            ClientSecretsError: Si el archivo no es válido.
            AccountServiceError: Si no se puede copiar o registrar.
        """
        info = read_client_secrets(source)
        profile_id = self._new_profile_id()
        paths = self._store.paths_for(profile_id)
        self.last_warning = None

        existing = self._store.find_by_client_id(info.client_id)
        if existing is not None:
            self.last_warning = (
                "Estas credenciales ya están asociadas al perfil "
                f"'{existing.name}'."
            )

        try:
            paths.ensure_directory()
            self._copy_atomic(Path(source), paths.credentials)
        except OSError as exc:
            self._remove_directory(paths.directory)
            raise AccountServiceError(
                "No se pudo copiar el archivo de credenciales."
            ) from exc

        profile = AccountProfile(
            id=profile_id,
            name=self._profile_name(name, info, Path(source)),
            client_id=info.client_id,
            project_id=info.project_id,
            created_at=now_iso(),
        )
        try:
            return self._store.add(profile)
        except Exception:
            self._remove_directory(paths.directory)
            raise

    def migrate_legacy(self) -> AccountProfile | None:
        """Importa las credenciales antiguas de la raíz, si existen.

        Solo actúa cuando todavía no hay perfiles. El token antiguo se copia
        para no obligar a iniciar sesión de nuevo.
        """
        if self._store.profiles:
            return None
        if not self._legacy_credentials.exists():
            return None

        profile = self.import_client_secrets(
            self._legacy_credentials,
            name="Predeterminada",
        )
        paths = self._store.paths_for(profile.id)
        if self._legacy_token.exists():
            try:
                self._copy_atomic(self._legacy_token, paths.token)
            except OSError:
                # La cuenta queda creada y el usuario podrá reconectar.
                pass
        return self._store.set_active(profile.id)

    # -- conexión ----------------------------------------------------------
    def connect(
        self,
        profile_id: str,
        browser_provider=None,
    ) -> AccountProfile:
        """Autentica el perfil y guarda el correo detectado.

        Raises:
            AccountServiceError: Si el correo no se puede verificar o ya
                pertenece a otro perfil.
            AuthenticationCancelled: Si el usuario cierra el selector.
        """
        profile = self._store.get(profile_id)
        paths = self.paths_for(profile.id)

        credentials = get_credentials(
            browser_provider=browser_provider,
            paths=paths,
            login_hint=profile.email,
        )
        service = get_service(credentials)
        info = get_user_profile(service)

        email = info.get("email")
        if not email:
            raise AccountServiceError(
                "Google no devolvió el correo de la cuenta autenticada."
            )

        if profile.email and email.casefold() != profile.email.casefold():
            raise AccountServiceError(
                "La cuenta autenticada es "
                f"'{email}', pero este perfil era '{profile.email}'. "
                "No se modificó el perfil."
            )

        existing = self._store.find_by_email(email)
        if existing is not None and existing.id != profile.id:
            raise AccountServiceError(
                f"El correo '{email}' ya está asociado al perfil "
                f"'{existing.name}'."
            )

        updated = replace(
            profile,
            email=email,
            account_name=info.get("display_name") or profile.account_name,
            last_used_at=now_iso(),
        )
        return self._store.update(updated)

    def refresh_profile(self, profile_id: str) -> AccountProfile:
        """Comprueba y renueva el token sin abrir el navegador.

        Raises:
            AccountServiceError: Si no hay token o ya no se puede renovar.
        """
        profile = self._store.get(profile_id)
        paths = self.paths_for(profile.id)
        token = load_token(paths)

        if token is None:
            raise AccountServiceError(
                "La cuenta no tiene una sesión guardada. Pulsa 'Conectar'."
            )

        if not token.valid:
            if token.expired and token.refresh_token:
                renewed = refresh(token)
                if renewed is None:
                    raise AccountServiceError(
                        "El permiso fue revocado o venció. "
                        "Pulsa 'Conectar' para renovarlo."
                    )
                try:
                    paths.token.write_text(
                        renewed.to_json(), encoding="utf-8"
                    )
                except OSError as exc:
                    raise AccountServiceError(
                        "No se pudo guardar el token renovado."
                    ) from exc
            else:
                raise AccountServiceError(
                    "La sesión necesita reconexión. Pulsa 'Conectar'."
                )

        updated = replace(profile, last_used_at=now_iso())
        return self._store.update(updated)

    # -- mantenimiento -----------------------------------------------------
    def replace_client_secrets(
        self,
        profile_id: str,
        source: Path,
    ) -> AccountProfile:
        """Sustituye el cliente OAuth y obliga a reconectar.

        El token anterior se elimina porque fue emitido por el cliente
        anterior. Los programas de la cuenta se conservan.
        """
        profile = self._store.get(profile_id)
        info = read_client_secrets(source)
        paths = self._store.paths_for(profile.id)

        try:
            self._copy_atomic(Path(source), paths.credentials)
        except OSError as exc:
            raise AccountServiceError(
                "No se pudo reemplazar el archivo de credenciales."
            ) from exc

        try:
            paths.token.unlink(missing_ok=True)
        except OSError as exc:
            raise AccountServiceError(
                "No se pudo eliminar el token anterior."
            ) from exc

        updated = replace(
            profile,
            client_id=info.client_id,
            project_id=info.project_id,
        )
        return self._store.update(updated)

    def delete(
        self,
        profile_id: str,
        *,
        remove_files: bool = True,
    ) -> AccountProfile:
        """Elimina un perfil y sus archivos administrados.

        Los archivos originales que el usuario importó nunca se tocan.
        """
        profile = self._store.get(profile_id)
        paths = self._store.paths_for(profile.id)

        if remove_files and paths.directory.exists():
            try:
                shutil.rmtree(paths.directory)
            except OSError as exc:
                raise AccountServiceError(
                    "No se pudieron borrar los archivos del perfil."
                ) from exc

        return self._store.remove(profile.id)

    def switch(self, profile_id: str) -> AccountProfile:
        """Marca el perfil como activo y actualiza su último uso."""
        profile = self._store.set_active(profile_id)
        updated = replace(profile, last_used_at=now_iso())
        return self._store.update(updated)

    # -- ayudantes ---------------------------------------------------------
    def _new_profile_id(self) -> str:
        """Genera un id que no colisione con los existentes."""
        from .paths import generate_profile_id

        existing = {profile.id for profile in self._store.profiles}
        candidate = generate_profile_id()
        while candidate in existing:
            candidate = generate_profile_id()
        return candidate

    @staticmethod
    def _profile_name(
        requested: str | None,
        info: ClientSecretsInfo,
        source: Path,
    ) -> str:
        """Nombre visible por defecto para un perfil importado."""
        clean = str(requested or "").strip()
        if clean:
            return clean
        return info.project_id or source.stem or "Cuenta"

    @staticmethod
    def _copy_atomic(source: Path, destination: Path) -> None:
        """Copia un archivo y lo publica de forma atómica."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f"{destination.name}.tmp")
        try:
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)
        except OSError:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise

    @staticmethod
    def _remove_directory(directory: Path) -> None:
        """Borra una carpeta de perfil recién creada, sin fallar si no existe."""
        try:
            shutil.rmtree(directory)
        except OSError:
            pass
