"""Lógica de sugerencias de placeholders para el campo de patrón.

El módulo no depende de Tk: detecta si el cursor está dentro de un ``{…}``,
filtra el catálogo y calcula el texto resultante al aceptar una sugerencia.
"""

from __future__ import annotations

from dataclasses import dataclass

from .placeholders import PLACEHOLDER_INFOS, PlaceholderInfo, normalize


@dataclass(frozen=True, slots=True)
class PlaceholderQuery:
    """Placeholder que se está escribiendo en la posición del cursor.

    Attributes:
        start: Índice del ``{`` que abre el placeholder.
        caret: Posición del cursor dentro del patrón.
        text: Texto escrito entre ``{`` y el cursor.
        close: Índice del ``}`` que cierra el placeholder, si ya existe.
    """

    start: int
    caret: int
    text: str
    close: int | None = None


def find_placeholder_query(text: str, caret: int) -> PlaceholderQuery | None:
    """Devuelve el placeholder abierto en la posición del cursor.

    Solo hay consulta si el último ``{`` anterior al cursor no tiene un ``}``
    entre medias. Si el cursor está dentro de un placeholder ya cerrado,
    ``close`` apunta a su ``}`` para poder reemplazar el token completo.
    """
    caret = max(0, min(caret, len(text)))
    start = text.rfind("{", 0, caret)
    if start == -1:
        return None
    if "}" in text[start + 1 : caret]:
        return None

    close = text.find("}", caret)
    next_open = text.find("{", caret)
    if close == -1 or (next_open != -1 and next_open < close):
        # El token no está cerrado o hay otra apertura antes del cierre.
        close = None

    return PlaceholderQuery(
        start=start,
        caret=caret,
        text=text[start + 1 : caret],
        close=close,
    )


def suggest_placeholders(query: PlaceholderQuery) -> list[PlaceholderInfo]:
    """Filtra el catálogo por el texto escrito detrás de ``{``.

    La comparación ignora tildes y mayúsculas, y funciona por prefijo.
    """
    if not query.text:
        return list(PLACEHOLDER_INFOS)
    needle = normalize(query.text)
    if not needle:
        return []
    return [
        info
        for info in PLACEHOLDER_INFOS
        if info.key.startswith(needle)
    ]


def apply_suggestion(
    text: str,
    query: PlaceholderQuery,
    info: PlaceholderInfo,
) -> tuple[str, int]:
    """Sustituye el placeholder en curso por el elegido.

    Returns:
        El texto nuevo y la posición del cursor después de la etiqueta.
    """
    end = query.close + 1 if query.close is not None else query.caret
    new_text = f"{text[:query.start]}{info.label}{text[end:]}"
    return new_text, query.start + len(info.label)


def move_selection(index: int, delta: int, count: int) -> int:
    """Devuelve el índice resaltado tras moverlo ``delta`` posiciones."""
    if count <= 0:
        return -1
    return max(0, min(index + delta, count - 1))
