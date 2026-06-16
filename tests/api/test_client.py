import json
import time

import httpx
import pytest

import ghealth.api.client
from ghealth.api import (
    GHealthApiClient,
    GHealthApiError,
    create_authenticated_client,
)
from ghealth.auth.token_store import load_tokens, save_tokens
from ghealth.config import Config, save_config


def _make_client(
    handler: httpx.MockTransport,
    *,
    expires_at: int | None = None,
) -> GHealthApiClient:
    config = Config(client_id="id", client_secret="secret", token_storage="plaintext")
    tokens = {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "expires_at": expires_at if expires_at is not None else int(time.time()) + 3600,
        "scope": "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    }
    http_client = httpx.Client(transport=handler, base_url="https://health.googleapis.com")
    return GHealthApiClient(config, tokens, client=http_client)


def test_client_adds_bearer_token() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={"name": "users/me/identity"})

    client = _make_client(httpx.MockTransport(handler))
    client.get_identity()
    assert captured_headers["authorization"] == "Bearer access-token"


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (400, "api_bad_request"),
        (403, "missing_scope_or_forbidden"),
        (404, "api_not_found"),
        (429, "rate_limited"),
        (500, "api_server_error"),
    ],
)
def test_http_errors_map_to_expected_codes(status_code: int, expected_code: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"error": {"message": "boom", "status": "FAILED", "details": [{"reason": "X"}]}},
        )

    client = _make_client(httpx.MockTransport(handler))
    with pytest.raises(GHealthApiError) as exc_info:
        client.get_identity()

    assert exc_info.value.code == expected_code
    assert exc_info.value.details["status_code"] == status_code


def test_malformed_json_success_maps_to_api_invalid_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    client = _make_client(httpx.MockTransport(handler))
    with pytest.raises(GHealthApiError) as exc_info:
        client.get_identity()
    assert exc_info.value.code == "api_invalid_response"


def test_network_error_maps_to_api_request_failed() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    client = _make_client(httpx.MockTransport(handler))
    with pytest.raises(GHealthApiError) as exc_info:
        client.get_identity()
    assert exc_info.value.code == "api_request_failed"


def test_401_refresh_once_saves_tokens_and_retries(monkeypatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(401, json={"error": {"message": "expired"}})
        assert request.headers["authorization"] == "Bearer new-access-token"
        return httpx.Response(200, json={"name": "users/me/identity"})

    def mock_refresh(config, refresh_token):
        assert refresh_token == "refresh-token"
        return {
            "access_token": "new-access-token",
            "expires_at": int(time.time()) + 3600,
        }

    monkeypatch.setattr(ghealth.api.client, "refresh_access_token", mock_refresh)
    monkeypatch.setattr(ghealth.api.client, "save_tokens", save_tokens)

    config = Config(client_id="id", client_secret="secret", token_storage="plaintext")
    save_config(config)
    tokens = {
        "access_token": "old-access-token",
        "refresh_token": "refresh-token",
        "expires_at": int(time.time()) + 3600,
        "scope": "scope-a scope-b",
    }
    save_tokens(tokens)
    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://health.googleapis.com",
    )

    client = GHealthApiClient(config, tokens, client=http_client)
    result = client.get_identity()

    assert result["name"] == "users/me/identity"
    assert calls["count"] == 2
    saved = load_tokens()
    assert saved is not None
    assert saved["access_token"] == "new-access-token"
    assert saved["scope"] == "scope-a scope-b"


def test_create_authenticated_client_refreshes_expired_token(monkeypatch) -> None:
    config = Config(client_id="id", client_secret="secret", token_storage="plaintext")
    save_config(config)
    save_tokens(
        {
            "access_token": "old",
            "refresh_token": "refresh",
            "expires_at": int(time.time()) - 10,
            "scope": "sleep",
        },
    )

    refreshed = {"called": False}

    def mock_refresh(cfg, refresh_token):
        refreshed["called"] = True
        return {
            "access_token": "fresh",
            "refresh_token": refresh_token,
            "expires_at": int(time.time()) + 3600,
        }

    monkeypatch.setattr(ghealth.api.client, "refresh_access_token", mock_refresh)

    client = create_authenticated_client(client=httpx.Client(base_url="https://health.googleapis.com"))
    assert refreshed["called"] is True
    assert client._tokens["access_token"] == "fresh"
    client.close()


def test_paginate_all_combines_pages() -> None:
    pages = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        pages["count"] += 1
        token = request.url.params.get("pageToken")
        if token is None:
            return httpx.Response(
                200,
                json={
                    "pairedDevices": [{"name": "users/me/pairedDevices/a"}],
                    "nextPageToken": "page-2",
                },
            )
        return httpx.Response(
            200,
            json={"pairedDevices": [{"name": "users/me/pairedDevices/b"}]},
        )

    client = _make_client(httpx.MockTransport(handler))
    result = client.list_all_paired_devices()

    assert result == {
        "pairedDevices": [
            {"name": "users/me/pairedDevices/a"},
            {"name": "users/me/pairedDevices/b"},
        ],
    }
    assert pages["count"] == 2


def test_paginate_all_rollups_combines_pages() -> None:
    pages = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        pages["count"] += 1
        body = json.loads(request.read())
        if body.get("pageToken") is None:
            return httpx.Response(
                200,
                json={
                    "rollupDataPoints": [{"startTime": "2026-06-01T00:00:00Z"}],
                    "nextPageToken": "page-2",
                },
            )
        return httpx.Response(200, json={"rollupDataPoints": [{"startTime": "2026-06-01T01:00:00Z"}]})

    client = _make_client(httpx.MockTransport(handler))
    result = client.list_all_rollup_data_points(
        "steps",
        start_time="2026-06-01T00:00:00Z",
        end_time="2026-06-02T00:00:00Z",
        window_size="3600s",
    )

    assert result == {
        "rollupDataPoints": [
            {"startTime": "2026-06-01T00:00:00Z"},
            {"startTime": "2026-06-01T01:00:00Z"},
        ],
    }
    assert pages["count"] == 2
