"""Pruebas para src.authentication.auth."""

from unittest.mock import Mock

import pytest

from src.authentication import auth
from src.authentication.auth import AuthenticationCancelled
from src.authentication.browsers import BrowserOption, SYSTEM_DEFAULT


class FakeCredentials:
    """Credenciales mínimas para probar la lógica sin tocar Google."""

    def __init__(self, *, valid=True, expired=False, refresh_token="refresh"):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token

    def to_json(self):
        return '{"token": "fake"}'


@pytest.fixture
def token_file(tmp_path, monkeypatch):
    path = tmp_path / "token.json"
    monkeypatch.setattr(auth, "TOKEN_FILE", path)
    return path


def test_token_valido_no_abre_navegador(token_file, monkeypatch):
    creds = FakeCredentials(valid=True)
    provider = Mock(return_value=SYSTEM_DEFAULT)
    monkeypatch.setattr(auth, "load_token", lambda: creds)

    assert auth.get_credentials(browser_provider=provider) is creds

    provider.assert_not_called()
    assert not token_file.exists()


def test_refresco_exitoso_no_abre_navegador(token_file):
    expired = FakeCredentials(valid=False, expired=True)
    refreshed = FakeCredentials(valid=True)
    provider = Mock(return_value=SYSTEM_DEFAULT)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(auth, "load_token", lambda: expired)
        patch.setattr(auth, "refresh", lambda _creds: refreshed)
        assert auth.get_credentials(browser_provider=provider) is refreshed

    provider.assert_not_called()
    assert token_file.read_text() == refreshed.to_json()


def test_sin_token_usa_el_navegador_predeterminado(token_file):
    flow = Mock(return_value=FakeCredentials(valid=True))

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(auth, "load_token", lambda: None)
        patch.setattr(auth, "browser_flow", flow)
        result = auth.get_credentials()

    flow.assert_called_once_with(SYSTEM_DEFAULT)
    assert result.valid is True
    assert token_file.exists()


def test_refresco_fallido_pide_navegador(token_file):
    expired = FakeCredentials(valid=False, expired=True)
    chosen = BrowserOption("Google Chrome", r"C:\Chrome\chrome.exe")
    flow = Mock(return_value=FakeCredentials(valid=True))

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(auth, "load_token", lambda: expired)
        patch.setattr(auth, "refresh", lambda _creds: None)
        patch.setattr(auth, "browser_flow", flow)
        auth.get_credentials(browser_provider=lambda: chosen)

    flow.assert_called_once_with(chosen)


def test_cancelar_no_genera_token(token_file):
    flow = Mock()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(auth, "load_token", lambda: None)
        patch.setattr(auth, "browser_flow", flow)
        with pytest.raises(AuthenticationCancelled):
            auth.get_credentials(browser_provider=lambda: None)

    flow.assert_not_called()
    assert not token_file.exists()


def test_browser_flow_predeterminado_no_registra_navegador(monkeypatch):
    fake_flow = Mock()
    creds = FakeCredentials(valid=True)
    fake_flow.run_local_server.return_value = creds
    monkeypatch.setattr(
        auth.InstalledAppFlow,
        "from_client_secrets_file",
        Mock(return_value=fake_flow),
    )
    register = Mock()
    monkeypatch.setattr(auth.webbrowser, "register", register)

    assert auth.browser_flow(SYSTEM_DEFAULT) is creds

    register.assert_not_called()
    fake_flow.run_local_server.assert_called_once_with(
        port=0, prompt="select_account"
    )


def test_browser_flow_registra_el_ejecutable(monkeypatch):
    fake_flow = Mock()
    creds = FakeCredentials(valid=True)
    fake_flow.run_local_server.return_value = creds
    monkeypatch.setattr(
        auth.InstalledAppFlow,
        "from_client_secrets_file",
        Mock(return_value=fake_flow),
    )
    register = Mock()
    monkeypatch.setattr(auth.webbrowser, "register", register)
    chosen = BrowserOption("Google Chrome", r"C:\Chrome\chrome.exe")

    assert auth.browser_flow(chosen) is creds

    register.assert_called_once()
    assert register.call_args.args[0] == auth.BROWSER_REGISTRY_NAME
    browser = register.call_args.args[2]
    assert browser.name == chosen.executable
    assert browser.args == ["%s"]  # sin flags de modo privado
    fake_flow.run_local_server.assert_called_once_with(
        port=0,
        browser=auth.BROWSER_REGISTRY_NAME,
        prompt="select_account",
    )


def test_browser_flow_sin_argumento_usa_predeterminado(monkeypatch):
    fake_flow = Mock()
    fake_flow.run_local_server.return_value = FakeCredentials(valid=True)
    monkeypatch.setattr(
        auth.InstalledAppFlow,
        "from_client_secrets_file",
        Mock(return_value=fake_flow),
    )
    register = Mock()
    monkeypatch.setattr(auth.webbrowser, "register", register)

    auth.browser_flow()

    register.assert_not_called()
    fake_flow.run_local_server.assert_called_once_with(
        port=0, prompt="select_account"
    )


def test_load_token_ignora_archivo_corrupto(token_file, monkeypatch):
    token_file.write_text("{}")
    monkeypatch.setattr(
        auth.Credentials,
        "from_authorized_user_file",
        Mock(side_effect=ValueError("formato inválido")),
    )

    assert auth.load_token() is None
