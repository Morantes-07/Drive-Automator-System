"""Programas configurables: patrón de archivos y carpeta destino."""

from .models import ProgramDefinition
from .persistence import (
    ProgramLoadResult,
    ProgramPersistenceError,
    ProgramRepository,
)
from .store import ProgramStore, ProgramStoreError

__all__ = [
    "ProgramDefinition",
    "ProgramLoadResult",
    "ProgramPersistenceError",
    "ProgramRepository",
    "ProgramStore",
    "ProgramStoreError",
]
