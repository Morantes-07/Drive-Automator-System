"""Clasificación y filtrado de archivos de Drive por tipo.

Las categorías pueden solaparse a propósito: un CSV pertenece a "hojas" y
también a "texto_codigo"; un Markdown pertenece a "markdown" y a
"texto_codigo". El usuario puede seleccionar una o varias categorías y se
incluyen los archivos que coincidan con al menos una. Si no selecciona
ninguna, se incluyen todos los archivos.

El módulo es puro: no depende de la API ni de la interfaz.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Mapping

#: MimeType que Drive usa para las carpetas.
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


@dataclass(frozen=True, slots=True)
class FileTypeRules:
    """Reglas que definen una categoría de archivos.

    Attributes:
        mime_prefixes: Prefijos de mimeType (ej. ``"video/"``).
        mime_types: MimeTypes exactos (ej. ``"application/pdf"``).
        extensions: Extensiones con punto (ej. ``".mp4"``).
    """

    mime_prefixes: tuple[str, ...] = ()
    mime_types: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()


#: Categorías disponibles. El orden se usa en la interfaz.
CATEGORIES: dict[str, FileTypeRules] = {
    "videos": FileTypeRules(
        mime_prefixes=("video/",),
        mime_types=("application/vnd.google-apps.vid",),
        extensions=(
            ".mp4",
            ".mov",
            ".avi",
            ".mkv",
            ".webm",
            ".wmv",
            ".m4v",
            ".mpeg",
            ".mpg",
            ".3gp",
            ".flv",
            ".ts",
            ".mts",
            ".m2ts",
            ".ogv",
        ),
    ),
    "imagenes": FileTypeRules(
        mime_prefixes=("image/",),
        extensions=(
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".svg",
            ".tif",
            ".tiff",
            ".heic",
            ".heif",
            ".raw",
            ".cr2",
            ".nef",
            ".arw",
            ".dng",
        ),
    ),
    "audio": FileTypeRules(
        mime_prefixes=("audio/",),
        extensions=(
            ".mp3",
            ".wav",
            ".flac",
            ".aac",
            ".ogg",
            ".m4a",
            ".wma",
            ".opus",
            ".aiff",
            ".alac",
        ),
    ),
    "documentos": FileTypeRules(
        mime_types=(
            "application/vnd.google-apps.document",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/rtf",
            "text/plain",
            "application/vnd.oasis.opendocument.text",
        ),
        extensions=(".doc", ".docx", ".rtf", ".txt", ".odt"),
    ),
    "hojas": FileTypeRules(
        mime_types=(
            "application/vnd.google-apps.spreadsheet",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
            "application/vnd.oasis.opendocument.spreadsheet",
        ),
        extensions=(".xls", ".xlsx", ".csv", ".ods"),
    ),
    "presentaciones": FileTypeRules(
        mime_types=(
            "application/vnd.google-apps.presentation",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.oasis.opendocument.presentation",
        ),
        extensions=(".ppt", ".pptx", ".odp"),
    ),
    "pdf": FileTypeRules(
        mime_types=("application/pdf",),
        extensions=(".pdf",),
    ),
    "markdown": FileTypeRules(
        mime_types=("text/markdown", "text/x-markdown"),
        extensions=(".md", ".markdown", ".mdown", ".mkd"),
    ),
    "comprimidos": FileTypeRules(
        mime_types=(
            "application/zip",
            "application/x-rar-compressed",
            "application/x-7z-compressed",
            "application/gzip",
            "application/x-tar",
            "application/x-bzip2",
            "application/x-xz",
        ),
        extensions=(".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"),
    ),
    "texto_codigo": FileTypeRules(
        mime_types=(
            "application/json",
            "application/xml",
            "application/javascript",
            "application/x-python-code",
            "text/markdown",
            "text/x-markdown",
            "text/javascript",
            "text/html",
            "text/css",
            "text/xml",
            "application/x-yaml",
            "text/yaml",
            "text/x-sh",
        ),
        extensions=(
            ".txt",
            ".csv",
            ".md",
            ".markdown",
            ".mdown",
            ".mkd",
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".html",
            ".htm",
            ".css",
            ".scss",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".ini",
            ".cfg",
            ".conf",
            ".sh",
            ".bat",
            ".ps1",
            ".sql",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".cs",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".kts",
            ".r",
            ".m",
            ".lua",
            ".pl",
            ".toml",
        ),
    ),
    "otros": FileTypeRules(),
}

#: Etiquetas en español para la interfaz.
CATEGORY_LABELS: dict[str, str] = {
    "videos": "Videos",
    "imagenes": "Fotos e imágenes",
    "audio": "Audio",
    "documentos": "Documentos",
    "hojas": "Hojas de cálculo",
    "presentaciones": "Presentaciones",
    "pdf": "PDF",
    "markdown": "Markdown",
    "comprimidos": "Archivos comprimidos",
    "texto_codigo": "Texto y código",
    "otros": "Otros",
}


def is_folder(file: Mapping[str, object]) -> bool:
    """Indica si el archivo de Drive es una carpeta."""
    return (
        str(file.get("mimeType") or "").strip().lower()
        == FOLDER_MIME_TYPE
    )


def categories_of(file: Mapping[str, object]) -> set[str]:
    """Devuelve todas las categorías a las que pertenece un archivo.

    Un archivo puede pertenecer a varias categorías. Si no encaja en ninguna,
    se devuelve ``{"otros"}``. Las carpetas devuelven un conjunto vacío.
    """
    if is_folder(file):
        return set()

    mime_type = str(file.get("mimeType") or "").strip().lower()
    name = str(file.get("name") or "").strip()
    extension = os.path.splitext(name)[1].lower()

    result: set[str] = set()
    for category, rules in CATEGORIES.items():
        if category == "otros":
            continue
        if any(
            mime_type.startswith(prefix) for prefix in rules.mime_prefixes
        ):
            result.add(category)
        elif mime_type in rules.mime_types:
            result.add(category)
        elif extension and extension in rules.extensions:
            result.add(category)

    if not result:
        result.add("otros")
    return result


def filter_files(
    files: Iterable[Mapping[str, object]],
    categories: set[str] | None = None,
) -> list[Mapping[str, object]]:
    """Filtra archivos por una o varias categorías.

    Sin categorías (``None`` o conjunto vacío) se devuelven todos los archivos
    que no sean carpetas. Con categorías se devuelven los archivos que
    pertenezcan a al menos una de ellas.

    Raises:
        ValueError: Si alguna categoría no existe.
    """
    selected = set(categories or ())
    unknown = selected - set(CATEGORIES)
    if unknown:
        raise ValueError(
            "Categorías desconocidas: " + ", ".join(sorted(unknown))
        )

    result: list[Mapping[str, object]] = []
    for file in files:
        if is_folder(file):
            continue
        if not selected or categories_of(file) & selected:
            result.append(file)
    return result
