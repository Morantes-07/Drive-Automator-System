"""Pruebas de la barra de organización de la pestaña de organización."""

from unittest.mock import Mock

import pytest

from src.programs import ProgramStore
from src.ui.organize_tab import OrganizeTab
from src.workflow.organizer import (
    FolderCreationResult,
    OrganizationPlan,
    OrganizationReport,
)


@pytest.fixture
def tab(tk_root):
    widget = OrganizeTab(tk_root, ProgramStore())
    widget.pack(fill="both", expand=True)
    tk_root.update_idletasks()
    yield widget
    widget._stop_progress()
    widget.destroy()


def _empty_plan() -> OrganizationPlan:
    """Plan vacío para probar la barra sin lógica de negocio."""
    return OrganizationPlan(files=(), missing_folders=())


def _empty_creation() -> FolderCreationResult:
    """Resultado de creación vacío para los reportes de prueba."""
    return FolderCreationResult(created={}, errors=())


def test_barra_oculta_al_construir(tab):
    assert not tab._progress.grid_info()


def test_start_progress_muestra_y_anima(tab, monkeypatch):
    start = Mock()
    monkeypatch.setattr(tab._progress, "start", start)

    tab._start_progress()

    assert tab._progress.grid_info()
    start.assert_called_once_with()


def test_stop_progress_detiene_y_oculta(tab, monkeypatch):
    stop = Mock()
    monkeypatch.setattr(tab._progress, "stop", stop)
    tab._progress.grid()

    tab._stop_progress()

    assert not tab._progress.grid_info()
    stop.assert_called_once_with()


def test_start_execution_en_seco_no_muestra_barra(tab, monkeypatch):
    tab._settings.dry_run = True
    tab._plan = _empty_plan()
    monkeypatch.setattr(tab, "_execute_worker", Mock())

    tab._start_execution(create_missing=False)

    assert not tab._progress.grid_info()


def test_start_execution_real_muestra_barra(tab, monkeypatch):
    tab._settings.dry_run = False
    tab._plan = _empty_plan()
    monkeypatch.setattr(tab, "_execute_worker", Mock())
    start = Mock()
    monkeypatch.setattr(tab._progress, "start", start)

    tab._start_execution(create_missing=False)

    assert tab._progress.grid_info()
    start.assert_called_once_with()


def test_on_execute_done_detiene_la_barra(tab, monkeypatch):
    stop = Mock()
    monkeypatch.setattr(tab._progress, "stop", stop)
    tab._progress.grid()

    tab._on_execute_done(
        OrganizationReport(dry_run=False),
        _empty_creation(),
        tab._generation,
    )

    assert not tab._progress.grid_info()
    stop.assert_called_once_with()


def test_on_execute_error_detiene_la_barra(tab, monkeypatch):
    stop = Mock()
    monkeypatch.setattr(tab._progress, "stop", stop)
    tab._progress.grid()

    tab._on_execute_error(
        RuntimeError("fallo"), tab._generation, dry_run=False
    )

    assert not tab._progress.grid_info()
    stop.assert_called_once_with()


def test_scan_no_muestra_la_barra(tab):
    tab._on_scan_done(_empty_plan(), tab._generation)

    assert not tab._progress.grid_info()
