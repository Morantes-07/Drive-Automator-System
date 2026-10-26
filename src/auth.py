import webbrowser
from src.utils import find_root_project
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from src.config import SCOPES

BASE_DIR = find_root_project() # Obtiene la ruta de la raíz
CREDENTIALS_FILE = BASE_DIR / "credentials.json" # Guarda la info de credentials.json
TOKEN_FILE = BASE_DIR / "token.json" # Guarda la info de token.json
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe" # Guarda la ruta exacta del navegador que se va a utilizar. Oportunidad de mejora: El usuario lo define

def load_token():
    #Retorna credenciales del token.json (None si no existen)
    if TOKEN_FILE.exists():
        return Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    return None

def refresh(creds):
    # Intentar renovar el token. Retorna las creds (None si falla)
    try:
        creds.refresh(Request())
        return creds
    except RefreshError: #Invalida el permiso: refresh token vencido o revocado
        return None

def browser_flow():
    # Abre Chrome para el flujo de autenticación completo
    webbrowser.register(
        "chrome-incognito", None, # abre el navegador en incógnito
        webbrowser.BackgroundBrowser([CHROME, "--incognito", "%s"]),
    )
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    return flow.run_local_server(port=0, browser="chrome-incognito")

def get_credentials():
    # Devuelve las credenciales válidas independientemente del caso
    creds = load_token()

    if creds and creds.valid:
        return creds # Retorna las credenciales si existen y aún son válidas

    if creds and creds.expired and creds.refresh_token:
        creds = refresh(creds) # Refresca las credenciales si aún es posible

    if not creds or not creds.valid:
        creds = browser_flow() # Ejecuta el flujo de navegador

    TOKEN_FILE.write_text(creds.to_json()) # Sobreescribe el token.json
    return creds # Retorna las credenciales