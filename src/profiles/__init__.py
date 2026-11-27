"""Perfiles de cuenta de Google: metadatos, credenciales y programas."""

from .credentials import ClientSecretsError, ClientSecretsInfo, read_client_secrets
from .models import AccountProfile, ProfileValidationError, now_iso
from .paths import (
    ProfilePathError,
    ProfilePaths,
    default_data_directory,
    generate_profile_id,
    validate_profile_id,
)
from .service import AccountService, AccountServiceError
from .store import ProfileStore, ProfileStoreError

__all__ = [
    "AccountProfile",
    "AccountService",
    "AccountServiceError",
    "ClientSecretsError",
    "ClientSecretsInfo",
    "ProfilePathError",
    "ProfilePaths",
    "ProfileStore",
    "ProfileStoreError",
    "ProfileValidationError",
    "default_data_directory",
    "generate_profile_id",
    "now_iso",
    "read_client_secrets",
    "validate_profile_id",
]
