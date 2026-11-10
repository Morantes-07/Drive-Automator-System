"""Coincidencia de nombres de archivo contra patrones compilados.

El match es un substring (unanchored) y case-insensitive dentro de un archivo. Un archivo puede:
- coincidir con un patrón -> se asigna su programa y valores capturados;
- no coincidir con ninguno -> queda sin asignar;
- coincidir con varios patrones -> se marca como ambiguo y no se asigna nada
  (se guarda para reportarlo, sin mover nada en esta versión).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .compiler import CompiledPattern

@dataclass(frozen=True)
class FileMatch:
    """Resultado de intentar encajar un nombre de archivo con un programa."""

    file_name: str
    status: str  # "matched" | "ambiguous" | "unmatched"
    program: str | None = None
    values: dict[str, str] = field(default_factory=dict)
    candidates: tuple[str, ...] = field(default_factory=tuple)

@dataclass(frozen=True)
class MatchReport:
    """Agrupa los resultados de cotejar varios archivos contra patrones."""

    results: tuple[FileMatch, ...]

    @property
    def matched(self) -> list[FileMatch]:
        """Archivos que coincidieron con exactamente un programa."""
        return [r for r in self.results if r.status == "matched"]

    @property
    def ambiguous(self) -> list[FileMatch]:
        """Archivos que coincidieron con varios programas (sin asignar)."""
        return [r for r in self.results if r.status == "ambiguous"]

    @property
    def unmatched(self) -> list[FileMatch]:
        """Archivos que no coincidieron con ningún programa."""
        return [r for r in self.results if r.status == "unmatched"]

def match_file(file_name: str, patterns: list[CompiledPattern]) -> FileMatch:
    """Busca el patrón que coincide con el nombre de archivo.

    - 0 coincidencias -> unmatched.
    - 1 coincidencia -> matched con programa y valores capturados.
    - >=2 coincidencias -> ambiguous, sin asignar programa.
    """
    hits: list[tuple[CompiledPattern, re.Match[str]]] = []
    for pattern in patterns:
        coincidence = pattern.regex.search(file_name)
        if coincidence:
            hits.append((pattern, coincidence))

    if not hits:
        return FileMatch(file_name=file_name, status="unmatched")

    if len(hits) == 1:
        pattern, coincidence = hits[0]
        return FileMatch(
            file_name=file_name,
            status="matched",
            program=pattern.program,
            values=coincidence.groupdict(),
        )

    return FileMatch(
        file_name=file_name,
        status="ambiguous",
        candidates=tuple(p.program for p, _ in hits),
    )

def match_files(
    file_names: list[str], patterns: list[CompiledPattern]
) -> MatchReport:
    """Coteja varios nombres de archivo contra los patrones compilados."""
    results = tuple(
        match_file(name, patterns) for name in file_names
    )
    return MatchReport(results=results)