"""Persistencia de los programas de una cuenta en ``programs.json``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.patterns.compiler import CompileError, compile_patterns
from src.utils.json_io import (
    JsonFileError,
    backup_corrupt_file,
    read_json_object,
    write_json_atomic,
)

from .models import ProgramDefinition

#: Versión del formato de ``programs.json``.
PROGRAMS_VERSION = 1


class ProgramPersistenceError(ValueError):
    """No se pudo leer o escribir el archivo de programas."""


@dataclass(frozen=True, slots=True)
class ProgramLoadResult:
    """Resultado de cargar los programas de un perfil.

    Attributes:
        items: Definiciones válidas, en el mismo orden del archivo.
        errors: Mensajes legibles de las entradas que se omitieron.
    """

    items: tuple[ProgramDefinition, ...]
    errors: tuple[str, ...]


class ProgramRepository:
    """Lee y escribe los programas de un perfil concreto."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        """Archivo ``programs.json`` que administra este repositorio."""
        return self._path

    def load(self) -> ProgramLoadResult:
        """Carga las definiciones, omitiendo las entradas inválidas.

        Un archivo corrupto se guarda como copia y se devuelve un registro
        vacío para que la cuenta siga siendo utilizable.
        """
        try:
            data = read_json_object(self._path)
        except FileNotFoundError:
            return ProgramLoadResult(items=(), errors=())
        except JsonFileError as exc:
            backup = backup_corrupt_file(self._path)
            message = str(exc)
            if backup is not None:
                message += f" Se guardó una copia en '{backup.name}'."
            return ProgramLoadResult(items=(), errors=(message,))

        version = data.get("version", PROGRAMS_VERSION)
        if not isinstance(version, int) or version > PROGRAMS_VERSION:
            return ProgramLoadResult(
                items=(),
                errors=("La versión de programs.json no es compatible.",),
            )

        entries = data.get("programs", [])
        if not isinstance(entries, list):
            return ProgramLoadResult(
                items=(),
                errors=("La lista de programas no es válida.",),
            )

        items: list[ProgramDefinition] = []
        errors: list[str] = []
        seen: set[str] = set()
        for index, entry in enumerate(entries):
            try:
                definition = self._read_definition(entry)
            except ProgramPersistenceError as exc:
                errors.append(f"Programa {index + 1}: {exc}")
                continue

            key = definition.program.casefold()
            if key in seen:
                errors.append(
                    f"Programa {index + 1}: nombre duplicado "
                    f"'{definition.program}'."
                )
                continue
            seen.add(key)
            items.append(definition)

        return ProgramLoadResult(items=tuple(items), errors=tuple(errors))

    def save(self, items: Iterable[ProgramDefinition]) -> None:
        """Guarda las definiciones de forma atómica.

        Raises:
            ProgramPersistenceError: Si alguna definición no es válida o el
                archivo no se puede escribir.
        """
        definitions = list(items)
        for definition in definitions:
            if not isinstance(definition, ProgramDefinition):
                raise ProgramPersistenceError(
                    "Se esperaba una definición de programa."
                )

        try:
            write_json_atomic(
                self._path,
                {
                    "version": PROGRAMS_VERSION,
                    "programs": [
                        definition.to_dict() for definition in definitions
                    ],
                },
            )
        except OSError as exc:
            raise ProgramPersistenceError(
                "No se pudo guardar el archivo de programas."
            ) from exc

    @staticmethod
    def _read_definition(entry: object) -> ProgramDefinition:
        """Convierte una entrada JSON en una definición validada."""
        if not isinstance(entry, dict):
            raise ProgramPersistenceError("la entrada no es un objeto JSON.")

        program = entry.get("program")
        pattern = entry.get("pattern")
        destination_path = entry.get("destination_path")
        destination_id = entry.get("destination_id")

        if not isinstance(program, str) or not program.strip():
            raise ProgramPersistenceError("el nombre del programa está vacío.")
        if not isinstance(pattern, str) or not pattern.strip():
            raise ProgramPersistenceError(
                f"el patrón de '{program}' está vacío."
            )
        if not isinstance(destination_path, str) or not destination_path.strip():
            raise ProgramPersistenceError(
                f"la carpeta destino de '{program}' está vacía."
            )
        if destination_id is not None and not isinstance(destination_id, str):
            raise ProgramPersistenceError(
                f"el id de destino de '{program}' no es texto."
            )

        definition = ProgramDefinition(
            program=program,
            pattern=pattern,
            destination_path=destination_path,
            destination_id=destination_id,
        )
        try:
            compile_patterns([definition.to_spec()])
        except CompileError as exc:
            raise ProgramPersistenceError(str(exc)) from exc
        return definition
