"""Modelo en memoria del árbol de carpetas de Google Drive.

``list_folders()`` descarga todas las carpetas en una sola pasada, así que el
árbol no necesita consultas adicionales: este módulo indexa esa lista por
carpeta padre y ofrece las operaciones que necesita la interfaz (hijos, ruta
lógica y resolución de una ruta escrita por el usuario).

El modelo es puro: no depende de Tk ni de la API, de modo que se puede probar
sin interfaz.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Iterable, Mapping

@dataclass(frozen=True, slots=True)
class FolderNode:
    """Carpeta del árbol.

    Attributes:
        id: Identificador de Drive.
        name: Nombre visible de la carpeta.
        parent_ids: Carpetas que la contienen. Drive permite que una carpeta
            tenga varios padres, así que se guardan todos.
    """

    id: str
    name: str
    parent_ids: tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.name

class FolderTreeError(ValueError):
    """Error al construir o consultar el árbol de carpetas."""

class AmbiguousPathError(FolderTreeError):
    """Varias carpetas comparten nombre dentro del mismo padre."""

    def __init__(self, path: str, candidates: Iterable[FolderNode]):
        self.path = path
        self.candidates = tuple(candidates)
        ids = ", ".join(node.id for node in self.candidates)
        super().__init__(
            f"Ruta ambigua '{path}': {len(self.candidates)} carpetas con ese "
            f"nombre ({ids})"
        )

def _plain(text: str) -> str:
    """Quita tildes y diacríticos de un texto."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))

def _normalize(text: str) -> str:
    """Normaliza un nombre para comparar rutas (sin tildes ni mayúsculas)."""
    return _plain(text).strip().casefold()

def _sort_key(node: FolderNode) -> tuple[str, str]:
    """Clave de orden alfabético que ignora mayúsculas y tildes."""
    return (_normalize(node.name), node.id)

