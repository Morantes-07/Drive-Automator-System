"""Planificación y ejecución de la organización de archivos de Drive.

El flujo se divide en tres pasos:

1. ``build_plan`` cruza los archivos con los patrones y el árbol de carpetas.
   No toca la API: solo decide qué se puede mover y qué carpetas faltan.
2. ``create_missing_folders`` intenta crear cada subcarpeta pendiente y
   devuelve las creadas junto con los fallos, sin abortar el resto.
3. ``execute_plan`` mueve los archivos y devuelve un reporte por estado.

Todas las funciones respetan ``dry_run``: con ``True`` no se crea ni se mueve
nada en Drive.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping

from src.drive.drive_client import create_folder, move_file
from src.drive.file_types import is_folder
from src.drive.folder_tree import (
    FolderNode,
    FolderTreeError,
    FolderTreeModel,
)
from src.patterns.matcher import match_file
from src.programs import ProgramDefinition, ProgramStore


@dataclass(frozen=True, slots=True)
class PlannedFile:
    """Resultado del análisis de un archivo de Drive.

    Attributes:
        file_id: Id del archivo.
        file_name: Nombre visible del archivo.
        parent_ids: Carpetas que contienen el archivo actualmente.
        program: Programa asignado, si el archivo coincidió con un patrón.
        destination_id: Id de la carpeta base del programa.
        destination_path: Ruta lógica de la carpeta base.
        folder_name: Nombre canónico de la subcarpeta.
        folder_path: Ruta lógica completa de la subcarpeta.
        folder_id: Id de la subcarpeta, si ya existe.
        status: ``ready``, ``missing_folder``, ``already_in_place``,
            ``ambiguous``, ``unmatched`` o ``error``.
        message: Explicación legible del estado.
    """

    file_id: str
    file_name: str
    parent_ids: tuple[str, ...] = ()
    program: str | None = None
    destination_id: str | None = None
    destination_path: str | None = None
    folder_name: str | None = None
    folder_path: str | None = None
    folder_id: str | None = None
    status: str = "unmatched"
    message: str | None = None


@dataclass(frozen=True, slots=True)
class MissingFolder:
    """Subcarpeta que hay que crear para poder mover sus archivos."""

    name: str
    parent_id: str
    parent_path: str


@dataclass(frozen=True, slots=True)
class FolderError:
    """Subcarpeta que no se pudo crear en Drive."""

    name: str
    parent_id: str
    parent_path: str
    message: str


@dataclass(frozen=True, slots=True)
class FolderCreationResult:
    """Resultado de intentar crear todas las subcarpetas pendientes."""

    created: Mapping[tuple[str, str], str]
    errors: tuple[FolderError, ...]


@dataclass(frozen=True, slots=True)
class OrganizationPlan:
    """Resultado del análisis, antes de tocar Drive."""

    files: tuple[PlannedFile, ...]
    missing_folders: tuple[MissingFolder, ...]

    @property
    def ready(self) -> tuple[PlannedFile, ...]:
        """Archivos cuya subcarpeta ya existe y se pueden mover."""
        return tuple(
            item for item in self.files if item.status == "ready"
        )

    @property
    def missing(self) -> tuple[PlannedFile, ...]:
        """Archivos cuya subcarpeta todavía no existe."""
        return tuple(
            item for item in self.files if item.status == "missing_folder"
        )

    @property
    def already_in_place(self) -> tuple[PlannedFile, ...]:
        """Archivos que ya están en su subcarpeta."""
        return tuple(
            item
            for item in self.files
            if item.status == "already_in_place"
        )

    @property
    def ambiguous(self) -> tuple[PlannedFile, ...]:
        """Archivos que coinciden con varios programas."""
        return tuple(
            item for item in self.files if item.status == "ambiguous"
        )

    @property
    def unmatched(self) -> tuple[PlannedFile, ...]:
        """Archivos que no coinciden con ningún patrón."""
        return tuple(
            item for item in self.files if item.status == "unmatched"
        )

    @property
    def errors(self) -> tuple[PlannedFile, ...]:
        """Archivos que no se pudieron planificar."""
        return tuple(
            item for item in self.files if item.status == "error"
        )


@dataclass(frozen=True, slots=True)
class OrganizationReport:
    """Resultado de mover archivos (o de simular el movimiento)."""

    moved: tuple[PlannedFile, ...] = ()
    already_in_place: tuple[PlannedFile, ...] = ()
    pending: tuple[PlannedFile, ...] = ()
    ambiguous: tuple[PlannedFile, ...] = ()
    unmatched: tuple[PlannedFile, ...] = ()
    errors: tuple[PlannedFile, ...] = ()
    dry_run: bool = False


def build_plan(
    files: Iterable[Mapping[str, object]],
    model: FolderTreeModel,
    store: ProgramStore,
) -> OrganizationPlan:
    """Cruza archivos, patrones y carpetas sin tocar la API.

    Los archivos compartidos con otros usuarios (``shared = true``) y las
    carpetas se ignoran, según el alcance definido para la aplicación.

    Args:
        files: Archivos de Drive con ``id``, ``name``, ``mimeType``,
            ``parents`` y ``shared``.
        model: Árbol de carpetas cargado desde Drive.
        store: Programas configurados por el usuario.

    Returns:
        Plan con el estado de cada archivo y las carpetas que faltan.
    """
    patterns = store.compiled()
    programs = {item.program: item for item in store.items()}

    planned: list[PlannedFile] = []
    missing: dict[tuple[str, str], MissingFolder] = {}
    base_paths: dict[str, str] = {}

    for file in files:
        if is_folder(file) or bool(file.get("shared", False)):
            continue

        file_id = str(file.get("id") or "").strip()
        file_name = str(file.get("name") or "").strip()
        raw_parents = file.get("parents") or ()
        if isinstance(raw_parents, str):
            raw_parents = (raw_parents,)
        parents = tuple(
            str(parent).strip()
            for parent in raw_parents
            if str(parent).strip()
        )
        if not file_id:
            planned.append(
                PlannedFile(
                    file_id="",
                    file_name=file_name,
                    parent_ids=parents,
                    status="error",
                    message="El archivo no tiene id.",
                )
            )
            continue

        match = match_file(file_name, patterns)
        if match.status == "unmatched":
            planned.append(
                PlannedFile(
                    file_id=file_id,
                    file_name=file_name,
                    parent_ids=parents,
                    status="unmatched",
                    message="No coincide con ningún patrón.",
                )
            )
            continue
        if match.status == "ambiguous":
            planned.append(
                PlannedFile(
                    file_id=file_id,
                    file_name=file_name,
                    parent_ids=parents,
                    status="ambiguous",
                    message=(
                        "Coincide con varios programas: "
                        + ", ".join(match.candidates)
                    ),
                )
            )
            continue

        definition = programs.get(match.program or "")
        if definition is None:
            planned.append(
                PlannedFile(
                    file_id=file_id,
                    file_name=file_name,
                    parent_ids=parents,
                    status="error",
                    message=(
                        f"El programa '{match.program}' no está en el "
                        "registro."
                    ),
                )
            )
            continue

        folder_name = match.folder_name
        if not folder_name:
            planned.append(
                PlannedFile(
                    file_id=file_id,
                    file_name=file_name,
                    parent_ids=parents,
                    program=definition.program,
                    destination_path=definition.destination_path,
                    status="error",
                    message=(
                        "El patrón no generó un nombre de subcarpeta."
                    ),
                )
            )
            continue

        destination = _resolve_destination(model, definition)
        if isinstance(destination, str):
            planned.append(
                PlannedFile(
                    file_id=file_id,
                    file_name=file_name,
                    parent_ids=parents,
                    program=definition.program,
                    destination_path=definition.destination_path,
                    folder_name=folder_name,
                    status="error",
                    message=destination,
                )
            )
            continue

        base_path = base_paths.get(destination.id)
        if base_path is None:
            base_path = model.path_of(destination.id)
            base_paths[destination.id] = base_path
        folder_path = f"{base_path}/{folder_name}"
        try:
            folder = model.resolve_path(folder_path)
        except FolderTreeError as exc:
            planned.append(
                PlannedFile(
                    file_id=file_id,
                    file_name=file_name,
                    parent_ids=parents,
                    program=definition.program,
                    destination_id=destination.id,
                    destination_path=base_path,
                    folder_name=folder_name,
                    folder_path=folder_path,
                    status="error",
                    message=str(exc),
                )
            )
            continue

        folder_id: str | None = None
        if folder is not None:
            folder_id = folder.id
            status = (
                "already_in_place"
                if folder_id in parents
                else "ready"
            )
            message = (
                "El archivo ya está en su subcarpeta."
                if status == "already_in_place"
                else None
            )
        else:
            status = "missing_folder"
            message = "La subcarpeta todavía no existe."
            key = (destination.id, folder_name)
            missing.setdefault(
                key,
                MissingFolder(
                    name=folder_name,
                    parent_id=destination.id,
                    parent_path=base_path,
                ),
            )

        planned.append(
            PlannedFile(
                file_id=file_id,
                file_name=file_name,
                parent_ids=parents,
                program=definition.program,
                destination_id=destination.id,
                destination_path=base_path,
                folder_name=folder_name,
                folder_path=folder_path,
                folder_id=folder_id,
                status=status,
                message=message,
            )
        )

    return OrganizationPlan(
        files=tuple(planned),
        missing_folders=tuple(missing.values()),
    )


def _resolve_destination(
    model: FolderTreeModel,
    definition: ProgramDefinition,
) -> FolderNode | str:
    """Devuelve la carpeta destino o un mensaje de error legible.

    Se prefiere el id guardado en la definición; si ya no existe en el árbol,
    se intenta resolver la ruta lógica.
    """
    if definition.destination_id:
        node = model.get(definition.destination_id)
        if node is not None:
            return node

    try:
        node = model.resolve_path(definition.destination_path)
    except FolderTreeError as exc:
        return str(exc)

    if node is None:
        return (
            "La carpeta destino no existe en Drive: "
            f"'{definition.destination_path}'."
        )
    return node


def create_missing_folders(
    service,
    plan: OrganizationPlan,
    dry_run: bool = True,
) -> FolderCreationResult:
    """Crea las subcarpetas que faltan y reporta los fallos por carpeta.

    Un error al crear una carpeta no impide intentar las demás. Los archivos
    de las carpetas fallidas se quedarán pendientes y no se moverán.

    Args:
        service: Servicio de Drive autenticado.
        plan: Plan generado por ``build_plan``.
        dry_run: Si es ``True``, no crea nada.

    Returns:
        Resultado con el mapa ``(parent_id, folder_name) -> folder_id`` de
        las carpetas creadas y la lista de fallos.
    """
    created: dict[tuple[str, str], str] = {}
    errors: list[FolderError] = []
    if dry_run:
        return FolderCreationResult(created=created, errors=())

    for missing in plan.missing_folders:
        try:
            folder = create_folder(service, missing.name, missing.parent_id)
            folder_id = str(folder.get("id") or "").strip()
            if not folder_id:
                raise ValueError(
                    "Drive no devolvió el id de la carpeta "
                    f"'{missing.name}'."
                )
        except Exception as exc:
            errors.append(
                FolderError(
                    name=missing.name,
                    parent_id=missing.parent_id,
                    parent_path=missing.parent_path,
                    message=str(exc),
                )
            )
        else:
            created[(missing.parent_id, missing.name)] = folder_id

    return FolderCreationResult(
        created=created,
        errors=tuple(errors),
    )


def execute_plan(
    service,
    plan: OrganizationPlan,
    folder_ids: dict[tuple[str, str], str] | None = None,
    dry_run: bool = True,
    folder_errors: Mapping[tuple[str, str], str] | None = None,
) -> OrganizationReport:
    """Mueve los archivos del plan y devuelve el reporte.

    Los archivos con estado ``missing_folder`` solo se mueven si su carpeta
    aparece en ``folder_ids`` (es decir, si se creó antes con
    ``create_missing_folders``). En ``dry_run`` no se llama a la API: los
    archivos que se moverían se incluyen en ``moved`` y el reporte queda
    marcado como simulación.

    Args:
        service: Servicio de Drive autenticado.
        plan: Plan generado por ``build_plan``.
        folder_ids: Mapa de carpetas creadas.
        dry_run: Si es ``True``, solo simula el movimiento.
        folder_errors: Motivos de las carpetas que no se pudieron crear,
            indexados por ``(parent_id, folder_name)``. Los archivos
            afectados quedan pendientes con el motivo en su detalle.

    Returns:
        Reporte con los archivos agrupados por resultado.
    """
    folder_ids = folder_ids or {}
    folder_errors = folder_errors or {}
    moved: list[PlannedFile] = []
    already_in_place: list[PlannedFile] = []
    pending: list[PlannedFile] = []
    ambiguous: list[PlannedFile] = []
    unmatched: list[PlannedFile] = []
    errors: list[PlannedFile] = []

    for item in plan.files:
        if item.status == "already_in_place":
            already_in_place.append(item)
            continue
        if item.status == "ambiguous":
            ambiguous.append(item)
            continue
        if item.status == "unmatched":
            unmatched.append(item)
            continue
        if item.status == "error":
            errors.append(item)
            continue

        target_id: str | None = None
        if item.status == "ready":
            target_id = item.folder_id
        elif item.status == "missing_folder":
            target_id = folder_ids.get(
                (item.destination_id or "", item.folder_name or "")
            )

        if target_id is None:
            key = (item.destination_id or "", item.folder_name or "")
            reason = folder_errors.get(key)
            if reason:
                pending.append(
                    replace(
                        item,
                        message=(
                            "No se pudo crear la subcarpeta: "
                            f"{reason}"
                        ),
                    )
                )
            else:
                pending.append(item)
            continue

        if dry_run:
            moved.append(item)
            continue

        try:
            move_file(
                service,
                item.file_id,
                target_id,
                item.parent_ids,
            )
        except Exception as exc:
            errors.append(
                replace(
                    item,
                    status="error",
                    message=f"No se pudo mover: {exc}",
                )
            )
        else:
            moved.append(item)

    return OrganizationReport(
        moved=tuple(moved),
        already_in_place=tuple(already_in_place),
        pending=tuple(pending),
        ambiguous=tuple(ambiguous),
        unmatched=tuple(unmatched),
        errors=tuple(errors),
        dry_run=dry_run,
    )
