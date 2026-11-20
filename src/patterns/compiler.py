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

class RenderError(ValueError):
    """Error al reconstruir el nombre de una carpeta desde un patrón."""

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
    if "/" in spec.pattern or "\\" in spec.pattern:
        raise CompileError(
            f"El patrón de '{spec.program}' no puede contener '/' ni '\\': "
            f"{spec.pattern}"
        )

    tokens = tokenize(spec.pattern)
    if not tokens:
        raise CompileError(
            f"El patrón no contiene contenido válido para '{spec.program}'"
        )

    parts: list[str] = []
    placeholders: list[str] = []
    for kind, text in tokens:
        if kind == "literal":
            parts.append(re.escape(text))
        else:
            try:
                regex_placeholder = fragment(text)
            except UnknownPlaceholderError as exc:
                raise CompileError(
                    f"Placeholder desconocido '{text}' en el patrón de "
                    f"'{spec.program}': {spec.pattern}"
                ) from exc
            # Nombre de grupo canónico (sin tildes, minúsculas) para que los
            # valores capturados sean predecibles independientemente de si el
            # usuario escribió {número} o {numero}.
            key = normalize(text)
            parts.append(f"(?P<{key}>{regex_placeholder})")
            placeholders.append(key)

    # Un placeholder no puede repetirse dentro del mismo patrón (nombres de
    # grupo duplicados en la regex).
    seen: set[str] = set()
    duplicates: list[str] = []
    for ph in placeholders:
        if ph in seen:
            duplicates.append(ph)
        seen.add(ph)
    if duplicates:
        raise CompileError(
            f"Placeholder repetido '{duplicates[0]}' en el patrón de "
            f"'{spec.program}': {spec.pattern}"
        )

    regex_str = "".join(parts)
    try:
        compiled = re.compile(regex_str, re.IGNORECASE)
    except re.error as exc:
        raise CompileError(
            f"Regex inválida al compilar: '{regex_str}' para '{spec.program}': {exc}"
        ) from exc

    return CompiledPattern(
        program=spec.program.strip(),
        source=spec.pattern,
        regex=compiled, 
        placeholders=tuple(placeholders),
    )

def compile_patterns(specs: list[PatternSpec]) -> list[CompiledPattern]:
    """Compila múltiples definiciones validando que no haya programas duplicados. 

    Actualmente un programa debe cumplir únicamente con un patrón.
    """
    compiled: list[CompiledPattern] = []
    seen_programs: set[str] = set()
    for spec in specs:
        if not isinstance(spec, PatternSpec):
            raise CompileError(
                f"Se esperaba clase de tipo PatternSpec, se recibió {type(spec).__name__}"
            )
        key_program = spec.program.strip().lower()
        if key_program in seen_programs:
            raise CompileError(f"Programa duplicado: '{spec.program}'")
        seen_programs.add(key_program)
        compiled.append(compile_pattern(spec))
    return compiled

def render_folder_name(
    compiled: CompiledPattern, values: dict[str, str]
) -> str:
    """Reconstruye el nombre de la subcarpeta a partir del patrón compilado.

    Los literales se conservan tal como se escribieron y cada placeholder se
    sustituye por el valor capturado durante el match. Así, un patrón
    ``G{número}-Power BI`` con el valor ``2`` genera siempre ``G2-Power BI``,
    sin importar cómo esté escrito el nombre del archivo original.

    Args:
        compiled: Patrón ya compilado.
        values: Valores capturados por el match, con claves canónicas.

    Returns:
        Nombre de carpeta válido, sin separadores de ruta.

    Raises:
        RenderError: Si falta un valor, el nombre queda vacío o contiene
            ``/`` o ``\\``.
    """
    if not isinstance(compiled, CompiledPattern):
        raise RenderError(
            "Se esperaba un CompiledPattern, se recibió "
            f"{type(compiled).__name__}"
        )

    parts: list[str] = []
    for kind, text in tokenize(compiled.source):
        if kind == "literal":
            parts.append(text)
            continue

        key = normalize(text)
        if key not in values:
            raise RenderError(
                f"Falta el valor del placeholder '{text}' para el patrón "
                f"de '{compiled.program}': {compiled.source}"
            )
        parts.append(str(values[key]))

    name = "".join(parts).strip()
    if not name:
        raise RenderError(
            f"El patrón de '{compiled.program}' genera un nombre de carpeta "
            f"vacío: {compiled.source}"
        )
    if "/" in name or "\\" in name:
        raise RenderError(
            f"El nombre de carpeta generado contiene un separador de ruta: "
            f"'{name}'"
        )
    return name
