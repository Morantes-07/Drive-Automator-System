"""Pruebas para AccountService sin llamar a Google."""

import json

import pytest

from src.authentication.auth import AuthPaths, AuthenticationCancelled
from src.profiles import service as service_module
from src.profiles.credentials import ClientSecretsError
from src.profiles.models import AccountProfile
from src.profiles.service import AccountService, AccountServiceError
from src.profiles.store import ProfileStore

ID1 = "a" * 32
ID2 = "b" * 32


class FakeCredentials:
    def __init__(self, valid=True, expired=False, refresh_token="refresh"):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token

    def to_json(self):
        return '{"token": "nuevo"}'


def _write_credentials(path, client_id="cliente-1", project_id="proyecto-1"):
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": "secreto",
                    "project_id": project_id,
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _store(tmp_path):
    return ProfileStore(tmp_path)


def _service(tmp_path, store=None):
    return AccountService(
        store if store is not None else _store(tmp_path),
        legacy_credentials=tmp_path / "legacy-credentials.json",
        legacy_token=tmp_path / "legacy-token.json",
    )


def test_importa_copia_las_credenciales_y_crea_el_perfil(tmp_path):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    source = _write_credentials(tmp_path / "original.json")

    profile = service.import_client_secrets(source, name="Trabajo")

    paths = store.paths_for(profile.id)
    assert paths.credentials.exists()
    assert paths.credentials.read_text(encoding="utf-8") == source.read_text(
        encoding="utf-8"
    )
    assert profile.name == "Trabajo"
    assert profile.client_id == "cliente-1"
    assert profile.project_id == "proyecto-1"
    assert source.exists()


def test_importa_usa_el_proyecto_como_nombre_por_defecto(tmp_path):
    service = _service(tmp_path)
    source = _write_credentials(tmp_path / "original.json")

    profile = service.import_client_secrets(source)

    assert profile.name == "proyecto-1"


def test_importa_avisa_si_el_cliente_ya_existe(tmp_path):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    source = _write_credentials(tmp_path / "original.json")
    service.import_client_secrets(source, name="Uno")

    second = service.import_client_secrets(source, name="Dos")

    assert second.name == "Dos"
    assert "ya están asociadas" in service.last_warning


def test_importa_rechaza_credenciales_invalidas(tmp_path):
    service = _service(tmp_path)
    source = tmp_path / "malo.json"
    source.write_text("{}", encoding="utf-8")

    with pytest.raises(ClientSecretsError):
        service.import_client_secrets(source)

    assert len(service.store) == 0


