from googleapiclient.discovery import build

FIELDS = "nextPageToken, files(id, name, mimeType, webViewLink, parents, owners(displayName, emailAddress))" # Campos para obtener de los archivos de Drive

# Función para validar las credenciales. Las recibe como argumento
def get_service(creds):
    return build("drive", "v3", credentials=creds) # Retorna el servicio API Drive V3 funcionando

# Lista los archivos utilizando el servicio según el query
def list_files(service, query):
    files = []
    page_token = None
    # El ciclo itera usando nextPageToken para no obtener todos los archivos en una sola petición
    while True:
        response = service.files().list(q=query, fields=FIELDS, pageSize=1000, pageToken=page_token).execute()

        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        # Si ya no existe page_token, rompe el ciclo
        if not page_token:
            break

    return files
# Lista todas las carpetas utilizando el servicio
def list_folders(service):
    folders, page_token = [], None
    while True:
        resp = service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and trashed=false", # mimeType carpeta, carpetas que no estén en papelera
            fields="nextPageToken, files(id, name, parents)", # Para cada archivo: id, nombre y carpetas padre []
            pageSize=1000, # 1000 datos de cada archivo por llamada
            pageToken=page_token,
        ).execute()
        folders += resp["files"]
        page_token = resp.get("nextPageToken")
        # Si no existe el page_token, rompe el ciclo
        if not page_token:
            break
    return folders