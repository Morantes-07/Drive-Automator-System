from pathlib import Path

def find_root_project(markers=(".git", "requirements.txt", ".gitignore")):
    """Retorna la ruta de la raíz del proyecto según marcadores: .git, .requirements.txt, .gitignore"""
    start = Path(__file__).resolve()
    for parent in start.parents:
        if any((parent / m).exists() for m in markers):
            return parent
    raise FileNotFoundError("No se encontró la raíz del proyecto")