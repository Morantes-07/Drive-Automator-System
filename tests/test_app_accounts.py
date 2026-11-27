"""Pruebas de la integración de cuentas en la ventana principal."""

from unittest.mock import Mock

import pytest

from src.authentication.auth import AuthPaths
from src.drive.folder_tree import FolderTreeModel
from src.programs import ProgramDefinition, ProgramRepository
from src.profiles.models import AccountProfile
from src.profiles.service import AccountService
from src.profiles.store import ProfileStore
from src.ui import app as app_module
from src.ui.app import DriveOrganizerApp

ID1 = "a" * 32
ID2 = "b" * 32


def _definition(program="Power BI", pattern="G{número}-Power BI"):
    return ProgramDefinition(
        program=program,
        pattern=pattern,
        destination_path=f"Mi Drive/{program}",
    )


@pytest.fixture
def store(tmp_path):
    return ProfileStore(tmp_path / "data")


@pytest.fixture
def accounts(store, tmp_path):
    return AccountService(
        store,
        legacy_credentials=tmp_path / "sin-credenciales.json",
        legacy_token=tmp_path / "sin-token.json",
    )


@pytest.fixture
def app(tk_root, store, accounts):
    window = DriveOrganizerApp(profiles=store, accounts=accounts)
    # Ninguna prueba debe abrir el navegador ni llamar a la API de Drive.
    window.reload_drive = lambda: None
    window.withdraw()
    yield window
    window._closing = True
    try:
        window.destroy()
    except Exception:
        pass


def _add_profile(store, profile_id=ID1, name="Trabajo", email=None):
    profile = AccountProfile(id=profile_id, name=name, email=email)
    store.add(profile)
    return profile


# -- selector de la cabecera -----------------------------------------------
def test_sin_cuentas_deshabilita_el_selector(app):
    assert app._account_menu.cget("state") == "disabled"
    assert app._account_menu.get() == "Sin cuenta"
    assert app._account_labels == {}


def test_selector_lista_las_cuentas_deduplicando_nombres(app, store):
    _add_profile(store, ID1, "Trabajo")
    _add_profile(store, ID2, "Trabajo")
    store.set_active(ID2)

    app._refresh_account_menu()

    assert app._account_menu.cget("state") == "normal"
    assert app._account_menu.cget("values") == ["Trabajo", "Trabajo (2)"]
    assert app._account_labels == {"Trabajo": ID1, "Trabajo (2)": ID2}
    assert app._account_menu.get() == "Trabajo (2)"


def test_selector_sin_cuenta_activa_muestra_la_primera(app, store):
    _add_profile(store, ID1, "Uno")
    _add_profile(store, ID2, "Dos")

    app._refresh_account_menu()

    assert app._account_labels == {"Uno": ID1, "Dos": ID2}


def test_on_account_menu_ignora_etiquetas_desconocidas_y_la_activa(
    app, store, monkeypatch
):
    _add_profile(store, ID1, "Trabajo")
    _add_profile(store, ID2, "Personal")
    store.set_active(ID1)
    app._refresh_account_menu()
    switch = Mock()
    monkeypatch.setattr(app, "switch_account", switch)

    app._on_account_menu("Desconocida")
    app._on_account_menu("Trabajo")

    switch.assert_not_called()


def test_on_account_menu_cambia_a_la_cuenta_elegida(app, store, monkeypatch):
    _add_profile(store, ID1, "Trabajo")
    _add_profile(store, ID2, "Personal")
    store.set_active(ID1)
    app._refresh_account_menu()
    switch = Mock()
    monkeypatch.setattr(app, "switch_account", switch)

    app._on_account_menu("Personal")

    switch.assert_called_once_with(ID2)


# -- cambio de cuenta ------------------------------------------------------
def test_cambiar_a_la_cuenta_activa_solo_refresca(app, store, monkeypatch):
    _add_profile(store, ID1)
    store.set_active(ID1)
    activate = Mock()
    refresh = Mock()
    monkeypatch.setattr(app, "_activate_profile", activate)
    monkeypatch.setattr(app, "_refresh_account_ui", refresh)

    app.switch_account(ID1)

    activate.assert_not_called()
    refresh.assert_called_once_with()


