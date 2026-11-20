"""Pruebas para src.workflow.organizer."""

from unittest.mock import MagicMock, patch

import pytest

from src.drive.folder_tree import FolderTreeModel
from src.programs import ProgramDefinition, ProgramStore
from src.workflow.organizer import (
    MissingFolder,
    OrganizationPlan,
    PlannedFile,
    build_plan,
    create_missing_folders,
    execute_plan,
)


FOLDERS = [
    {"id": "root", "name": "Mi Drive", "parents": []},
    {"id": "programs", "name": "Programs", "parents": ["root"]},
    {"id": "powerbi", "name": "Power BI", "parents": ["programs"]},
    {"id": "g1", "name": "G1-Power BI", "parents": ["powerbi"]},
    {"id": "g2", "name": "G2-Power BI", "parents": ["powerbi"]},
]


def modelo(folders=None):
    return FolderTreeModel(
        FOLDERS if folders is None else folders,
        root_id="root",
        root_name="Mi Drive",
    )


def store(destination_id="powerbi"):
    result = ProgramStore()
    result.add(
        ProgramDefinition(
            program="Power BI",
            pattern="G{número}-Power BI",
            destination_path="Mi Drive/Programs/Power BI",
            destination_id=destination_id,
        )
    )
    return result


def archivo(
    file_id="f1",
    name="G1-Power BI.mp4",
    parents=("root",),
    shared=False,
    mime_type="video/mp4",
):
    return {
        "id": file_id,
        "name": name,
        "mimeType": mime_type,
        "parents": list(parents),
        "shared": shared,
    }


def test_build_plan_archivo_listo():
    plan = build_plan([archivo()], modelo(), store())
    assert len(plan.files) == 1
    item = plan.files[0]
    assert item.status == "ready"
    assert item.program == "Power BI"
    assert item.folder_name == "G1-Power BI"
    assert item.folder_id == "g1"
    assert item.destination_id == "powerbi"
    assert plan.ready == (item,)
    assert plan.missing_folders == ()


def test_build_plan_archivo_ya_en_su_lugar():
    plan = build_plan([archivo(parents=("g1",))], modelo(), store())
    item = plan.files[0]
    assert item.status == "already_in_place"
    assert item.folder_id == "g1"
    assert plan.already_in_place == (item,)


def test_build_plan_carpeta_faltante():
    plan = build_plan(
        [archivo(name="G3-Power BI.mp4")], modelo(), store()
    )
    item = plan.files[0]
    assert item.status == "missing_folder"
    assert item.folder_id is None
    assert item.folder_path == "Mi Drive/Programs/Power BI/G3-Power BI"
    assert plan.missing_folders == (
        MissingFolder(
            name="G3-Power BI",
            parent_id="powerbi",
            parent_path="Mi Drive/Programs/Power BI",
        ),
    )
    assert plan.missing == (item,)


def test_build_plan_agrupa_carpetas_faltantes():
    plan = build_plan(
        [
            archivo(file_id="f1", name="G3-Power BI.mp4"),
            archivo(file_id="f2", name="g3-power bi.mov"),
        ],
        modelo(),
        store(),
    )
    assert len(plan.files) == 2
    assert len(plan.missing_folders) == 1
    assert plan.missing_folders[0].name == "G3-Power BI"


def test_build_plan_archivo_sin_patron():
    plan = build_plan([archivo(name="otro.mp4")], modelo(), store())
    item = plan.files[0]
    assert item.status == "unmatched"
    assert item.program is None
    assert plan.unmatched == (item,)


def test_build_plan_archivo_ambiguo():
    store_ambiguo = ProgramStore()
    for program in ("A", "B"):
        store_ambiguo.add(
            ProgramDefinition(
                program=program,
                pattern="X{número}",
                destination_path="Mi Drive/Programs/Power BI",
                destination_id="powerbi",
            )
        )
    plan = build_plan(
        [archivo(name="X5.mp4")], modelo(), store_ambiguo
    )
    item = plan.files[0]
    assert item.status == "ambiguous"
    assert item.program is None
    assert "A, B" in item.message
    assert plan.ambiguous == (item,)


def test_build_plan_destino_inexistente():
    store_sin_destino = ProgramStore()
    store_sin_destino.add(
        ProgramDefinition(
            program="Power BI",
            pattern="G{número}-Power BI",
            destination_path="Mi Drive/No existe",
        )
    )
    plan = build_plan([archivo()], modelo(), store_sin_destino)
    item = plan.files[0]
    assert item.status == "error"
    assert "no existe" in item.message
    assert plan.errors == (item,)


