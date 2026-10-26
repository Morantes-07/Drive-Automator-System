from collections import defaultdict
# Construye un diccionario para obtener los hijos de cada carpeta: recibe folders (id, name, parents[])
def build_children(folders):
    # Utiliza defaultdict(list) para definir como lista vacía a cada padre que aún no tiene hijos
    children = defaultdict(list)
    # Recorre cada carpeta
    for f in folders:
        # Toma la lista de padres de cada carpeta
        for p in f.get("parents", []): 
            children[p].append(f) # Crea el padre "p" con cada hijo "f"
    return children
 # Saber si una carpeta restá repetida, no existe o aparece una única vez en su carpeta base
def find_unique(children, father_id, name, path):
    c = [f for f in children.get(father_id, []) if f["name"] == name]
    if not c: # Error cuando no existe la carpeta buscada
        raise ValueError(f"No existe '{name}' en '{path}'") # Futura mejora: avisar al usuario para sacarla de la lista de carpetas destino
    if len(c) > 1: # Error cuando hay más de una carpeta con el mismo 'name'
        raise ValueError(f"Ambigua: {len(c)} carpetas '{name}' en '{path}'") # Futura mejora: avisar al usuario y que este decida cuál elegir
    return c[0]
# Construir el árbol a partir de la carpeta base hacia abajo, de forma recursiva
def build_tree(children, folder, path):
    node = {"id": folder["id"], "children": {}} # Se crea el nodo con el id de la carpeta y sus hijos (children) que inicia vacío
    # Obtiene sus hijos con get(folder["id"])
    for h in children.get(folder["id"], []):
        # Por cada hijo, comprueba que su nombre ya no esté en el nodo
        if h["name"] in node["children"]:
            raise ValueError(f"Nombre duplicado '{h['name']}' en '{path}'") # El nombre está duplicado: lanza error
        node["children"][h["name"]] = build_tree(children, h, f"{folder}/{h['name']}") # No está duplicado: llama de forma recursiva a build_tree para construir su subárbol
    return node

def flatten(node, path, out):
    out[path] = node["id"]
    for name, child in node["children"].items():
        flatten(child, f"{path}/{name}", out)
    return out