def test_importa_limpia_si_falla_el_registro(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    source = _write_credentials(tmp_path / "original.json")

    monkeypatch.setattr(
        store, "add", lambda _profile: (_ for _ in ()).throw(RuntimeError("fallo"))
    )

    with pytest.raises(RuntimeError):
        service.import_client_secrets(source)

    assert not list((tmp_path / "profiles").glob("*"))


def test_importa_limpia_si_falla_la_copia(tmp_path, monkeypatch):
    service = _service(tmp_path)
    source = _write_credentials(tmp_path / "original.json")

    monkeypatch.setattr(
        service,
        "_copy_atomic",
        lambda *_args: (_ for _ in ()).throw(OSError("sin espacio")),
    )

    with pytest.raises(AccountServiceError, match="copiar"):
        service.import_client_secrets(source)


def test_importa_genera_un_id_que_no_colisione(tmp_path, monkeypatch):
    store = _store(tmp_path)
    store.add(AccountProfile(id=ID1, name="Existente"))
    service = _service(tmp_path, store)
    source = _write_credentials(tmp_path / "original.json")

    monkeypatch.setattr(
        "src.profiles.paths.generate_profile_id",
        lambda: next(ids),
    )
    ids = iter([ID1, ID2])

    profile = service.import_client_secrets(source)

    assert profile.id == ID2


def test_conecta_guarda_correo_y_nombre(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )

    credentials = FakeCredentials()
    monkeypatch.setattr(service_module, "get_credentials", lambda **_kwargs: credentials)
    monkeypatch.setattr(service_module, "get_service", lambda _creds: "servicio")
    monkeypatch.setattr(
        service_module,
        "get_user_profile",
        lambda _service: {"email": "user@example.com", "display_name": "User"},
    )

    updated = service.connect(profile.id)

    assert updated.email == "user@example.com"
    assert updated.account_name == "User"
    assert updated.last_used_at


def test_conecta_envia_login_hint_si_ya_habia_correo(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    store.update(
        AccountProfile(
            id=profile.id,
            name=profile.name,
            email="viejo@example.com",
        )
    )
    captured = {}

    def fake_get_credentials(**kwargs):
        captured.update(kwargs)
        return FakeCredentials()

    monkeypatch.setattr(service_module, "get_credentials", fake_get_credentials)
    monkeypatch.setattr(service_module, "get_service", lambda _creds: "servicio")
    monkeypatch.setattr(
        service_module,
        "get_user_profile",
        lambda _service: {"email": "viejo@example.com"},
    )

    service.connect(profile.id)

    assert captured["login_hint"] == "viejo@example.com"


def test_conecta_rechaza_un_correo_distinto(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    store.update(
        AccountProfile(id=profile.id, name=profile.name, email="a@example.com")
    )
    monkeypatch.setattr(service_module, "get_credentials", lambda **_k: FakeCredentials())
    monkeypatch.setattr(service_module, "get_service", lambda _c: "servicio")
    monkeypatch.setattr(
        service_module,
        "get_user_profile",
        lambda _s: {"email": "b@example.com"},
    )

    with pytest.raises(AccountServiceError, match="La cuenta autenticada"):
        service.connect(profile.id)

    assert store.get(profile.id).email == "a@example.com"


def test_conecta_rechaza_correo_duplicado(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    first = service.import_client_secrets(
        _write_credentials(tmp_path / "uno.json", client_id="cliente-1")
    )
    second = service.import_client_secrets(
        _write_credentials(tmp_path / "dos.json", client_id="cliente-2")
    )
    store.update(
        AccountProfile(id=first.id, name=first.name, email="user@example.com")
    )
    monkeypatch.setattr(service_module, "get_credentials", lambda **_k: FakeCredentials())
    monkeypatch.setattr(service_module, "get_service", lambda _c: "servicio")
    monkeypatch.setattr(
        service_module,
        "get_user_profile",
        lambda _s: {"email": "user@example.com"},
    )

    with pytest.raises(AccountServiceError, match="ya está asociado"):
        service.connect(second.id)


def test_conecta_rechaza_si_google_no_devuelve_correo(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    monkeypatch.setattr(service_module, "get_credentials", lambda **_k: FakeCredentials())
    monkeypatch.setattr(service_module, "get_service", lambda _c: "servicio")
    monkeypatch.setattr(service_module, "get_user_profile", lambda _s: {})

    with pytest.raises(AccountServiceError, match="correo"):
        service.connect(profile.id)


def test_conecta_propaga_autenticacion_cancelada(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )

    def cancelar(**_kwargs):
        raise AuthenticationCancelled("cancelado")

    monkeypatch.setattr(service_module, "get_credentials", cancelar)
    with pytest.raises(AuthenticationCancelled):
        service.connect(profile.id)


def test_refresh_sin_token_falla(tmp_path):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    with pytest.raises(AccountServiceError, match="no tiene una sesión"):
        service.refresh_profile(profile.id)


def test_refresh_con_token_valido_actualiza_uso(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    monkeypatch.setattr(service_module, "load_token", lambda _paths: FakeCredentials())

    updated = service.refresh_profile(profile.id)

    assert updated.last_used_at


def test_refresh_renueva_y_guarda_el_token(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    expired = FakeCredentials(valid=False, expired=True)
    renewed = FakeCredentials(valid=True)
    monkeypatch.setattr(service_module, "load_token", lambda _paths: expired)
    monkeypatch.setattr(service_module, "refresh", lambda _creds: renewed)

    service.refresh_profile(profile.id)

    assert store.paths_for(profile.id).token.read_text(encoding="utf-8") == renewed.to_json()


def test_refresh_con_error_de_renovacion(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    monkeypatch.setattr(
        service_module,
        "load_token",
        lambda _paths: FakeCredentials(valid=False, expired=True),
    )
    monkeypatch.setattr(service_module, "refresh", lambda _creds: None)

    with pytest.raises(AccountServiceError, match="revocado"):
        service.refresh_profile(profile.id)


def test_refresh_sin_refresh_token_pide_reconexion(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    monkeypatch.setattr(
        service_module,
        "load_token",
        lambda _paths: FakeCredentials(
            valid=False, expired=False, refresh_token=None
        ),
    )

    with pytest.raises(AccountServiceError, match="reconexión"):
        service.refresh_profile(profile.id)


def test_refresh_error_al_guardar_token(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    monkeypatch.setattr(
        service_module,
        "load_token",
        lambda _paths: FakeCredentials(valid=False, expired=True),
    )
    monkeypatch.setattr(
        service_module, "refresh", lambda _creds: FakeCredentials(valid=True)
    )

    class BadToken:
        def write_text(self, *_args, **_kwargs):
            raise OSError("sin permiso")

    monkeypatch.setattr(
        service,
        "paths_for",
        lambda _profile_id: AuthPaths(
            client_secrets=tmp_path / "c.json", token=BadToken()
        ),
    )

    with pytest.raises(AccountServiceError, match="guardar el token"):
        service.refresh_profile(profile.id)


def test_reemplaza_credenciales_y_borra_el_token(tmp_path):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    paths = store.paths_for(profile.id)
    paths.token.write_text('{"token": "viejo"}', encoding="utf-8")
    source = _write_credentials(
        tmp_path / "nuevo.json", client_id="cliente-2", project_id="proyecto-2"
    )

    updated = service.replace_client_secrets(profile.id, source)

    assert updated.client_id == "cliente-2"
    assert updated.project_id == "proyecto-2"
    assert not paths.token.exists()
    assert "cliente-2" in paths.credentials.read_text(encoding="utf-8")
    assert source.exists()


def test_reemplaza_credenciales_error_de_copia(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    monkeypatch.setattr(
        service,
        "_copy_atomic",
        lambda *_args: (_ for _ in ()).throw(OSError("fallo")),
    )

    with pytest.raises(AccountServiceError, match="reemplazar"):
        service.replace_client_secrets(
            profile.id, _write_credentials(tmp_path / "nuevo.json")
        )


def test_reemplaza_credenciales_error_al_borrar_token(tmp_path):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    store.paths_for(profile.id).token.mkdir()

    with pytest.raises(AccountServiceError, match="token anterior"):
        service.replace_client_secrets(
            profile.id, _write_credentials(tmp_path / "nuevo.json")
        )


def test_elimina_solo_los_archivos_administrados(tmp_path):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    source = _write_credentials(tmp_path / "original.json")
    profile = service.import_client_secrets(source)
    paths = store.paths_for(profile.id)

    removed = service.delete(profile.id)

    assert removed.id == profile.id
    assert not paths.directory.exists()
    assert source.exists()
    assert len(store) == 0


def test_elimina_sin_borrar_archivos(tmp_path):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    paths = store.paths_for(profile.id)

    service.delete(profile.id, remove_files=False)

    assert paths.directory.exists()


def test_elimina_falla_si_no_puede_borrar_la_carpeta(tmp_path, monkeypatch):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )
    monkeypatch.setattr(
        service_module.shutil,
        "rmtree",
        lambda *_args: (_ for _ in ()).throw(OSError("bloqueado")),
    )

    with pytest.raises(AccountServiceError, match="borrar"):
        service.delete(profile.id)

    assert len(store) == 1


def test_switch_actualiza_activo_y_ultimo_uso(tmp_path):
    store = _store(tmp_path)
    service = _service(tmp_path, store)
    profile = service.import_client_secrets(
        _write_credentials(tmp_path / "original.json")
    )

    updated = service.switch(profile.id)

    assert store.active_id == profile.id
    assert updated.last_used_at
    assert service.active_paths().token == store.paths_for(profile.id).token


def test_active_paths_sin_cuenta(tmp_path):
    assert _service(tmp_path).active_paths() is None


def test_migra_credenciales_antiguas(tmp_path):
    creds = _write_credentials(tmp_path / "legacy-credentials.json")
    token = tmp_path / "legacy-token.json"
    token.write_text('{"token": "viejo"}', encoding="utf-8")
    store = _store(tmp_path)
    service = _service(tmp_path, store)

    profile = service.migrate_legacy()

    assert profile is not None
    assert profile.name == "Predeterminada"
    assert store.active_id == profile.id
    assert store.paths_for(profile.id).token.read_text(encoding="utf-8") == '{"token": "viejo"}'
    assert creds.exists()


def test_migra_no_hace_nada_si_ya_hay_perfiles(tmp_path):
    store = _store(tmp_path)
    store.add(AccountProfile(id=ID1, name="Uno"))
    service = _service(tmp_path, store)
    _write_credentials(tmp_path / "legacy-credentials.json")

    assert service.migrate_legacy() is None


def test_migra_no_hace_nada_sin_credenciales(tmp_path):
    assert _service(tmp_path).migrate_legacy() is None


def test_migra_sigue_si_no_puede_copiar_el_token(tmp_path, monkeypatch):
    _write_credentials(tmp_path / "legacy-credentials.json")
    (tmp_path / "legacy-token.json").write_text("{}", encoding="utf-8")
    service = _service(tmp_path)
    original = AccountService._copy_atomic

    def fake_copy(source, destination):
        if destination.name == "token.json":
            raise OSError("fallo")
        return original(source, destination)

    monkeypatch.setattr(AccountService, "_copy_atomic", staticmethod(fake_copy))

    profile = service.migrate_legacy()

    assert profile is not None
    assert service.store.active_id == profile.id
