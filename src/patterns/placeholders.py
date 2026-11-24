"""Catálogo de placeholders permitidos en los patrones definidos por el usuario.

Un placeholder es una etiqueta entre llaves que se reemplaza por una expresión
regular durante la compilación. Por ahora se admiten tres placeholders simples:

- {número} / {numero}: uno o más dígitos (0-9).
- {letra}: una sola letra ASCII (A-Z, a-z).
- {palabra}: una o más letras y números Unicode, sin guiones ni guión bajo.
"""

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlaceholderInfo:
    """Información visible de un placeholder del catálogo.

    Attributes:
        key: Clave canónica, sin tildes y en minúsculas.
        label: Etiqueta que se muestra al usuario, entre llaves.
        fragment: Expresión regular que representa el placeholder.
        description: Explicación breve de qué captura.
        example: Ejemplo de texto que acepta.
    """

    key: str
    label: str
    fragment: str
    description: str
    example: str


#: Catálogo único del que salen tanto las expresiones regulares como la ayuda.
PLACEHOLDER_INFOS: tuple[PlaceholderInfo, ...] = (
    PlaceholderInfo(
        key="numero",
        label="{número}",
        # Uno o más números
        fragment=r"\d+",
        description="Uno o más dígitos (0-9)",
        example="12",
    ),
    PlaceholderInfo(
        key="letra",
        label="{letra}",
        # Solo letras ASCII: no admite tildes ni ñ.
        fragment=r"[A-Za-z]",
        description="Una letra ASCII (sin ñ ni tildes)",
        example="B",
    ),
    PlaceholderInfo(
        key="palabra",
        label="{palabra}",
        # \w cubre letras Unicode (tildes, ñ, etc.) y dígitos. Se excluye "_".
        fragment=r"[^\W_]+",
        description="Letras y números, sin guiones",
        example="Lección",
    ),
)

PLACEHOLDERS: dict[str, str] = {
    info.key: info.fragment for info in PLACEHOLDER_INFOS
}

PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")

class UnknownPlaceholderError(ValueError):
    """Se lanza cuando un placeholder no está registrado en el catálogo."""

def strip_accents(text: str) -> str:
    """Elimina tildes y diacríticos de una cadena."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(caracter for caracter in nfkd if not unicodedata.combining(caracter))

def normalize(name: str) -> str:
    """Devuelve la clave canónica de un placeholder (sin tildes, minúsculas)."""
    return strip_accents(name).strip().lower()

def fragment(name: str) -> str:
    """Devuelve la expresión regular asociada a un placeholder.

    Acepta tanto con tilde como sin tilde (ej. "número" y "numero").
    """
    key = normalize(name)
    if key not in PLACEHOLDERS:
        valid_ones = ", ".join(info.label for info in PLACEHOLDER_INFOS)
        raise UnknownPlaceholderError(
            f"Placeholder desconocido: '{name}'. "
            f"Placeholders válidos: {valid_ones}"
        )
    return PLACEHOLDERS[key]

def tokenize(pattern: str) -> list[tuple[str, str]]:
    """Separa un patrón en trozos literales y placeholders.

    Retorna una lista de tuplas (tipo, texto) donde tipo es "literal" o
    "placeholder" y texto es el contenido original del trozo.
    """
    tokens: list[tuple[str, str]] = []
    pos = 0
    for coincidence in PLACEHOLDER_RE.finditer(pattern):
        literal_before = pattern[pos:coincidence.start()]
        if literal_before:
            tokens.append(("literal", literal_before))
        name_placeholder = coincidence.group(1)
        tokens.append(("placeholder", name_placeholder))
        pos = coincidence.end()
    remainder = pattern[pos:]
    if remainder:
        tokens.append(("literal", remainder))
    return tokens