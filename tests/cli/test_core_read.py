import json
import time

import httpx
from typer.testing import CliRunner

import ghealth.cli
from ghealth.api import GHealthApiClient
from ghealth.auth.token_store import save_tokens
from ghealth.cli import app
from ghealth.config import Config, save_config

runner = CliRunner()


def _setup_auth(
    mock_keyring,
    *,
    scope: str = "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
) -> None:
    config = Config(client_id="id", client_secret="secret", token_storage="keyring")
    save_config(config)
    save_tokens(
        {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_at": int(time.time()) + 3600,
            "scope": scope,
        },
    )


def _patch_api_client(monkeypatch, handler: httpx.MockTransport) -> GHealthApiClient:
    http_client = httpx.Client(transport=handler, base_url="https://health.googleapis.com")
    config = Config(client_id="id", client_secret="secret", token_storage="keyring")
    tokens = {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "expires_at": int(time.time()) + 3600,
    }
    api_client = GHealthApiClient(config, tokens, client=http_client)

    def factory(*, client=None):
        if client is not None:
            return GHealthApiClient(config, tokens, client=client)
        return api_client

    monkeypatch.setattr(ghealth.cli, "create_authenticated_client", factory)
    return api_client


def test_user_identity_json(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"name": "users/me/identity", "googleUserId": "123"},
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", "user", "identity"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["name"] == "users/me/identity"
    assert data["googleUserId"] == "123"


def test_missing_config_exits_not_configured() -> None:
    result = runner.invoke(app, ["--format", "json", "user", "identity"])
    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "not_configured"


def test_missing_tokens_exits_not_authenticated(mock_keyring) -> None:
    save_config(Config(client_id="id", client_secret="secret", token_storage="keyring"))
    result = runner.invoke(app, ["--format", "json", "user", "identity"])
    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "not_authenticated"


def test_devices_list_json(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("pageSize") == "10"
        return httpx.Response(
            200,
            json={"pairedDevices": [{"name": "users/me/pairedDevices/watch"}]},
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", "devices", "list", "--page-size", "10"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["pairedDevices"][0]["name"] == "users/me/pairedDevices/watch"


def test_devices_list_limit_truncates_json_output(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "pairedDevices": [
                    {"name": "users/me/pairedDevices/a"},
                    {"name": "users/me/pairedDevices/b"},
                ],
            },
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", "devices", "list", "--limit", "1"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["pairedDevices"] == [{"name": "users/me/pairedDevices/a"}]
    assert data["limited"] is True


def test_devices_list_raw(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "pairedDevices": [
                    {"name": "users/me/pairedDevices/a"},
                    {"name": "users/me/pairedDevices/b"},
                ],
            },
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "raw", "devices", "list"])
    assert result.exit_code == 0
    lines = result.stdout.strip().split("\n")
    assert lines == [
        "users/me/pairedDevices/a",
        "users/me/pairedDevices/b",
    ]


def test_devices_list_table_shows_documented_device_fields(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "pairedDevices": [
                    {
                        "name": "users/me/pairedDevices/3095917910",
                        "deviceType": "TRACKER",
                        "deviceVersion": "Pixel Watch 3",
                        "batteryStatus": "High",
                        "batteryLevel": 87,
                        "lastSyncTime": "2026-06-12T13:00:00Z",
                    },
                ],
            },
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["devices", "list"])

    assert result.exit_code == 0
    assert "TRACKER" in result.stdout
    assert "Pixel Watch 3" in result.stdout
    assert "High (87%)" in result.stdout
    assert "2026-06-12T13:00:00Z" in result.stdout


def test_devices_get_table_shows_documented_device_fields(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "name": "users/me/pairedDevices/3095917910",
                "deviceType": "TRACKER",
                "deviceVersion": "Pixel Watch 3",
                "batteryStatus": "High",
                "batteryLevel": 87,
                "features": ["STEPS", "HEART_RATE"],
            },
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["devices", "get", "3095917910"])

    assert result.exit_code == 0
    assert "deviceVersion" in result.stdout
    assert "Pixel Watch 3" in result.stdout
    assert "STEPS, HEART_RATE" in result.stdout


def test_devices_list_all_combines_pages(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)

    def handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("pageToken")
        if token is None:
            return httpx.Response(
                200,
                json={
                    "pairedDevices": [{"name": "users/me/pairedDevices/a"}],
                    "nextPageToken": "t2",
                },
            )
        return httpx.Response(200, json={"pairedDevices": [{"name": "users/me/pairedDevices/b"}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", "devices", "list", "--all"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "nextPageToken" not in data
    assert len(data["pairedDevices"]) == 2


def test_api_403_becomes_missing_scope_or_forbidden(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"error": {"message": "insufficient scope", "status": "PERMISSION_DENIED"}},
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", "data-points", "list", "steps"])
    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "missing_scope_or_forbidden"
    assert "suggested_login_command" in data["error"]["details"]


def test_devices_scope_error_suggests_activity_scope(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring, scope="https://www.googleapis.com/auth/cloud-platform")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"error": {"message": "ACCESS_TOKEN_SCOPE_INSUFFICIENT", "status": "PERMISSION_DENIED"}},
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", "devices", "list"])

    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "missing_scope_or_forbidden"
    assert (
        data["error"]["details"]["required_scope"]
        == "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly"
    )
    assert data["error"]["details"]["suggested_scope"] == "activity_and_fitness.readonly"
    assert (
        data["error"]["details"]["suggested_combined_login_command"] == "ghealth auth login --with-webhooks"
    )
