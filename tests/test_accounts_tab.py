"""Pruebas de la pestaña de cuentas con widgets reales."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from src.authentication.auth import AuthPaths, AuthenticationCancelled
from src.profiles.models import AccountProfile
from src.profiles.store import ProfileStore
from src.ui import accounts_tab as accounts_tab_module
from src.ui.accounts_tab import AccountsTab, STATUS_LABELS

ID1 = "a" * 32
ID2 = "b" * 32


class FakeService:
    """Servicio mínimo para probar la pestaña sin tocar Google."""

    def __init__(self, store):
        self.store = store
        self.last_warning = None
        self.import_error = None
        self.connect_error = None
        self.refresh_error = None
        self.replace_error = None
        self.delete_error = None
        self.profile = None

    def paths_for(self, profile_id):
        paths = self.store.paths_for(profile_id)
        return AuthPaths(paths.credentials, paths.token)

    def import_client_secrets(self, source, name=None):
        if self.import_error:
            raise self.import_error
        return self.profile

    def connect(self, profile_id, browser_provider=None):
        if self.connect_error:
            raise self.connect_error
        return self.profile

    def refresh_profile(self, profile_id):
        if self.refresh_error:
            raise self.refresh_error
        return self.profile

    def replace_client_secrets(self, profile_id, source):
        if self.replace_error:
            raise self.replace_error
        return self.profile

    def delete(self, profile_id):
        if self.delete_error:
            raise self.delete_error
        return self.profile


@pytest.fixture
def store(tmp_path):
    store = ProfileStore(tmp_path)
    store.add(
        AccountProfile(
            id=ID1,
            name="Trabajo",
            email="work@example.com",
            project_id="proyecto-1",
        )
    )
    store.add(
        AccountProfile(
            id=ID2,
            name="Personal",
            email="home@example.com",
            project_id="proyecto-2",
        )
    )
    store.set_active(ID1)
    return store


@pytest.fixture
def tab(tk_root, store):
    service = FakeService(store)
    widget = AccountsTab(
        tk_root,
        store,
        service,
        on_switch=Mock(),
        on_profile_added=Mock(),
        on_profile_removed=Mock(),
        on_connected=Mock(),
        on_credentials_replaced=Mock(),
        on_profiles_changed=Mock(),
    )
    widget.pack(fill="both", expand=True)
    tk_root.update_idletasks()
    yield widget
    widget.destroy()


def test_sin_cuentas_muestra_estado_vacio(tk_root, tmp_path):
    store = ProfileStore(tmp_path)
    widget = AccountsTab(tk_root, store, FakeService(store))
    try:
        tk_root.update_idletasks()
        assert widget._active_name_label.cget("text") == "Sin cuenta activa"
        assert widget._count_label.cget("text") == "0 cuentas"
        assert widget._empty_label.place_info()
        assert widget._connect_button.cget("state") == "disabled"
        assert widget._add_button.cget("state") == "normal"
    finally:
        widget.destroy()


def test_pinta_las_cuentas_y_la_activa(tab, monkeypatch):
    monkeypatch.setattr(
        "src.ui.accounts_tab.token_status", lambda _paths: "valid"
    )

    tab.refresh()

    assert tab._active_name_label.cget("text") == "Trabajo"
    assert "work@example.com" in tab._active_detail_label.cget("text")
    assert len(tab.tree.get_children("")) == 2
    assert tab._count_label.cget("text") == "2 cuentas"
    assert tab._active_status_label.cget("text") == STATUS_LABELS["valid"]
    assert not tab._empty_label.place_info()
    assert tab.tree.selection() == (ID1,)


def test_seleccionar_otra_cuenta_habilita_usar(tab):
    tab.tree.selection_set(ID2)
    tab._update_buttons()

    assert tab._use_button.cget("state") == "normal"
    tab._use_selected()
    tab._on_switch.assert_called_once_with(ID2)


def test_usar_la_cuenta_activa_no_hace_nada(tab):
    tab.tree.selection_set(ID1)
    tab._update_buttons()
    tab._use_selected()
    tab._on_switch.assert_not_called()


def test_add_account_pide_archivo_y_nombre(tab, monkeypatch):
    start = Mock()
    monkeypatch.setattr(tab, "_start_worker", start)
    monkeypatch.setattr(
        "src.ui.accounts_tab.filedialog.askopenfilename",
        lambda **_kwargs: str(Path("C:/creds.json")),
    )
    monkeypatch.setattr(
        "src.ui.accounts_tab.simpledialog.askstring",
        lambda *_args, **_kwargs: "Nueva",
    )

    tab._add_account()

    assert tab.busy
    start.assert_called_once_with(tab._add_worker, Path("C:/creds.json"), "Nueva")


def test_add_account_no_hace_nada_si_cancela(tab, monkeypatch):
    start = Mock()
    monkeypatch.setattr(tab, "_start_worker", start)
    monkeypatch.setattr(
        "src.ui.accounts_tab.filedialog.askopenfilename",
        lambda **_kwargs: "",
    )

    tab._add_account()

    start.assert_not_called()
    assert not tab.busy


def test_add_account_no_hace_nada_si_cancela_el_nombre(tab, monkeypatch):
    start = Mock()
    monkeypatch.setattr(tab, "_start_worker", start)
    monkeypatch.setattr(
        "src.ui.accounts_tab.filedialog.askopenfilename",
        lambda **_kwargs: "C:/creds.json",
    )
    monkeypatch.setattr(
        "src.ui.accounts_tab.simpledialog.askstring",
        lambda *_args, **_kwargs: None,
    )

    tab._add_account()

    start.assert_not_called()
    assert not tab.busy


def test_add_done_notifica_y_activa(tab):
    profile = tab._store.get(ID1)
    tab._set_busy(True)

    tab._on_add_done(profile, None)

    assert not tab.busy
    tab._on_profiles_changed.assert_called_once_with()
    tab._on_profile_added.assert_called_once_with(profile.id)
    assert "añadida" in tab._message_label.cget("text")


def test_add_sin_sesion_conserva_el_perfil(tab):
    profile = tab._store.get(ID1)
    tab._set_busy(True)

    tab._on_add_without_session(profile, "aviso", RuntimeError("sin token"))

    assert not tab.busy
    tab._on_profiles_changed.assert_called_once_with()
    tab._on_profile_added.assert_not_called()
    assert "sin sesión" in tab._message_label.cget("text")


def test_connect_done_notifica(tab):
    profile = tab._store.get(ID1)

    tab._on_connect_done(profile)

    tab._on_profiles_changed.assert_called_once_with()
    tab._on_connected.assert_called_once_with(profile.id)
    assert "Sesión iniciada" in tab._message_label.cget("text")


def test_check_done_notifica(tab):
    profile = tab._store.get(ID1)

    tab._on_check_done(profile)

    tab._on_profiles_changed.assert_called_once_with()
    assert "válida" in tab._message_label.cget("text")


def test_replace_done_notifica(tab):
    profile = tab._store.get(ID1)

    tab._on_replace_done(profile)

    tab._on_profiles_changed.assert_called_once_with()
    tab._on_credentials_replaced.assert_called_once_with(profile.id)
    message = tab._message_label.cget("text")
    assert "reemplazadas" in message.casefold()
    assert "Conectar" in message


def test_delete_done_notifica(tab):
    profile = tab._store.get(ID2)

    tab._on_delete_done(profile)

    tab._on_profiles_changed.assert_called_once_with()
    tab._on_profile_removed.assert_called_once_with(profile.id)
    assert "eliminada" in tab._message_label.cget("text")


def test_error_de_autenticacion_cancelada(tab):
    tab._set_busy(True)

    tab._on_operation_error(AuthenticationCancelled("x"), "No se pudo")

    assert not tab.busy
    assert "cancelada" in tab._message_label.cget("text")


def test_error_generico_muestra_el_mensaje(tab):
    tab._set_busy(True)

    tab._on_operation_error(RuntimeError("fallo"), "No se pudo")

    assert not tab.busy
    assert "No se pudo: fallo" == tab._message_label.cget("text")


def test_error_vacio_usa_el_tipo_de_excepcion(tab):
    tab._on_operation_error(RuntimeError(), "Error")
    assert "RuntimeError" in tab._message_label.cget("text")


def test_busy_bloquea_las_acciones(tab, monkeypatch):
    start = Mock()
    monkeypatch.setattr(tab, "_start_worker", start)
    tab._set_busy(True)

    tab._add_account()
    tab._connect_active()
    tab._check_active()
    tab._replace_credentials()
    tab._delete_selected()

    start.assert_not_called()
    assert tab._add_button.cget("state") == "disabled"


def test_seleccion_inexistente_devuelve_none(tab):
    tab.tree.insert("", "end", iid="f" * 32, values=("x",))
    tab.tree.selection_set("f" * 32)
    assert tab._selected_profile() is None


def test_status_color_y_timestamp():
    tab = AccountsTab.__new__(AccountsTab)
    assert tab._status_color("valid") == "success"
    assert tab._status_color("missing") == "muted"
    assert tab._status_color("refreshable") == "warning"
    assert AccountsTab._format_timestamp(None) == "—"
    assert AccountsTab._format_timestamp("2026-01-01T10:20:30+00:00") == (
        "2026-01-01 10:20"
    )


@pytest.mark.parametrize(
    "method, error_attr, expected",
    [
        ("_add_worker", "import_error", "importar"),
        ("_connect_worker", "connect_error", "conectar"),
        ("_check_worker", "refresh_error", "renovar"),
        ("_replace_worker", "replace_error", "reemplazar"),
        ("_delete_worker", "delete_error", "eliminar"),
    ],
)
def test_workers_propagan_errores(tab, monkeypatch, method, error_attr, expected):
    monkeypatch.setattr(tab, "_schedule", lambda callback, *args: callback(*args))
    setattr(tab._service, error_attr, RuntimeError("fallo"))
    tab._set_busy(True)

    if method == "_add_worker":
        getattr(tab, method)(Path("C:/creds.json"), "Nueva")
    elif method == "_replace_worker":
        getattr(tab, method)(ID1, Path("C:/creds.json"))
    else:
        getattr(tab, method)(ID1)

    assert not tab.busy
    assert expected in tab._message_label.cget("text").casefold()


def test_workers_exitosos(tab, monkeypatch):
    monkeypatch.setattr(tab, "_schedule", lambda callback, *args: callback(*args))
    tab._service.profile = tab._store.get(ID1)
    tab._set_busy(True)

    tab._connect_worker(ID1)

    assert not tab.busy
    assert "Sesión iniciada" in tab._message_label.cget("text")


def test_add_worker_exitoso(tab, monkeypatch):
    monkeypatch.setattr(tab, "_schedule", lambda callback, *args: callback(*args))
    profile = tab._store.get(ID1)
    tab._service.profile = profile
    tab._service.last_warning = "aviso"
    tab._set_busy(True)

    tab._add_worker(Path("C:/creds.json"), "Nueva")

    assert not tab.busy
    tab._on_profile_added.assert_called_once_with(profile.id)
    assert "aviso" in tab._message_label.cget("text")


# -- ejecución diferida a Tk ----------------------------------------------
def test_start_worker_lanza_el_objetivo(tab, monkeypatch):
    target = Mock()
    captured: dict[str, object] = {}

    class FakeThread:
        def __init__(self, *, target, args, daemon):
            captured.update(target=target, args=args, daemon=daemon)

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(accounts_tab_module.threading, "Thread", FakeThread)

    tab._start_worker(target, ID1, "extra")

    assert captured["target"] is target
    assert captured["args"] == (ID1, "extra")
    assert captured["daemon"] is True
    assert captured["started"] is True


def test_schedule_ejecuta_el_callback_en_el_hilo_principal(tab, tk_root):
    callback = Mock()

    tab._schedule(callback, "listo")
    tk_root.update()

    callback.assert_called_once_with("listo")


def test_schedule_ignora_el_callback_si_falla_after(tab, monkeypatch):
    callback = Mock()
    monkeypatch.setattr(
        tab, "after", Mock(side_effect=RuntimeError("ventana cerrada"))
    )

    tab._schedule(callback)

    callback.assert_not_called()
