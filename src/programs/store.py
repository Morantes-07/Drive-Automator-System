"""Registro en memoria de los programas configurados.

El registro valida cada definición (programa único, patrón compilable y
carpeta destino informada) y sirve de puente con ``src.patterns``: de aquí
salen los ``PatternSpec`` y los patrones compilados que usará el organizador.
"""

from __future__ import annotations

from src.patterns.compiler import (
    CompiledPattern,
    CompileError,
    PatternSpec,
    compile_patterns,
)

from .models import ProgramDefinition


class ProgramStoreError(ValueError):
    """Error de validación del registro de programas."""


class ProgramStore:
    """Lista ordenada de programas, sin duplicados por nombre."""

    def __init__(self) -> None:
        self._items: list[ProgramDefinition] = []

    # -- lectura -----------------------------------------------------------
    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(tuple(self._items))

    def items(self) -> tuple[ProgramDefinition, ...]:
        """Copia inmutable de los programas registrados."""
        return tuple(self._items)

    def get(self, index: int) -> ProgramDefinition:
        """Programa en esa posición (``IndexError`` si no existe)."""
        return self._items[index]

    def index_of(self, program: str) -> int | None:
        """Posición del programa con ese nombre, sin distinguir mayúsculas."""
        key = str(program).strip().casefold()
        for index, item in enumerate(self._items):
            if item.program.casefold() == key:
                return index
        return None

    def specs(self) -> list[PatternSpec]:
        """Definiciones listas para ``compile_patterns``."""
        return [item.to_spec() for item in self._items]

    def compiled(self) -> list[CompiledPattern]:
        """Patrones compilados de todos los programas registrados."""
        return compile_patterns(self.specs())

    # -- escritura ---------------------------------------------------------
    def add(self, definition: ProgramDefinition) -> ProgramDefinition:
        """Añade un programa validando que no exista otro con ese nombre."""
        self._validate(definition)
        self._items.append(definition)
        return definition

    def update(self, index: int, definition: ProgramDefinition) -> ProgramDefinition:
        """Reemplaza el programa de esa posición."""
        if not 0 <= index < len(self._items):
            raise IndexError(f"Programa fuera de rango: {index}")
        self._validate(definition, ignore_index=index)
        self._items[index] = definition
        return definition

    def remove(self, index: int) -> ProgramDefinition:
        """Elimina y devuelve el programa de esa posición."""
        if not 0 <= index < len(self._items):
            raise IndexError(f"Programa fuera de rango: {index}")
        return self._items.pop(index)

    def clear(self) -> None:
        """Vacía el registro."""
        self._items.clear()

    # -- validación --------------------------------------------------------
    def _validate(
        self,
        definition: ProgramDefinition,
        ignore_index: int | None = None,
    ) -> None:
        if not isinstance(definition, ProgramDefinition):
            raise ProgramStoreError(
                "Se esperaba una definición de programa, se recibió "
                f"{type(definition).__name__}"
            )
        if not definition.program:
            raise ProgramStoreError("El nombre del programa no puede estar vacío.")
        if not definition.pattern:
            raise ProgramStoreError(
                f"El patrón de '{definition.program}' no puede estar vacío."
            )
        if not definition.destination_path:
            raise ProgramStoreError(
                f"La carpeta destino de '{definition.program}' no puede estar vacía."
            )

        try:
            compile_patterns([definition.to_spec()])
        except CompileError as exc:
            raise ProgramStoreError(str(exc)) from exc

        existing = self.index_of(definition.program)
        if existing is not None and existing != ignore_index:
            raise ProgramStoreError(
                f"Ya existe un programa llamado '{definition.program}'."
            )
