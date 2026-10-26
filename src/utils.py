from pathlib import Path
import pandas as pd

# Función para construir el dataframe resultante
def build_df(files):
    df = pd.DataFrame(files)
    df["owner"] = df["owners"].apply(
        lambda o: o[0]["emailAddress"] if o and isinstance(o, list) else None 
    ) # define el campo "owner" tomando el "emailAddress" del campo "owners"
    df["parent_id"] = df["parents"].apply(
        lambda p: p[0] if p and isinstance(p, list) else None
    ) # Define el campo "parent_id" desde el campo "parents"
    df = df.drop(columns=["owners", "parents"])
    return df
# Función que retorna la ruta de la raíz del proyecto según los marcadores: .git, .requirements.txt, .gitignore
def find_root_project(markers=(".git", "requirements.txt", ".gitignore")):
    start = Path(__file__).resolve()
    for parent in start.parents:
        if any((parent / m).exists() for m in markers):
            return parent
    raise FileNotFoundError("No se encontró la raíz del proyecto")