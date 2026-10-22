from pathlib import Path
import pandas as pd

# Función para construir el dataframe resultante
def build_df(files):
    df = pd.DataFrame(files)
    df["owner"] = df["owners"].apply(
        lambda o: o[0]["emailAddress"] if o and isinstance(o, list) else None 
    )
    df["size"] = pd.to_numeric(df.get("size"), errors="coerce")
    df["parent_id"] = df["parents"].apply(
        lambda p: p[0] if p and isinstance(p, list) else None
    )
    df = df.drop(columns=["owners", "parents"])
    return df

def find_root(markers=(".git", "requirements.txt", ".gitignore")):
    start = Path(__file__).resolve()
    for parent in start.parents:
        if any((parent / m).exists() for m in markers):
            return parent
    raise FileNotFoundError("No se encontró la raíz del proyecto")