def test_build_plan_ruta_ambigua():
    folders = FOLDERS + [
        {"id": "powerbi2", "name": "Power BI", "parents": ["programs"]},
    ]
    store_sin_id = ProgramStore()
    store_sin_id.add(
        ProgramDefinition(
            program="Power BI",
            pattern="G{número}-Power BI",
            destination_path="Mi Drive/Programs/Power BI",
        )
    )
    plan = build_plan([archivo()], modelo(folders), store_sin_id)
    item = plan.files[0]
    assert item.status == "error"
    assert "ambigua" in item.message.lower()


def test_build_plan_excluye_archivos_compartidos():
    plan = build_plan([archivo(shared=True)], modelo(), store())
    assert plan.files == ()


def test_build_plan_ignora_carpetas():
    plan = build_plan(
        [
            archivo(
                name="G1-Power BI",
                mime_type="application/vnd.google-apps.folder",
            )
        ],
        modelo(),
        store(),
    )
    assert plan.files == ()


def test_build_plan_archivo_sin_id():
    plan = build_plan([archivo(file_id="")], modelo(), store())
    item = plan.files[0]
    assert item.status == "error"
    assert "id" in item.message


def test_build_plan_usa_la_ruta_si_el_id_del_destino_no_existe():
    plan = build_plan(
        [archivo()], modelo(), store(destination_id="id-viejo")
    )
    item = plan.files[0]
    assert item.status == "ready"
    assert item.destination_id == "powerbi"


def test_build_plan_acepta_parents_como_texto():
    file = archivo()
    file["parents"] = "g1"
    plan = build_plan([file], modelo(), store())
    item = plan.files[0]
    assert item.parent_ids == ("g1",)
    assert item.status == "already_in_place"


def test_build_plan_resuelve_rutas_con_separadores_de_windows():
    store_sin_id = ProgramStore()
    store_sin_id.add(
        ProgramDefinition(
            program="Power BI",
            pattern="G{número}-Power BI",
            destination_path="Mi Drive\\Programs\\Power BI",
        )
    )
    plan = build_plan([archivo()], modelo(), store_sin_id)
    item = plan.files[0]
    assert item.status == "ready"
    assert item.destination_id == "powerbi"
    assert item.folder_path == (
        "Mi Drive/Programs/Power BI/G1-Power BI"
    )


def test_build_plan_usa_la_ruta_real_del_destino():
    store_con_ruta_vieja = ProgramStore()
    store_con_ruta_vieja.add(
        ProgramDefinition(
            program="Power BI",
            pattern="G{número}-Power BI",
            destination_path="Mi Drive/Ruta vieja",
            destination_id="powerbi",
        )
    )
    plan = build_plan(
        [archivo()], modelo(), store_con_ruta_vieja
    )
    item = plan.files[0]
    assert item.status == "ready"
    assert item.folder_id == "g1"
    assert item.folder_path == (
        "Mi Drive/Programs/Power BI/G1-Power BI"
    )
    assert item.destination_path == "Mi Drive/Programs/Power BI"


def test_plan_propiedades_agrupan_estados():
    plan = OrganizationPlan(
        files=(
            PlannedFile(file_id="1", file_name="a", status="ready"),
            PlannedFile(
                file_id="2", file_name="b", status="missing_folder"
            ),
            PlannedFile(
                file_id="3", file_name="c", status="already_in_place"
            ),
            PlannedFile(file_id="4", file_name="d", status="ambiguous"),
            PlannedFile(file_id="5", file_name="e", status="unmatched"),
            PlannedFile(file_id="6", file_name="f", status="error"),
        ),
        missing_folders=(),
    )
    assert len(plan.ready) == 1
    assert len(plan.missing) == 1
    assert len(plan.already_in_place) == 1
    assert len(plan.ambiguous) == 1
    assert len(plan.unmatched) == 1
    assert len(plan.errors) == 1


def test_create_missing_folders_dry_run_no_llama_a_la_api():
    plan = OrganizationPlan(
        files=(),
        missing_folders=(
            MissingFolder(
                name="G3-Power BI",
                parent_id="powerbi",
                parent_path="Mi Drive/Programs/Power BI",
            ),
        ),
    )
    with patch("src.workflow.organizer.create_folder") as create:
        created = create_missing_folders(
            MagicMock(), plan, dry_run=True
        )
    assert created == {}
    create.assert_not_called()


def test_create_missing_folders_crea_y_devuelve_ids():
    plan = OrganizationPlan(
        files=(),
        missing_folders=(
            MissingFolder(
                name="G3-Power BI",
                parent_id="powerbi",
                parent_path="Mi Drive/Programs/Power BI",
            ),
        ),
    )
    service = MagicMock()
    with patch(
        "src.workflow.organizer.create_folder",
        return_value={"id": "nueva"},
    ) as create:
        created = create_missing_folders(
            service, plan, dry_run=False
        )
    create.assert_called_once_with(service, "G3-Power BI", "powerbi")
    assert created == {("powerbi", "G3-Power BI"): "nueva"}


