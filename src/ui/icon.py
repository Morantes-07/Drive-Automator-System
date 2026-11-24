"""Icono de la aplicación: ventana, barra de tareas e identidad del proceso.

El recurso vive en la carpeta ``assets`` de la raíz del proyecto, así que la
ruta se resuelve con ``find_root_project`` para que funcione tanto al ejecutar
como módulo desde cualquier directorio como al abrir el proyecto desde un IDE.

En Windows la barra de tareas agrupa los botones por ``AppUserModelID``. Sin
una identidad propia, un proceso iniciado con ``python.exe`` muestra el icono
de Python aunque la ventana tenga el nuestro, por eso hay que registrarla antes
de crear la ventana.
"""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from pathlib import Path

from src.utils.path_management import find_root_project

#: Identidad del proceso en la barra de tareas de Windows.
APP_USER_MODEL_ID = "Esumer.OrganizadorDrive.1"

#: Nombre del recurso dentro de ``assets``.
ICON_FILENAME = "flavicon_esumer.ico"


def set_app_user_model_id(app_id: str = APP_USER_MODEL_ID) -> bool:
    """Da al proceso una identidad propia en la barra de tareas de Windows.

    Devuelve ``False`` fuera de Windows o si el sistema no acepta el registro;
    en ese caso la aplicación sigue arrancando con normalidad.
    """
    if sys.platform != "win32":
        return False
    try:
        result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        return False
    return result == 0


def icon_path() -> Path:
    """Devuelve la ruta al archivo ``.ico`` de la ventana."""
    return find_root_project() / "assets" / ICON_FILENAME


def apply_window_icon(window: tk.Tk | tk.Toplevel) -> bool:
    """Pone el icono de la aplicación en una ventana y avisa si lo logró.

    El ``.ico`` contiene entradas de varios tamaños, así que Tk lo usa tanto
    para el icono grande como para el pequeño de la barra de tareas. Un recurso
    ausente no debe impedir que arranque la interfaz: en ese caso se devuelve
    ``False`` y se conserva el icono previo.
    """
    try:
        window.iconbitmap(str(icon_path()))
    except (OSError, tk.TclError):
        return False
    return True
