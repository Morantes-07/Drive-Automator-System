from src.auth import get_credentials
from src.drive_client import get_service, list_files
from src.utils import build_df, find_root

BASE_DIR = find_root()

QUERY_OWNED = (
    "'me' in owners and trashed = false "
    "and mimeType != 'application/vnd.google-apps.folder'"
)
QUERY_SHARED = (
    "sharedWithMe = true and trashed = false "
    "and mimeType != 'application/vnd.google-apps.folder'"
)

def main():
    creds = get_credentials()
    service = get_service(creds=creds)

    files = list_files(service=service, query=QUERY_OWNED)
    df = build_df(files=files)
    df.to_excel(BASE_DIR/"output"/"reporte_ejemplo.xlsx", sheet_name="Testeo Drive", index=False)


if __name__ == "__main__":
    main()