"""Ajustes que pueden cambiar mientras la aplicación está abierta.

El valor inicial de ``dry_run`` se toma de ``config.DRY_RUN``. La interfaz
puede modificarlo sin reiniciar la aplicación, pero el modo real nunca se
guarda en disco: cada arranque vuelve al valor seguro de la configuración.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeSettings:
    """Configuración mutable de la sesión actual.

    Attributes:
        dry_run: Si es ``True``, las operaciones de escritura se simulan y
            no se toca Drive.
    """

    dry_run: bool = True
