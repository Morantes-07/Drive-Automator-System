from googleapiclient.discovery import build

FIELDS = "nextPageToken, files(id, name, mimeType, webViewLink, parents, shared, owners(displayName, emailAddress))" # Campos para obtener de los archivos de Drive

def get_service(creds):
    """Validar las credenciales. Las recibe como argumento"""
    return build("drive", "v3", credentials=creds) # Retorna el servicio API Drive V3 funcionando

def list_files(service, query):
    """Lista los archivos utilizando el servicio según el query"""
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

def list_folders(service):
    """Lista todas las carpetas utilizando el servicio"""
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

def get_root_id(service):
    """Obtener el ID de la carpeta Root del Drive"""
    return service.files().get(fileId="root", fields="id").execute()["id"]

def create_folder(service, name, parent_id):
    """Crea una carpeta en Drive y devuelve sus datos básicos.

    Args:
        service: Servicio de Drive autenticado.
        name: Nombre de la carpeta.
        parent_id: Id de la carpeta que la contendrá.

    Returns:
        Diccionario con ``id``, ``name`` y ``parents`` de la carpeta creada.

    Raises:
        ValueError: Si el nombre o el padre están vacíos.
    """
    clean_name = str(name or "").strip()
    clean_parent = str(parent_id or "").strip()
    if not clean_name:
        raise ValueError("El nombre de la carpeta no puede estar vacío.")
    if not clean_parent:
        raise ValueError("La carpeta padre es obligatoria.")

    body = {
        "name": clean_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [clean_parent],
    }
    return (
        service.files()
        .create(body=body, fields="id, name, parents")
        .execute()
    )

def move_file(service, file_id, new_parent_id, old_parent_ids):
    """Mueve un archivo a otra carpeta de Drive.

    Args:
        service: Servicio de Drive autenticado.
        file_id: Id del archivo que se va a mover.
        new_parent_id: Id de la carpeta destino.
        old_parent_ids: Carpetas actuales del archivo. Se omiten las que
            coincidan con el destino.

    Returns:
        Diccionario con ``id``, ``name`` y ``parents`` del archivo movido.

    Raises:
        ValueError: Si el archivo o la carpeta destino están vacíos.
    """
    clean_file = str(file_id or "").strip()
    clean_parent = str(new_parent_id or "").strip()
    if not clean_file:
        raise ValueError("El id del archivo es obligatorio.")
    if not clean_parent:
        raise ValueError("La carpeta destino es obligatoria.")

    parents = [
        str(parent_id).strip()
        for parent_id in (old_parent_ids or ())
        if str(parent_id).strip() and str(parent_id).strip() != clean_parent
    ]

    params = {
        "fileId": clean_file,
        "addParents": clean_parent,
        "fields": "id, name, parents",
    }
    if parents:
        params["removeParents"] = ",".join(parents)
    return service.files().update(**params).execute()
