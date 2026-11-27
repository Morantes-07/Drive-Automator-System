"""Modelo de una cuenta de Google configurada en la aplicación."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class ProfileValidationError(ValueError):
    """Los datos de un perfil no tienen el formato esperado."""


def now_iso() -> str:
    """Instante actual en UTC con formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class AccountProfile:
    """Cuenta de Google con su propio cliente OAuth y sesión.

    Attributes:
        id: Identificador estable usado para nombrar la carpeta del perfil.
        name: Nombre visible elegido por el usuario.
        email: Correo de la cuenta autenticada, si ya se conoce.
        account_name: Nombre que Google devuelve para la cuenta.
        client_id: Id del cliente OAuth leído de ``credentials.json``.
        project_id: Proyecto de Google Cloud asociado al cliente.
        created_at: Momento en que se importó el perfil.
        last_used_at: Última vez que se activó o conectó.
    """

    id: str
    name: str
    email: str | None = None
    account_name: str | None = None
    client_id: str | None = None
    project_id: str | None = None
    created_at: str = field(default_factory=now_iso)
    last_used_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", str(self.id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        if not self.id:
            raise ProfileValidationError("El id del perfil no puede estar vacío.")
        if not self.name:
            raise ProfileValidationError(
                "El nombre del perfil no puede estar vacío."
            )
        for field in ("email", "account_name", "client_id", "project_id"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, str(value).strip() or None)

    def to_dict(self) -> dict[str, Any]:
        """Representación serializable para ``profiles.json``."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "account_name": self.account_name,
            "client_id": self.client_id,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountProfile:
        """Reconstruye un perfil desde ``profiles.json``.

        Raises:
            ProfileValidationError: Si faltan campos obligatorios o tienen
                un tipo inesperado.
        """
        if not isinstance(data, dict):
            raise ProfileValidationError(
                "Cada perfil debe ser un objeto JSON."
            )

        profile_id = data.get("id")
        name = data.get("name")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ProfileValidationError("El perfil no tiene un id válido.")
        if not isinstance(name, str) or not name.strip():
            raise ProfileValidationError(
                f"El perfil '{profile_id}' no tiene un nombre válido."
            )

        optional: dict[str, str | None] = {}
        for field in (
            "email",
            "account_name",
            "client_id",
            "project_id",
            "created_at",
            "last_used_at",
        ):
            value = data.get(field)
            if value is not None and not isinstance(value, str):
                raise ProfileValidationError(
                    f"El campo '{field}' del perfil '{profile_id}' no es texto."
                )
            optional[field] = value

        return cls(
            id=profile_id,
            name=name,
            email=optional["email"],
            account_name=optional["account_name"],
            client_id=optional["client_id"],
            project_id=optional["project_id"],
            created_at=optional["created_at"] or now_iso(),
            last_used_at=optional["last_used_at"],
        )
