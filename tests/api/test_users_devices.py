import time

import httpx

from ghealth.api import (
    GHealthApiClient,
)
from ghealth.config import Config


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


def test_client_calls_expected_user_paths() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json={"name": request.url.path})

    transport = httpx.MockTransport(handler)
    client = _make_client(transport)

    client.get_identity()
    client.get_profile()
    client.get_settings()

    assert paths == [
        "/v4/users/me/identity",
        "/v4/users/me/profile",
        "/v4/users/me/settings",
    ]


def test_list_paired_devices_sends_pagination_params() -> None:
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json={"pairedDevices": []})

    client = _make_client(httpx.MockTransport(handler))
    client.list_paired_devices(page_size=10, page_token="abc")

    assert captured_params["pageSize"] == "10"
    assert captured_params["pageToken"] == "abc"


def test_get_calls_expand_short_ids() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json={"name": request.url.path})

    client = _make_client(httpx.MockTransport(handler))
    client.get_paired_device("device-1")
    client.get_data_point("steps", "point-1")

    assert paths == [
        "/v4/users/me/pairedDevices/device-1",
        "/v4/users/me/dataTypes/steps/dataPoints/point-1",
    ]


def test_get_accepts_full_resource_names() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json={"name": request.url.path})

    client = _make_client(httpx.MockTransport(handler))
    client.get_paired_device("users/me/pairedDevices/device-1")
    client.get_data_point("steps", "users/me/dataTypes/steps/dataPoints/point-1")

    assert paths == [
        "/v4/users/me/pairedDevices/device-1",
        "/v4/users/me/dataTypes/steps/dataPoints/point-1",
    ]
