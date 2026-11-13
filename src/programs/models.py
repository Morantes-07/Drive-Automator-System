"""Definición de un programa: patrón de nombre y carpeta destino."""

from __future__ import annotations

from dataclasses import dataclass

from src.patterns.compiler import PatternSpec


@dataclass(frozen=True, slots=True)
class ProgramDefinition:
    """Programa configurado por el usuario en tiempo de ejecución.

    Attributes:
        program: Nombre del programa (por ejemplo, "Power BI").
        pattern: Patrón de nombre de archivo con placeholders.
        destination_path: Ruta lógica de la carpeta destino, tal como se
            muestra en la interfaz (por ejemplo, "Mi Drive/Power BI/2024").
        destination_id: Id de Drive de la carpeta destino, si se eligió con el
            selector. Puede ser None cuando la ruta se escribió a mano.
    """

    program: str
    pattern: str
    destination_path: str
    destination_id: str | None = None

    def __post_init__(self) -> None:
        # Los campos se normalizan al construir para que el resto del código no
        # tenga que repetir los mismos strip.
        object.__setattr__(self, "program", str(self.program).strip())
        object.__setattr__(self, "pattern", str(self.pattern).strip())
        object.__setattr__(
            self, "destination_path", str(self.destination_path).strip()
        )

    def to_spec(self) -> PatternSpec:
        """Convierte la definición en el patrón que consume el compilador."""
        return PatternSpec(program=self.program, pattern=self.pattern)
