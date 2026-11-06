from pathlib import Path

# Función que retorna la ruta de la raíz del proyecto según los marcadores: .git, .requirements.txt, .gitignore
def find_root_project(markers=(".git", "requirements.txt", ".gitignore")):
    start = Path(__file__).resolve()
    for parent in start.parents:
        if any((parent / m).exists() for m in markers):
            return parent
    raise FileNotFoundError("No se encontró la raíz del proyecto")