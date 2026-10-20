from googleapiclient.discovery import build

FIELDS = (
    "nextPageToken, "
    "files(id, name, mimeType, size, webViewLink, parents, "
    "owners(displayName, emailAddress))"
)

def get_service(creds):
    return build("drive", "v3", credentials=creds)

def list_files(service, query):
    files = []
    page_token = None

    while True:
        response = service.files().list(q=query, fields=FIELDS, pageSize=1000, pageToken=page_token).execute()

        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return files