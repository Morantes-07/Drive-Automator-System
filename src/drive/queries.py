"""Consultas reutilizables de la API de Google Drive."""

from __future__ import annotations

#: Archivos propios que no están en la papelera y no son carpetas.
#:
#: El filtro ``shared = false`` se aplica en el cliente (``build_plan``)
#: porque la API rechaza ``shared = false`` y ``sharedWithMe = false`` en
#: ``q`` con un error 400 "Invalid Value".
QUERY_OWNED = (
    "'me' in owners and trashed = false "
    "and mimeType != 'application/vnd.google-apps.folder'"
)

#: Archivos compartidos con el usuario (pendiente de integrar en el flujo).
QUERY_SHARED = (
    "sharedWithMe = true and trashed = false "
    "and mimeType != 'application/vnd.google-apps.folder'"
)
