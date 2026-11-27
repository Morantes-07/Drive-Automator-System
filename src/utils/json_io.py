"""Lectura y escritura segura de archivos JSON de configuración.

Los perfiles de cuenta y los programas usan estos ayudantes para no repetir
el manejo de archivos corruptos ni la escritura atómica. Nunca se registran
los contenidos: pueden incluir datos sensibles.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


class JsonFileError(ValueError):
    """El archivo no existe, no se puede leer o no contiene un objeto JSON."""


def read_json_object(path: Path) -> dict[str, Any]:
    """Lee un objeto JSON del disco.

    Args:
        path: Archivo que se quiere leer.

    Returns:
        Diccionario con el contenido del archivo.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        JsonFileError: Si no se puede leer o no contiene un objeto JSON.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except (OSError, UnicodeDecodeError) as exc:
        raise JsonFileError(
            f"No se pudo leer '{path.name}'."
        ) from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JsonFileError(
            f"'{path.name}' no contiene JSON válido."
        ) from exc

    if not isinstance(data, dict):
        raise JsonFileError(
            f"'{path.name}' debe contener un objeto JSON en la raíz."
        )
    return data


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Escribe un objeto JSON de forma atómica.

    Se escribe primero en un archivo temporal de la misma carpeta y luego se
    reemplaza el destino, de modo que una interrupción no deja el archivo a
    medio escribir.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def backup_corrupt_file(path: Path) -> Path | None:
    """Renombra un archivo ilegible y devuelve la nueva ruta.

    Si el renombrado falla, devuelve ``None`` para que el llamador pueda
    continuar con valores vacíos en lugar de bloquear el arranque.
    """
    if not path.exists():
        return None

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.name}.corrupt-{stamp}")
    index = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.corrupt-{stamp}-{index}")
        index += 1

    try:
        path.replace(candidate)
    except OSError:
        return None
    return candidate
