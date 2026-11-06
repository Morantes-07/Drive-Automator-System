"""Compilación de definiciones de patrón en expresiones regulares reutilizables.

Cada patrón es texto literal con placeholders ({número}, {letra}, {palabra}).
El compilador escapa el texto literal, sustituye los placeholders por grupos
con nombre y compila una regex sin anclas, lista para buscarse dentro de un
nombre de archivo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .placeholders import (
    fragment,
    normalize,
    tokenize,
    UnknownPlaceholderError,
)


@dataclass(frozen=True)
class PatternSpec:
    """Definición de un patrón provista por el usuario en tiempo de ejecución.

    Attributes:
        program: Nombre del programa al que pertenece el patrón.
        pattern: Texto del patrón con placeholders, ej. "G{número}-Power BI".
    """
    program: str
    pattern: str


@dataclass(frozen=True)
class CompiledPattern:
    """Patrón ya compilado, listo para buscarse en nombres de archivo."""

    program: str
    source: str
    regex: re.Pattern[str]
    placeholders: tuple[str, ...]


class CompileError(ValueError):
    """Error al compilar una definición de patrón."""


def compile_pattern(spec: PatternSpec) -> CompiledPattern:
    """Compila un PatternSpec en una regex sin anclas, con IGNORECASE.

    El match es un substring: basta con que el patrón aparezca en cualquier
    parte del nombre de archivo.
    """
    if not spec.program or not spec.program.strip():
        raise CompileError(
            f"El programa no puede estar vacío: {spec!r}"
        )
    if not spec.pattern or not spec.pattern.strip():
        raise CompileError(
            f"El patrón no puede estar vacío para '{spec.program}'"
        )

    tokens = tokenize(spec.pattern)
    if not tokens:
        raise CompileError(
            f"El patrón no contiene contenido válido para '{spec.program}'"
        )

    partes: list[str] = []
    placeholders: list[str] = []
    for tipo, texto in tokens:
        if tipo == "literal":
            partes.append(re.escape(texto))
        else:
            try:
                regex_placeholder = fragment(texto)
            except UnknownPlaceholderError as exc:
                raise CompileError(
                    f"Placeholder desconocido '{texto}' en el patrón de "
                    f"'{spec.program}': {spec.pattern}"
                ) from exc
            # Nombre de grupo canónico (sin tildes, minúsculas) para que los
            # valores capturados sean predecibles independientemente de si el
            # usuario escribió {número} o {numero}.
            clave = normalize(texto)
            partes.append(f"(?P<{clave}>{regex_placeholder})")
            placeholders.append(clave)

    # Un placeholder no puede repetirse dentro del mismo patrón (nombres de
    # grupo duplicados en la regex).
    vistos: set[str] = set()
    duplicados: list[str] = []
    for ph in placeholders:
        if ph in vistos:
            duplicados.append(ph)
        vistos.add(ph)
    if duplicados:
        raise CompileError(
            f"Placeholder repetido '{duplicados[0]}' en el patrón de "
            f"'{spec.program}': {spec.pattern}"
        )

    regex_str = "".join(partes)
    try:
        compilada = re.compile(regex_str, re.IGNORECASE)
    except re.error as exc:
        raise CompileError(
            f"Regex inválida '{regex_str}' para '{spec.program}': {exc}"
        ) from exc

    return CompiledPattern(
        program=spec.program.strip(),
        source=spec.pattern,
        regex=compilada,
        placeholders=tuple(placeholders),
    )


def compile_patterns(specs: list[PatternSpec]) -> list[CompiledPattern]:
    """Compila múltiples definiciones validando que no haya programas duplicados.

    Un programa debe cumplir un único patrón (por ahora).
    """
    compiladas: list[CompiledPattern] = []
    programas_vistos: set[str] = set()
    for spec in specs:
        if not isinstance(spec, PatternSpec):
            raise CompileError(
                f"Se esperaba PatternSpec, se recibió {type(spec).__name__}"
            )
        clave_programa = spec.program.strip().lower()
        if clave_programa in programas_vistos:
            raise CompileError(f"Programa duplicado: '{spec.program}'")
        programas_vistos.add(clave_programa)
        compiladas.append(compile_pattern(spec))
    return compiladas