@pytest.mark.parametrize(
    "attribute",
    ["loading", "organize", "accounts"],
)
def test_cambiar_de_cuenta_se_bloquea_si_hay_trabajo(
    app, store, monkeypatch, attribute
):
    _add_profile(store, ID1)
    _add_profile(store, ID2, "Personal")
    store.set_active(ID1)
    activate = Mock()
    monkeypatch.setattr(app, "_activate_profile", activate)
    if attribute == "loading":
        app._loading_drive = True
    elif attribute == "organize":
        app.organize_tab._busy = True
    else:
        app.accounts_tab._busy = True

    try:
        app.switch_account(ID2)
    finally:
        app._loading_drive = False
        app.organize_tab._busy = False
        app.accounts_tab._busy = False

    activate.assert_not_called()
    assert store.active_id == ID1
    assert "Espera" in app._status_label.cget("text")


def test_activate_profile_recarga_programas_y_drive(app, store, monkeypatch):
    _add_profile(store, ID1)
    _add_profile(store, ID2, "Personal")
    store.set_active(ID1)
    calls: list[str] = []
    monkeypatch.setattr(
        app, "_reset_drive_state", lambda: calls.append("reset")
    )
    monkeypatch.setattr(
        app, "_load_programs_for_active", lambda: calls.append("programs")
    )
    monkeypatch.setattr(
        app, "_refresh_account_ui", lambda: calls.append("ui")
    )
    monkeypatch.setattr(app, "reload_drive", lambda: calls.append("drive"))

    app._activate_profile(ID2)

    assert store.active_id == ID2
    assert calls == ["reset", "programs", "ui", "drive"]


def test_activate_profile_muestra_el_error_y_no_cambia(app, store, monkeypatch):
    _add_profile(store, ID1)
    store.set_active(ID1)
    monkeypatch.setattr(
        app.accounts, "switch", Mock(side_effect=RuntimeError("fallo"))
    )
    refresh = Mock()
    monkeypatch.setattr(app, "_refresh_account_ui", refresh)

    app._activate_profile(ID2)

    assert store.active_id == ID1
    assert refresh.called
    assert "No se pudo activar la cuenta: fallo" == (
        app._status_label.cget("text")
    )


def test_active_auth_paths_devuelve_los_del_perfil(app, store, accounts):
    profile = _add_profile(store, ID1)
    accounts.switch(profile.id)

    paths = app._active_auth_paths()

    assert paths == AuthPaths(
        client_secrets=store.paths_for(profile.id).credentials,
        token=store.paths_for(profile.id).token,
    )


def test_active_auth_paths_sin_cuenta_falla(app):
    with pytest.raises(RuntimeError, match="cuenta activa"):
        app._active_auth_paths()


# -- arranque --------------------------------------------------------------
def test_startup_sin_cuentas_muestra_estado_vacio(app):
    app._startup()

    assert app.model is None
    assert "Añade una cuenta" in app._status_label.cget("text")


def test_startup_carga_la_cuenta_activa(app, store, accounts, monkeypatch):
    profile = _add_profile(store, ID1)
    accounts.switch(profile.id)
    load_programs = Mock()
    reload_drive = Mock()
    monkeypatch.setattr(app, "_load_programs_for_active", load_programs)
    monkeypatch.setattr(app, "reload_drive", reload_drive)

    app._startup()

    load_programs.assert_called_once_with()
    reload_drive.assert_called_once_with()


def test_startup_activa_la_primera_cuenta_si_no_hay_activa(
    app, store, accounts, monkeypatch
):
    profile = _add_profile(store, ID1)
    monkeypatch.setattr(app, "reload_drive", Mock())
    monkeypatch.setattr(app, "_load_programs_for_active", Mock())

    app._startup()

    assert store.active_id == profile.id


def test_startup_informa_del_error_al_activar(app, store, monkeypatch):
    _add_profile(store, ID1)
    monkeypatch.setattr(
        app.accounts, "switch", Mock(side_effect=RuntimeError("roto"))
    )

    app._startup()

    assert "No se pudo activar la cuenta: roto" == (
        app._status_label.cget("text")
    )


def test_startup_informa_si_falla_la_migracion(app, store, monkeypatch):
    profile = _add_profile(store, ID1)
    store.set_active(profile.id)
    monkeypatch.setattr(
        app.accounts,
        "migrate_legacy",
        Mock(side_effect=RuntimeError("roto")),
    )
    monkeypatch.setattr(app, "_load_programs_for_active", Mock())

    app._startup()

    assert "credenciales antiguas" in app._status_label.cget("text")


