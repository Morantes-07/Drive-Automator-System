from googleapiclient.discovery import build

FIELDS = "nextPageToken, files(id, name, mimeType, webViewLink, parents, owners(displayName, emailAddress))"

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

def list_folders(service):
    folders, token = [], None
    while True:
        resp = service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="nextPageToken, files(id, name, parents)",
            pageSize=1000,
            pageToken=token,
        ).execute()
        folders += resp["files"]
        token = resp.get("nextPageToken")
        if not token:
            break
    return folders