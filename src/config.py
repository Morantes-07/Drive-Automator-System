# Permisos concedidos: Google Drive Completo y Google Sheets
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]
# True: simular proceso, no mover nada realmente, reporta qué haría
# False: mueve los archivos de verdad. Cambiarse cuando ya se confirme que funcionará bien
DRY_RUN = True