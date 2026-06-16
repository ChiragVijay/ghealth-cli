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


def test_subscribers_list_requires_cloud_platform_scope(mock_keyring) -> None:
    _setup_auth(mock_keyring)

    result = runner.invoke(app, ["--format", "json", "subscribers", "list", "--project", "my-project"])

    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "cloud_platform_scope_required"
    assert data["error"]["details"]["suggested_scope"] == "cloud-platform"


def test_subscribers_list_table_shows_documented_fields(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring, scope="https://www.googleapis.com/auth/cloud-platform")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v4/projects/my-project/subscribers"
        return httpx.Response(
            200,
            json={
                "subscribers": [
                    {
                        "name": "projects/my-project/subscribers/my-sub",
                        "endpointUri": "https://example.com/webhooks/google-health",
                        "subscriberConfigs": [{"dataTypes": ["steps", "sleep"]}],
                    },
                ],
            },
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["subscribers", "list", "--project", "my-project"])

    assert result.exit_code == 0
    assert "my-sub" in result.stdout
    assert "https://example.com/webhooks/google-health" in result.stdout
    assert "steps, sleep" in result.stdout


def test_subscribers_create_builds_payload(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring, scope="https://www.googleapis.com/auth/cloud-platform")
    captured = {"path": "", "subscriber_id": "", "body": b""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["subscriber_id"] = request.url.params.get("subscriberId", "")
        captured["body"] = request.read()
        return httpx.Response(200, json={"name": "operations/subscriber-create"})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "subscribers",
            "create",
            "--project",
            "my-project",
            "--endpoint-uri",
            "https://example.com/webhooks/google-health",
            "--data-types",
            "steps,sleep",
            "--authorization-secret",
            "Bearer secret",
            "--subscriber-id",
            "my-sub",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/projects/my-project/subscribers"
    assert captured["subscriber_id"] == "my-sub"
    assert json.loads(captured["body"]) == {
        "endpointUri": "https://example.com/webhooks/google-health",
        "subscriberConfigs": [
            {
                "dataTypes": ["steps", "sleep"],
                "subscriptionCreatePolicy": "MANUAL",
            },
        ],
        "endpointAuthorization": {"secret": "Bearer secret"},
    }


def test_subscribers_update_uses_body_and_update_mask(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring, scope="https://www.googleapis.com/auth/cloud-platform")
    body_file = tmp_path / "subscriber.json"
    body_file.write_text(json.dumps({"endpointUri": "https://example.com/new"}), encoding="utf-8")
    captured = {"path": "", "mask": "", "body": b""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["mask"] = request.url.params.get("updateMask", "")
        captured["body"] = request.read()
        return httpx.Response(200, json={"name": "operations/subscriber-update"})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "subscribers",
            "update",
            "projects/my-project/subscribers/my-sub",
            "--body",
            str(body_file),
            "--update-mask",
            "endpointUri",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/projects/my-project/subscribers/my-sub"
    assert captured["mask"] == "endpointUri"
    assert json.loads(captured["body"]) == {"endpointUri": "https://example.com/new"}


def test_subscribers_delete_sends_force_with_yes(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring, scope="https://www.googleapis.com/auth/cloud-platform")
    captured = {"path": "", "force": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["force"] = request.url.params.get("force", "")
        return httpx.Response(200, json={"name": "operations/subscriber-delete"})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "subscribers",
            "delete",
            "projects/my-project/subscribers/my-sub",
            "--force",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert captured == {"path": "/v4/projects/my-project/subscribers/my-sub", "force": "true"}


def test_subscriptions_list_sends_filter_and_renders_table(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring, scope="https://www.googleapis.com/auth/cloud-platform")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("filter") == 'user = "users/123"'
        return httpx.Response(
            200,
            json={
                "subscriptions": [
                    {
                        "name": "projects/my-project/subscribers/my-sub/subscriptions/sub-1",
                        "user": "users/123",
                        "dataTypes": ["steps", "sleep"],
                    },
                ],
            },
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "subscriptions",
            "list",
            "--subscriber",
            "projects/my-project/subscribers/my-sub",
            "--filter",
            'user = "users/123"',
        ],
    )

    assert result.exit_code == 0
    assert "sub-1" in result.stdout
    assert "users/123" in result.stdout
    assert "steps, sleep" in result.stdout


def test_subscriptions_create_builds_payload(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring, scope="https://www.googleapis.com/auth/cloud-platform")
    captured = {"path": "", "subscription_id": "", "body": b""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["subscription_id"] = request.url.params.get("subscriptionId", "")
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={"name": "projects/my-project/subscribers/my-sub/subscriptions/sub-1"},
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "subscriptions",
            "create",
            "--subscriber",
            "projects/my-project/subscribers/my-sub",
            "--user",
            "users/123",
            "--data-types",
            "steps,sleep",
            "--subscription-id",
            "sub-1",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/projects/my-project/subscribers/my-sub/subscriptions"
    assert captured["subscription_id"] == "sub-1"
    assert json.loads(captured["body"]) == {"user": "users/123", "dataTypes": ["steps", "sleep"]}


def test_subscriptions_update_and_delete(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring, scope="https://www.googleapis.com/auth/cloud-platform")
    body_file = tmp_path / "subscription.json"
    body_file.write_text(json.dumps({"dataTypes": ["sleep"]}), encoding="utf-8")
    requests: list[tuple[str, str, dict[str, str], dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read()) if request.content else None
        requests.append((request.method, request.url.path, dict(request.url.params), body))
        return httpx.Response(
            200, json={"name": "projects/my-project/subscribers/my-sub/subscriptions/sub-1"}
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    update = runner.invoke(
        app,
        [
            "--format",
            "json",
            "subscriptions",
            "update",
            "projects/my-project/subscribers/my-sub/subscriptions/sub-1",
            "--body",
            str(body_file),
            "--update-mask",
            "dataTypes",
        ],
    )
    delete = runner.invoke(
        app,
        [
            "--format",
            "json",
            "subscriptions",
            "delete",
            "projects/my-project/subscribers/my-sub/subscriptions/sub-1",
            "--yes",
        ],
    )

    assert update.exit_code == 0
    assert delete.exit_code == 0
    assert requests == [
        (
            "PATCH",
            "/v4/projects/my-project/subscribers/my-sub/subscriptions/sub-1",
            {"updateMask": "dataTypes"},
            {"dataTypes": ["sleep"]},
        ),
        ("DELETE", "/v4/projects/my-project/subscribers/my-sub/subscriptions/sub-1", {}, None),
    ]
