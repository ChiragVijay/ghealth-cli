import json
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


def test_list_subscribers_sends_project_parent_and_pagination() -> None:
    captured_path = ""
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path
        captured_path = request.url.path
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json={"subscribers": []})

    client = _make_client(httpx.MockTransport(handler))
    client.list_subscribers("my-project", page_size=25, page_token="tok")

    assert captured_path == "/v4/projects/my-project/subscribers"
    assert captured_params == {"pageSize": "25", "pageToken": "tok"}


def test_create_subscriber_sends_payload_and_subscriber_id() -> None:
    captured_path = ""
    captured_params: dict[str, str] = {}
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path, captured_body
        captured_path = request.url.path
        captured_params.update(dict(request.url.params))
        captured_body = request.read()
        return httpx.Response(200, json={"name": "operations/subscriber-create"})

    client = _make_client(httpx.MockTransport(handler))
    payload = {
        "endpointUri": "https://example.com/webhooks/google-health",
        "subscriberConfigs": [{"dataTypes": ["steps"], "subscriptionCreatePolicy": "MANUAL"}],
        "endpointAuthorization": {"secret": "Bearer secret"},
    }
    client.create_subscriber("projects/my-project", payload, subscriber_id="my-sub")

    assert captured_path == "/v4/projects/my-project/subscribers"
    assert captured_params == {"subscriberId": "my-sub"}
    assert json.loads(captured_body) == payload


def test_update_and_delete_subscriber_paths() -> None:
    requests: list[tuple[str, str, dict[str, str], dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read()) if request.content else None
        requests.append((request.method, request.url.path, dict(request.url.params), body))
        return httpx.Response(200, json={"name": "operations/subscriber-op"})

    client = _make_client(httpx.MockTransport(handler))
    client.update_subscriber(
        "projects/my-project/subscribers/my-sub",
        {"endpointUri": "https://example.com/new"},
        update_mask="endpointUri",
    )
    client.delete_subscriber("projects/my-project/subscribers/my-sub", force=True)

    assert requests == [
        (
            "PATCH",
            "/v4/projects/my-project/subscribers/my-sub",
            {"updateMask": "endpointUri"},
            {"endpointUri": "https://example.com/new"},
        ),
        ("DELETE", "/v4/projects/my-project/subscribers/my-sub", {"force": "true"}, None),
    ]


def test_list_subscriptions_sends_filter_and_pagination() -> None:
    captured_path = ""
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path
        captured_path = request.url.path
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json={"subscriptions": []})

    client = _make_client(httpx.MockTransport(handler))
    client.list_subscriptions(
        "projects/my-project/subscribers/my-sub",
        filter='user = "users/123"',
        page_size=10,
        page_token="tok",
    )

    assert captured_path == "/v4/projects/my-project/subscribers/my-sub/subscriptions"
    assert captured_params == {"filter": 'user = "users/123"', "pageSize": "10", "pageToken": "tok"}


def test_create_update_delete_subscription_paths() -> None:
    requests: list[tuple[str, str, dict[str, str], dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read()) if request.content else None
        requests.append((request.method, request.url.path, dict(request.url.params), body))
        return httpx.Response(
            200, json={"name": "projects/my-project/subscribers/my-sub/subscriptions/sub-1"}
        )

    client = _make_client(httpx.MockTransport(handler))
    client.create_subscription(
        "projects/my-project/subscribers/my-sub",
        {"user": "users/123", "dataTypes": ["steps"]},
        subscription_id="sub-1",
    )
    client.update_subscription(
        "projects/my-project/subscribers/my-sub/subscriptions/sub-1",
        {"dataTypes": ["sleep"]},
        update_mask="dataTypes",
    )
    client.delete_subscription("projects/my-project/subscribers/my-sub/subscriptions/sub-1")

    assert requests == [
        (
            "POST",
            "/v4/projects/my-project/subscribers/my-sub/subscriptions",
            {"subscriptionId": "sub-1"},
            {"user": "users/123", "dataTypes": ["steps"]},
        ),
        (
            "PATCH",
            "/v4/projects/my-project/subscribers/my-sub/subscriptions/sub-1",
            {"updateMask": "dataTypes"},
            {"dataTypes": ["sleep"]},
        ),
        ("DELETE", "/v4/projects/my-project/subscribers/my-sub/subscriptions/sub-1", {}, None),
    ]