class FolderTreeModel:
    """Índice de carpetas por padre, con la raíz como punto de partida.

    Args:
        folders: Carpetas tal como las devuelve ``list_folders()`` (diccionarios
            con ``id``, ``name`` y ``parents``) o instancias de ``FolderNode``.
        root_id: Identificador de la carpeta raíz de Drive.
        root_name: Nombre con el que se muestra la raíz en la interfaz.
    """

    def __init__(
        self,
        folders: Iterable[Mapping[str, object] | FolderNode],
        root_id: str,
        root_name: str = "Mi Drive",
    ):
        if not root_id or not str(root_id).strip():
            raise FolderTreeError("La carpeta raíz necesita un id")
        root_id = str(root_id).strip()
        root_name = (root_name or "Mi Drive").strip() or "Mi Drive"

        nodes: dict[str, FolderNode] = {}
        for folder in folders:
            node = self._to_node(folder)
            if node.id in nodes:
                raise FolderTreeError(
                    f"Id de carpeta duplicado: '{node.id}' ('{node.name}')"
                )
            nodes[node.id] = node

        # La raíz siempre existe y siempre se muestra con el mismo nombre.
        nodes[root_id] = FolderNode(id=root_id, name=root_name, parent_ids=())

        children: dict[str, list[str]] = {}
        for node in nodes.values():
            for parent_id in node.parent_ids:
                # Los padres que no están en el listado (por ejemplo, carpetas
                # compartidas) se ignoran: sus hijos no cuelgan de la raíz.
                if parent_id in nodes:
                    children.setdefault(parent_id, []).append(node.id)

        self._nodes = nodes
        self._children = {
            parent_id: tuple(sorted(ids, key=lambda folder_id: _sort_key(nodes[folder_id])))
            for parent_id, ids in children.items()
        }
        self._root_id = root_id

    # -- construcción ------------------------------------------------------
    @staticmethod
    def _to_node(folder: Mapping[str, object] | FolderNode) -> FolderNode:
        """Convierte una carpeta de la API en un FolderNode validado."""
        if isinstance(folder, FolderNode):
            return folder
        if not isinstance(folder, Mapping):
            raise FolderTreeError(
                f"Se esperaba una carpeta (dict o FolderNode), se recibió "
                f"{type(folder).__name__}"
            )

        folder_id = folder.get("id")
        name = folder.get("name")
        if not folder_id or not str(folder_id).strip():
            raise FolderTreeError(f"Carpeta sin id: {folder!r}")
        if not name or not str(name).strip():
            raise FolderTreeError(f"Carpeta sin nombre: '{folder_id}'")

        parents = folder.get("parents") or ()
        if isinstance(parents, str):
            parents = (parents,)
        return FolderNode(
            id=str(folder_id).strip(),
            name=str(name).strip(),
            parent_ids=tuple(str(parent).strip() for parent in parents),
        )

    # -- consultas ---------------------------------------------------------
    @property
    def root(self) -> FolderNode:
        """Carpeta raíz del árbol."""
        return self._nodes[self._root_id]

    @property
    def root_id(self) -> str:
        """Identificador de la carpeta raíz."""
        return self._root_id

    def __len__(self) -> int:
        """Número de carpetas del árbol, incluida la raíz."""
        return len(self._nodes)

    def __contains__(self, folder_id: str) -> bool:
        return folder_id in self._nodes

    def get(self, folder_id: str) -> FolderNode | None:
        """Devuelve la carpeta con ese id, o None si no existe."""
        return self._nodes.get(folder_id)

    def require(self, folder_id: str) -> FolderNode:
        """Devuelve la carpeta con ese id; falla si no existe."""
        node = self._nodes.get(folder_id)
        if node is None:
            raise FolderTreeError(f"Carpeta desconocida: '{folder_id}'")
        return node

    def children_of(self, folder_id: str) -> tuple[FolderNode, ...]:
        """Hijos directos de una carpeta, ordenados alfabéticamente."""
        ids = self._children.get(folder_id, ())
        return tuple(self._nodes[folder_id] for folder_id in ids)

    def has_children(self, folder_id: str) -> bool:
        """Indica si la carpeta tiene al menos un hijo directo."""
        return bool(self._children.get(folder_id))

    def parent_of(self, folder_id: str) -> FolderNode | None:
        """Primer padre conocido de la carpeta, o None si no tiene."""
        node = self._nodes.get(folder_id)
        if node is None:
            return None
        for parent_id in node.parent_ids:
            parent = self._nodes.get(parent_id)
            if parent is not None:
                return parent
        return None

    def path_of(self, folder_id: str, separator: str = "/") -> str:
        """Ruta lógica de la carpeta, desde la raíz hasta ella.

        Con varios padres se elige el primero que exista en el modelo y que no
        se haya visitado todavía, de modo que un ciclo en los datos no bloquea
        la construcción de la ruta.
        """
        node = self._nodes.get(folder_id)
        if node is None:
            raise FolderTreeError(f"Carpeta desconocida: '{folder_id}'")

        parts = [node.name]
        visited = {node.id}
        current = node
        while True:
            parent = None
            for parent_id in current.parent_ids:
                candidate = self._nodes.get(parent_id)
                if candidate is not None and candidate.id not in visited:
                    parent = candidate
                    break
            if parent is None:
                break
            parts.append(parent.name)
            visited.add(parent.id)
            current = parent
        return separator.join(reversed(parts))

    def resolve_path(self, path: str | None) -> FolderNode | None:
        """Devuelve la carpeta que corresponde a una ruta lógica.

        Acepta la ruta con o sin el nombre de la raíz al principio y compara
        sin distinguir mayúsculas ni tildes. Devuelve None si la ruta está
        vacía o si alguna parte no existe.

        Raises:
            AmbiguousPathError: Si una parte de la ruta coincide con más de
                una carpeta del mismo padre.
        """
        if path is None:
            return None
        # Se admite tanto "/" como "\" para que el texto pegado desde Windows
        # también funcione.
        parts = [
            part.strip()
            for part in str(path).replace("\\", "/").split("/")
        ]
        parts = [part for part in parts if part]
        if not parts:
            return None

        current = self.root
        if _normalize(parts[0]) == _normalize(current.name) or parts[0] == current.id:
            parts = parts[1:]

        for part in parts:
            candidates = [
                node
                for node in self.children_of(current.id)
                if _normalize(node.name) == _normalize(part)
            ]
            if not candidates:
                return None
            if len(candidates) > 1:
                raise AmbiguousPathError(path, candidates)
            current = candidates[0]
        return current