def test_startup_migra_e_informa(app, store, accounts, monkeypatch):
    profile = _add_profile(store, ID1)
    monkeypatch.setattr(
        app.accounts,
        "migrate_legacy",
        Mock(return_value=profile),
    )
    monkeypatch.setattr(app, "_load_programs_for_active", Mock())
    monkeypatch.setattr(app, "reload_drive", Mock())

    app._startup()

    assert "Predeterminada" in app._status_label.cget("text")


def test_startup_tras_cerrar_no_hace_nada(app, monkeypatch):
    migrate = Mock()
    monkeypatch.setattr(app.accounts, "migrate_legacy", migrate)
    app._closing = True

    app._startup()

    migrate.assert_not_called()


# -- programas por cuenta --------------------------------------------------
def test_carga_los_programas_de_la_cuenta_activa(app, store, accounts):
    profile = _add_profile(store, ID1)
    accounts.switch(profile.id)
    repository = ProgramRepository(store.paths_for(profile.id).programs)
    repository.save([_definition()])

    app._load_programs_for_active()

    assert [item.program for item in app.store] == ["Power BI"]
    assert len(app.programs_tab.tree.get_children("")) == 1


def test_carga_programas_sin_cuenta_vacia_el_registro(app, store):
    app.store.add(_definition())

    app._load_programs_for_active()

    assert app.store.items() == ()
    assert app.programs_tab.tree.get_children("") == ()


