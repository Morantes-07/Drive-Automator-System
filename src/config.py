# Permisos concedidos: Google Drive Completo y Google Sheetsclear
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]
# True: simular proceso, no mover nada realmente, reporta qué haría
# False: mueve los archivos de verdad. Este es el valor inicial de cada
# La pestaña Organización puede cambiarlo en caliente, pero el modo inicial no se cambia nunca en disco
DRY_RUN = True