def test_create_missing_folders_falla_si_no_hay_id():
    plan = OrganizationPlan(
        files=(),
        missing_folders=(
            MissingFolder(
                name="G3-Power BI",
                parent_id="powerbi",
                parent_path="Mi Drive/Programs/Power BI",
            ),
        ),
    )
    with patch(
        "src.workflow.organizer.create_folder",
        return_value={},
    ):
        with pytest.raises(ValueError, match="id"):
            create_missing_folders(
                MagicMock(), plan, dry_run=False
            )


def test_execute_plan_mueve_archivos_listos():
    item = PlannedFile(
        file_id="f1",
        file_name="G1-Power BI.mp4",
        parent_ids=("root",),
        program="Power BI",
        destination_id="powerbi",
        folder_name="G1-Power BI",
        folder_id="g1",
        status="ready",
    )
    plan = OrganizationPlan(files=(item,), missing_folders=())
    service = MagicMock()
    with patch("src.workflow.organizer.move_file") as move:
        report = execute_plan(service, plan, dry_run=False)
    move.assert_called_once_with(service, "f1", "g1", ("root",))
    assert report.moved == (item,)
    assert report.dry_run is False


def test_execute_plan_dry_run_no_mueve():
    item = PlannedFile(
        file_id="f1",
        file_name="G1-Power BI.mp4",
        parent_ids=("root",),
        folder_id="g1",
        status="ready",
    )
    plan = OrganizationPlan(files=(item,), missing_folders=())
    with patch("src.workflow.organizer.move_file") as move:
        report = execute_plan(MagicMock(), plan, dry_run=True)
    move.assert_not_called()
    assert report.moved == (item,)
    assert report.dry_run is True


def test_execute_plan_pendientes_sin_carpeta():
    item = PlannedFile(
        file_id="f1",
        file_name="G3-Power BI.mp4",
        parent_ids=("root",),
        destination_id="powerbi",
        folder_name="G3-Power BI",
        status="missing_folder",
    )
    plan = OrganizationPlan(files=(item,), missing_folders=())
    with patch("src.workflow.organizer.move_file") as move:
        report = execute_plan(MagicMock(), plan, dry_run=False)
    move.assert_not_called()
    assert report.pending == (item,)


def test_execute_plan_mueve_pendientes_con_carpeta_creada():
    item = PlannedFile(
        file_id="f1",
        file_name="G3-Power BI.mp4",
        parent_ids=("root",),
        destination_id="powerbi",
        folder_name="G3-Power BI",
        status="missing_folder",
    )
    plan = OrganizationPlan(files=(item,), missing_folders=())
    folder_ids = {("powerbi", "G3-Power BI"): "nueva"}
    service = MagicMock()
    with patch("src.workflow.organizer.move_file") as move:
        report = execute_plan(
            service, plan, folder_ids=folder_ids, dry_run=False
        )
    move.assert_called_once_with(service, "f1", "nueva", ("root",))
    assert report.moved == (item,)


def test_execute_plan_reporta_errores():
    item = PlannedFile(
        file_id="f1",
        file_name="G1-Power BI.mp4",
        parent_ids=("root",),
        folder_id="g1",
        status="ready",
    )
    plan = OrganizationPlan(files=(item,), missing_folders=())
    with patch(
        "src.workflow.organizer.move_file",
        side_effect=RuntimeError("boom"),
    ):
        report = execute_plan(MagicMock(), plan, dry_run=False)
    assert len(report.errors) == 1
    assert report.errors[0].status == "error"
    assert "boom" in report.errors[0].message
    assert report.moved == ()


def test_execute_plan_clasifica_estados():
    plan = OrganizationPlan(
        files=(
            PlannedFile(
                file_id="1", file_name="a", status="already_in_place"
            ),
            PlannedFile(file_id="2", file_name="b", status="ambiguous"),
            PlannedFile(file_id="3", file_name="c", status="unmatched"),
            PlannedFile(file_id="4", file_name="d", status="error"),
        ),
        missing_folders=(),
    )
    report = execute_plan(MagicMock(), plan, dry_run=False)
    assert len(report.already_in_place) == 1
    assert len(report.ambiguous) == 1
    assert len(report.unmatched) == 1
    assert len(report.errors) == 1
    assert report.moved == ()


def test_execute_plan_ready_sin_folder_id_queda_pendiente():
    item = PlannedFile(
        file_id="f1",
        file_name="G1-Power BI.mp4",
        status="ready",
        folder_id=None,
    )
    plan = OrganizationPlan(files=(item,), missing_folders=())
    report = execute_plan(MagicMock(), plan, dry_run=False)
    assert report.pending == (item,)
