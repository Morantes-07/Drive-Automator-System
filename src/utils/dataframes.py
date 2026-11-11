import pandas as pd

# Construcción de dataframe
def build_df(files):
    """Construcción de dataframe para reporte de archivos"""
    df = pd.DataFrame(files)
    df["owner"] = df["owners"].apply(
        lambda o: o[0]["emailAddress"] if o and isinstance(o, list) else None 
    ) # define el campo "owner" tomando el "emailAddress" del campo "owners"
    df["parent_id"] = df["parents"].apply(
        lambda p: p[0] if p and isinstance(p, list) else None
    ) # Define el campo "parent_id" desde el campo "parents"
    df = df.drop(columns=["owners", "parents"])
    return df