def test_carga_programas_avisa_de_entradas_omitidas(
    app, store, accounts, tmp_path
):
    profile = _add_profile(store, ID1)
    accounts.switch(profile.id)
    path = store.paths_for(profile.id).programs
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"version": 1, "programs": [{"program": "", "pattern": "X", '
        '"destination_path": "Y"}]}',
        encoding="utf-8",
    )

    app._load_programs_for_active()

    assert app.store.items() == ()
    assert "omitieron" in app._status_label.cget("text")


def test_guarda_los_programas_de_la_cuenta_activa(app, store, accounts):
    profile = _add_profile(store, ID1)
    accounts.switch(profile.id)
    app.store.add(_definition())

    app._save_programs()

    saved = ProgramRepository(store.paths_for(profile.id).programs).load()
    assert [item.program for item in saved.items] == ["Power BI"]


def test_guarda_programas_sin_cuenta_no_escribe_nada(app, tmp_path):
    app.store.add(_definition())

    app._save_programs()

    assert not list(tmp_path.rglob("programs.json"))


def test_guarda_programas_no_hace_nada_mientras_se_suspende(app, store):
    profile = _add_profile(store, ID1)
    store.set_active(profile.id)
    app.store.add(_definition())
    app._suspend_program_save = True

    app._save_programs()

    assert not store.paths_for(profile.id).programs.exists()


def test_guarda_programas_informa_del_error(app, store, monkeypatch):
    profile = _add_profile(store, ID1)
    store.set_active(profile.id)
    app.store.add(_definition())
    monkeypatch.setattr(
        "src.ui.app.ProgramRepository.save",
        Mock(side_effect=OSError("sin espacio")),
    )

    app._save_programs()

    assert "No se pudieron guardar" in app._status_label.cget("text")


def test_cambio_en_los_programas_invalida_y_guarda(app, store, accounts):
    profile = _add_profile(store, ID1)
    accounts.switch(profile.id)
    invalidate = Mock()
    app.organize_tab.invalidate_plan = invalidate
    app.store.add(_definition())

    app._on_store_change(app.store)

    invalidate.assert_called_once_with()
    assert "1 programa" in app._summary_label.cget("text")
    assert store.paths_for(profile.id).programs.exists()


# -- eventos de cuentas ----------------------------------------------------
def test_on_profile_added_activa_la_cuenta(app, monkeypatch):
    activate = Mock()
    monkeypatch.setattr(app, "_activate_profile", activate)

    app._on_profile_added(ID1)

    activate.assert_called_once_with(ID1)


def test_on_profile_removed_activa_la_siguiente(app, store, monkeypatch):
    _add_profile(store, ID1)
    _add_profile(store, ID2, "Personal")
    _add_profile(store, "c" * 32, "Otra")
    store.set_active(ID1)
    store.remove(ID1)
    activate = Mock()
    monkeypatch.setattr(app, "_activate_profile", activate)

    app._on_profile_removed(ID1)

    activate.assert_called_once_with(ID2)


def test_on_profile_removed_sin_cuentas_limpia_el_estado(app, monkeypatch):
    reset = Mock()
    monkeypatch.setattr(app, "_reset_drive_state", reset)
    app.store.add(_definition())

    app._on_profile_removed(ID1)

    reset.assert_called_once_with()
    assert app.store.items() == ()
    assert "No hay cuentas configuradas" in app._status_label.cget("text")


def test_on_profile_removed_de_otra_cuenta_solo_refresca(
    app, store, monkeypatch
):
    _add_profile(store, ID1)
    _add_profile(store, ID2, "Personal")
    store.set_active(ID2)
    reset = Mock()
    monkeypatch.setattr(app, "_reset_drive_state", reset)
    refresh = Mock()
    monkeypatch.setattr(app, "_refresh_account_ui", refresh)

    app._on_profile_removed(ID1)

    reset.assert_not_called()
    refresh.assert_called_once_with()


def test_on_connected_recarga_solo_si_es_la_activa(app, store, monkeypatch):
    _add_profile(store, ID1)
    _add_profile(store, ID2, "Personal")
    store.set_active(ID1)
    reload_drive = Mock()
    monkeypatch.setattr(app, "reload_drive", reload_drive)

    app._on_connected(ID2)
    reload_drive.assert_not_called()

    app._on_connected(ID1)
    reload_drive.assert_called_once_with()


def test_on_credentials_replaced_invalida_solo_la_activa(
    app, store, monkeypatch
):
    _add_profile(store, ID1)
    _add_profile(store, ID2, "Personal")
    store.set_active(ID1)
    reset = Mock()
    monkeypatch.setattr(app, "_reset_drive_state", reset)

    app._on_credentials_replaced(ID2)
    reset.assert_not_called()

    app._on_credentials_replaced(ID1)
    reset.assert_called_once_with()
    assert "Credenciales reemplazadas" in app._status_label.cget("text")


def test_on_profiles_changed_refresca_la_interfaz(app, monkeypatch):
    refresh = Mock()
    monkeypatch.setattr(app, "_refresh_account_ui", refresh)

    app._on_profiles_changed()

    refresh.assert_called_once_with()


def test_refresh_account_ui_sincroniza_menu_y_pestana(app, monkeypatch):
    menu = Mock()
    tab = Mock()
    monkeypatch.setattr(app, "_refresh_account_menu", menu)
    monkeypatch.setattr(app, "accounts_tab", tab)

    app._refresh_account_ui()

    menu.assert_called_once_with()
    tab.refresh.assert_called_once_with()


# -- Drive -----------------------------------------------------------------
def test_reset_drive_state_descarta_el_arbol(app, store):
    profile = _add_profile(store, ID1)
    store.set_active(profile.id)
    app.model = FolderTreeModel([], root_id="raiz")
    generation = app._drive_generation

    app._reset_drive_state()

    assert app.model is None
    assert app._drive_generation == generation + 1
    assert app._loading_drive is False
    assert app._reload_button.cget("state") == "normal"


def test_reload_drive_sin_cuenta_avisa(app):
    DriveOrganizerApp.reload_drive(app)

    assert app.model is None
    assert "Añade una cuenta" in app._status_label.cget("text")


def test_reload_drive_no_hace_nada_si_esta_cargando(app, store, monkeypatch):
    _add_profile(store, ID1)
    app._loading_drive = True
    thread = Mock()
    monkeypatch.setattr(app_module.threading, "Thread", thread)

    DriveOrganizerApp.reload_drive(app)

    thread.assert_not_called()


def test_reload_drive_informa_si_falla_la_ruta(app, store, monkeypatch):
    profile = _add_profile(store, ID1)
    store.set_active(profile.id)
    monkeypatch.setattr(
        app.accounts, "paths_for", Mock(side_effect=RuntimeError("roto"))
    )

    DriveOrganizerApp.reload_drive(app)

    assert "No se pudo preparar la cuenta: roto" == (
        app._status_label.cget("text")
    )


def test_reload_drive_lanza_el_trabajador(app, store, monkeypatch):
    profile = _add_profile(store, ID1, "Trabajo")
    store.set_active(profile.id)
    worker = Mock()
    monkeypatch.setattr(app, "_load_drive_worker", worker)
    started: list[dict] = []

    class FakeThread:
        def __init__(self, *, target, args=(), daemon=None):
            started.append({"target": target, "args": args})

        def start(self):
            started[-1]["target"](*started[-1]["args"])

    monkeypatch.setattr(app_module.threading, "Thread", FakeThread)

    DriveOrganizerApp.reload_drive(app)

    assert app._loading_drive
    worker.assert_called_once()
    args = worker.call_args.args
    assert args[0] == AuthPaths(
        client_secrets=store.paths_for(profile.id).credentials,
        token=store.paths_for(profile.id).token,
    )
    assert args[1] == app._drive_generation
    assert "Trabajo" in app._status_label.cget("text")
    assert app._reload_button.cget("state") == "disabled"


def test_load_drive_worker_carga_el_modelo(app, monkeypatch):
    monkeypatch.setattr(app, "_schedule", lambda cb, *args: cb(*args))
    monkeypatch.setattr(
        "src.authentication.auth.get_credentials", lambda **_kwargs: object()
    )
    monkeypatch.setattr(
        "src.drive.drive_client.get_service", lambda _creds: object()
    )
    monkeypatch.setattr(
        "src.drive.drive_client.get_root_id", lambda _service: "raiz"
    )
    monkeypatch.setattr(
        "src.drive.drive_client.list_folders", lambda _service: []
    )
    app._loading_drive = True

    app._load_drive_worker(AuthPaths("c.json", "t.json"), 0, None)

    assert app.model is not None
    assert app.programs_tab._model is app.model
    assert app.organize_tab._model is app.model
    assert "carpetas de Drive cargadas" in app._status_label.cget("text")


def test_load_drive_worker_informa_del_error(app, monkeypatch):
    monkeypatch.setattr(app, "_schedule", lambda cb, *args: cb(*args))
    monkeypatch.setattr(
        "src.authentication.auth.get_credentials",
        Mock(side_effect=RuntimeError("sin red")),
    )
    app._loading_drive = True

    app._load_drive_worker(AuthPaths("c.json", "t.json"), 0, None)

    assert app.model is None
    assert "No se pudo conectar con Drive: sin red" == (
        app._status_label.cget("text")
    )


def test_on_drive_loaded_ignora_resultados_antiguos(app):
    model = FolderTreeModel([], root_id="raiz")
    app._drive_generation = 5

    app._on_drive_loaded(model, 4)

    assert app.model is None


def test_on_drive_loaded_aplica_el_modelo_actual(app):
    model = FolderTreeModel([], root_id="raiz")
    app._drive_generation = 5
    app._loading_drive = True

    app._on_drive_loaded(model, 5)

    assert not app._loading_drive
    assert app.model is model
    assert app._reload_button.cget("state") == "normal"


def test_on_drive_error_ignora_resultados_antiguos(app):
    app._drive_generation = 5
    app._loading_drive = True

    app._on_drive_error(RuntimeError("roto"), 4)

    assert app._loading_drive


def test_on_drive_error_aplica_el_error_actual(app):
    app._drive_generation = 5
    app._loading_drive = True

    app._on_drive_error(RuntimeError("roto"), 5)

    assert not app._loading_drive
    assert app.model is None
    assert "No se pudo conectar con Drive: roto" == (
        app._status_label.cget("text")
    )


# -- cierre y errores de Tk ------------------------------------------------
def test_on_close_marca_el_cierre(app):
    app._on_close()

    assert app._closing


def test_reporte_de_excepcion_usa_la_barra_de_estado(app, monkeypatch):
    monkeypatch.setattr(app_module.traceback, "print_exception", Mock())

    app._report_callback_exception(RuntimeError, RuntimeError("roto"), None)

    assert "Error inesperado: roto" == app._status_label.cget("text")


def test_schedule_ejecuta_el_callback_en_el_hilo_principal(app):
    callback = Mock()

    app._schedule(callback, "listo")
    app.update()

    callback.assert_called_once_with("listo")


def test_schedule_ignora_el_callback_al_cerrar(app):
    callback = Mock()
    app._closing = True

    app._schedule(callback)

    callback.assert_not_called()


def test_schedule_ignora_el_callback_si_falla_after(app, monkeypatch):
    callback = Mock()
    monkeypatch.setattr(
        app, "after", Mock(side_effect=RuntimeError("ventana cerrada"))
    )

    app._schedule(callback)

    callback.assert_not_called()
