"""Flujo de consola: reporte de los archivos propios en un Excel.

Se mantiene como alternativa a la interfaz gráfica (``python -m src.main
--cli``) y conserva el comportamiento original.
"""

from src.authentication.auth import get_credentials
from src.drive.drive_client import get_service, list_files
from src.utils.dataframes import build_df
from src.utils.path_management import find_root_project

BASE_DIR = find_root_project()  # Carpeta raíz del proyecto

# Query de archivos propios
QUERY_OWNED = (
    "'me' in owners and trashed = false "
    "and mimeType != 'application/vnd.google-apps.folder'"
)
# Query de archivos compartidos (pendiente de integrar en el flujo)
QUERY_SHARED = (
    "sharedWithMe = true and trashed = false "
    "and mimeType != 'application/vnd.google-apps.folder'"
)


def run_cli() -> None:
    """Descarga los archivos propios y genera el reporte de ejemplo."""
    credentials = get_credentials()
    service = get_service(creds=credentials)

    files = list_files(service=service, query=QUERY_OWNED)
    df = build_df(files=files)
    df.to_excel(
        BASE_DIR / "output" / "reporte_ejemplo.xlsx",
        sheet_name="Testeo Drive",
        index=False,
    )
    print(f"Reporte generado con {len(df)} archivos.")
