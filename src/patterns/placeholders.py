"""Catálogo de placeholders permitidos en los patrones definidos por el usuario.

Un placeholder es una etiqueta entre llaves que se reemplaza por una expresión
regular durante la compilación. Por ahora se admiten tres placeholders simples:

- {número} / {numero}: uno o más dígitos (0-9).
- {letra}: una sola letra, mayúscula o minúscula.
- {palabra}: una o más letras y números, sin guiones.
"""

import re
import unicodedata


PLACEHOLDERS: dict[str, str] = {
    "numero": r"\d+",
    "letra": r"[A-Za-z]",
    "palabra": r"[A-Za-z0-9]+",
}

_PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")


class UnknownPlaceholderError(ValueError):
    """Se lanza cuando un placeholder no está registrado en el catálogo."""


def _strip_accents(text: str) -> str:
    """Elimina tildes y diacríticos de una cadena."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(caracter for caracter in nfkd if not unicodedata.combining(caracter))


def normalize(name: str) -> str:
    """Devuelve la clave canónica de un placeholder (sin tildes, minúsculas)."""
    return _strip_accents(name).strip().lower()


def fragment(name: str) -> str:
    """Devuelve la expresión regular asociada a un placeholder.

    Acepta tanto con tilde como sin tilde (ej. "número" y "numero").
    """
    clave = normalize(name)
    if clave not in PLACEHOLDERS:
        validos = ", ".join(sorted(PLACEHOLDERS))
        raise UnknownPlaceholderError(
            f"Placeholder desconocido: '{name}'. "
            f"Placeholderes válidos: {validos}"
        )
    return PLACEHOLDERS[clave]


def tokenize(pattern: str) -> list[tuple[str, str]]:
    """Separa un patrón en trozos literales y placeholders.

    Retorna una lista de tuplas (tipo, texto) donde tipo es "literal" o
    "placeholder" y texto es el contenido original del trozo.
    """
    tokens: list[tuple[str, str]] = []
    pos = 0
    for coincidencia in _PLACEHOLDER_RE.finditer(pattern):
        literal_antes = pattern[pos:coincidencia.start()]
        if literal_antes:
            tokens.append(("literal", literal_antes))
        nombre_placeholder = coincidencia.group(1)
        tokens.append(("placeholder", nombre_placeholder))
        pos = coincidencia.end()
    resto = pattern[pos:]
    if resto:
        tokens.append(("literal", resto))
    return tokens
