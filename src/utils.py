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
    return df.drop(columns=["owners", "parents"])