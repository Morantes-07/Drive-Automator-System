from google_auth_oauthlib.flow import InstalledAppFlow
import webbrowser
from src.config import SCOPES

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

webbrowser.register(
    "chrome-incognito", None,
    webbrowser.BackgroundBrowser([CHROME, "--incognito", "%s"]),
)

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0, browser="chrome-incognito")

with open("token.json", "w") as f:
    f.write(creds.to_json())