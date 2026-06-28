import json
import time
from datetime import date

import httpx
import pytest
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


def test_data_points_list_builds_time_filter(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured_filter = {"value": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_filter["value"] = request.url.params.get("filter", "")
        return httpx.Response(200, json={"dataPoints": [{"name": "users/me/dataTypes/steps/dataPoints/1"}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "list",
            "steps",
            "--start",
            "2026-06-01T00:00:00Z",
            "--end",
            "2026-06-02T00:00:00Z",
        ],
    )
    assert result.exit_code == 0
    assert (
        captured_filter["value"] == 'steps.interval.start_time >= "2026-06-01T00:00:00Z" AND '
        'steps.interval.start_time < "2026-06-02T00:00:00Z"'
    )


def test_data_points_filter_with_start_exits_code_2(mock_keyring) -> None:
    _setup_auth(mock_keyring)
    result = runner.invoke(
        app,
        [
            "data-points",
            "list",
            "steps",
            "--filter",
            'steps.interval.start_time >= "2026-06-01T00:00:00Z"',
            "--start",
            "2026-06-01T00:00:00Z",
        ],
    )
    assert result.exit_code == 2


def test_data_points_list_limit_truncates_json_output(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "dataPoints": [
                    {"name": "users/me/dataTypes/steps/dataPoints/1"},
                    {"name": "users/me/dataTypes/steps/dataPoints/2"},
                    {"name": "users/me/dataTypes/steps/dataPoints/3"},
                ],
                "nextPageToken": "next",
            },
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", "data-points", "list", "steps", "--limit", "2"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert [item["name"] for item in data["dataPoints"]] == [
        "users/me/dataTypes/steps/dataPoints/1",
        "users/me/dataTypes/steps/dataPoints/2",
    ]
    assert data["nextPageToken"] == "next"
    assert data["limited"] is True
    assert data["limit"] == 2


def test_data_points_list_all_limit_stops_pagination_early(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        token = request.url.params.get("pageToken")
        if token is None:
            return httpx.Response(
                200,
                json={
                    "dataPoints": [{"name": "users/me/dataTypes/steps/dataPoints/1"}],
                    "nextPageToken": "page-2",
                },
            )
        return httpx.Response(
            200,
            json={
                "dataPoints": [{"name": "users/me/dataTypes/steps/dataPoints/2"}],
                "nextPageToken": "page-3",
            },
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        ["--format", "json", "data-points", "list", "steps", "--all", "--limit", "1"],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dataPoints"] == [{"name": "users/me/dataTypes/steps/dataPoints/1"}]
    assert calls["count"] == 1


def test_data_points_list_rejects_invalid_limit(mock_keyring) -> None:
    _setup_auth(mock_keyring)
    result = runner.invoke(app, ["--format", "json", "data-points", "list", "steps", "--limit", "0"])

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "invalid_limit"


def test_data_points_reconcile_sends_filter_and_source_family(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured = {"path": "", "source": "", "filter": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["source"] = request.url.params.get("dataSourceFamily", "")
        captured["filter"] = request.url.params.get("filter", "")
        return httpx.Response(
            200, json={"dataPoints": [{"dataPointName": "users/me/dataTypes/steps/dataPoints/1"}]}
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "reconcile",
            "steps",
            "--start",
            "2026-06-01T00:00:00Z",
            "--data-source-family",
            "google-wearables",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/steps/dataPoints:reconcile"
    assert captured["source"] == "users/me/dataSourceFamilies/google-wearables"
    assert captured["filter"] == 'steps.interval.start_time >= "2026-06-01T00:00:00Z"'


def test_data_points_rollup_sends_json_body(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = request.read()
        return httpx.Response(200, json={"rollupDataPoints": [{"startTime": "2026-06-01T00:00:00Z"}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "rollup",
            "steps",
            "--start",
            "2026-06-01T00:00:00Z",
            "--end",
            "2026-06-02T00:00:00Z",
            "--window-size",
            "3600s",
            "--page-size",
            "10",
        ],
    )

    assert result.exit_code == 0
    body = json.loads(captured_body)
    assert body["range"] == {
        "startTime": "2026-06-01T00:00:00Z",
        "endTime": "2026-06-02T00:00:00Z",
    }
    assert body["windowSize"] == "3600s"
    assert body["pageSize"] == 10


def test_data_points_daily_rollup_sends_civil_date_body(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = request.read()
        return httpx.Response(200, json={"rollupDataPoints": [{"civilStartTime": {"date": {"year": 2026}}}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "daily-rollup",
            "steps",
            "--start-date",
            "2026-06-01",
            "--end-date",
            "2026-06-03",
            "--window-size-days",
            "1",
        ],
    )

    assert result.exit_code == 0
    body = json.loads(captured_body)
    assert body["range"]["start"] == {"date": {"year": 2026, "month": 6, "day": 1}}
    assert body["range"]["end"] == {"date": {"year": 2026, "month": 6, "day": 3}}
    assert body["windowSizeDays"] == 1


def test_data_points_daily_rollup_invalid_date_exits_code_2(mock_keyring) -> None:
    _setup_auth(mock_keyring)
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "daily-rollup",
            "steps",
            "--start-date",
            "2026-06-01T00:00:00",
            "--end-date",
            "2026-06-03",
        ],
    )

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "invalid_date"


def test_data_points_unsupported_operation_exits_code_2(mock_keyring) -> None:
    _setup_auth(mock_keyring)
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "rollup",
            "active-minutes",
            "--start",
            "2026-06-01T00:00:00Z",
            "--end",
            "2026-06-02T00:00:00Z",
            "--window-size",
            "3600s",
        ],
    )

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "unsupported_operation"


def test_steps_daily_shortcut_calls_daily_rollup(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured = {"path": "", "body": b""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.read()
        return httpx.Response(200, json={"rollupDataPoints": [{"civilStartTime": {"date": {"year": 2026}}}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "steps",
            "daily",
            "--start-date",
            "2026-06-01",
            "--end-date",
            "2026-06-10",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp"
    body = json.loads(captured["body"])
    assert body["range"]["start"] == {"date": {"year": 2026, "month": 6, "day": 1}}
    assert body["range"]["end"] == {"date": {"year": 2026, "month": 6, "day": 10}}


def test_calories_daily_shortcut_calls_total_calories_daily_rollup(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured = {"path": "", "body": b""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.read()
        return httpx.Response(200, json={"rollupDataPoints": [{"civilStartTime": {"date": {"year": 2026}}}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "calories",
            "daily",
            "--start-date",
            "2026-06-01",
            "--end-date",
            "2026-06-10",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/total-calories/dataPoints:dailyRollUp"
    body = json.loads(captured["body"])
    assert body["range"]["start"] == {"date": {"year": 2026, "month": 6, "day": 1}}
    assert body["range"]["end"] == {"date": {"year": 2026, "month": 6, "day": 10}}


def test_calories_daily_shortcut_accepts_last_days(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    monkeypatch.setattr("ghealth.commands.shared.current_civil_date", lambda: date(2026, 6, 12))
    captured = {"path": "", "body": b""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.read()
        return httpx.Response(200, json={"rollupDataPoints": [{"civilStartTime": {"date": {"year": 2026}}}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", "calories", "daily", "--last-days", "5"])

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/total-calories/dataPoints:dailyRollUp"
    body = json.loads(captured["body"])
    assert body["range"]["start"] == {"date": {"year": 2026, "month": 6, "day": 7}}
    assert body["range"]["end"] == {"date": {"year": 2026, "month": 6, "day": 12}}


def test_daily_rollup_rejects_combined_last_days_and_date_range(mock_keyring) -> None:
    _setup_auth(mock_keyring)
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "calories",
            "daily",
            "--last-days",
            "5",
            "--start-date",
            "2026-06-01",
            "--end-date",
            "2026-06-10",
        ],
    )

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "invalid_date_range"


def test_data_points_daily_rollup_accepts_last_days(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    monkeypatch.setattr("ghealth.commands.shared.current_civil_date", lambda: date(2026, 6, 12))
    captured = {"path": "", "body": b""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.read()
        return httpx.Response(200, json={"rollupDataPoints": [{"civilStartTime": {"date": {"year": 2026}}}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        ["--format", "json", "data-points", "daily-rollup", "total-calories", "--last-days", "5"],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/total-calories/dataPoints:dailyRollUp"
    body = json.loads(captured["body"])
    assert body["range"]["start"] == {"date": {"year": 2026, "month": 6, "day": 7}}
    assert body["range"]["end"] == {"date": {"year": 2026, "month": 6, "day": 12}}


@pytest.mark.parametrize(
    ("command", "data_type"),
    [
        ("active-energy", "active-energy-burned"),
        ("active-minutes", "active-minutes"),
        ("active-zone-minutes", "active-zone-minutes"),
        ("distance", "distance"),
        ("floors", "floors"),
    ],
)
def test_daily_activity_shortcuts_call_daily_rollup(command, data_type, mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    monkeypatch.setattr("ghealth.commands.shared.current_civil_date", lambda: date(2026, 6, 12))
    captured = {"path": "", "body": b""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.read()
        return httpx.Response(200, json={"rollupDataPoints": [{"civilStartTime": {"date": {"year": 2026}}}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", command, "daily", "--last-days", "5"])

    assert result.exit_code == 0
    assert captured["path"] == f"/v4/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp"
    body = json.loads(captured["body"])
    assert body["range"]["start"] == {"date": {"year": 2026, "month": 6, "day": 7}}
    assert body["range"]["end"] == {"date": {"year": 2026, "month": 6, "day": 12}}


def test_sleep_list_shortcut_builds_session_filter(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured = {"path": "", "filter": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["filter"] = request.url.params.get("filter", "")
        return httpx.Response(200, json={"dataPoints": [{"name": "users/me/dataTypes/sleep/dataPoints/1"}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "sleep",
            "list",
            "--start",
            "2026-06-01",
            "--end",
            "2026-06-10",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/sleep/dataPoints"
    assert (
        captured["filter"] == 'sleep.interval.civil_end_time >= "2026-06-01" AND '
        'sleep.interval.civil_end_time < "2026-06-10"'
    )


def test_sleep_list_shortcut_limit_truncates_json_output(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "dataPoints": [
                    {"name": "users/me/dataTypes/sleep/dataPoints/1"},
                    {"name": "users/me/dataTypes/sleep/dataPoints/2"},
                ],
            },
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", "sleep", "list", "--limit", "1"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dataPoints"] == [{"name": "users/me/dataTypes/sleep/dataPoints/1"}]
    assert data["limited"] is True


@pytest.mark.parametrize(
    ("command", "data_type"),
    [
        ("height", "height"),
        ("body-fat", "body-fat"),
    ],
)
def test_common_list_shortcuts_call_data_type_list(command, data_type, mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured = {"path": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(
            200,
            json={"dataPoints": [{"name": f"users/me/dataTypes/{data_type}/dataPoints/1"}]},
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", command, "list", "--limit", "1"])

    assert result.exit_code == 0
    assert captured["path"] == f"/v4/users/me/dataTypes/{data_type}/dataPoints"


@pytest.mark.parametrize(
    ("command", "data_type", "expected_filter"),
    [
        (
            "exercise",
            "exercise",
            'exercise.interval.civil_start_time >= "2026-06-01" AND '
            'exercise.interval.civil_start_time < "2026-06-10"',
        ),
        (
            "hydration",
            "hydration-log",
            'hydration_log.interval.civil_start_time >= "2026-06-01" AND '
            'hydration_log.interval.civil_start_time < "2026-06-10"',
        ),
        (
            "nutrition",
            "nutrition-log",
            'nutrition_log.interval.civil_start_time >= "2026-06-01" AND '
            'nutrition_log.interval.civil_start_time < "2026-06-10"',
        ),
    ],
)
def test_interval_list_shortcuts_build_civil_start_filter(
    command,
    data_type,
    expected_filter,
    mock_keyring,
    monkeypatch,
) -> None:
    _setup_auth(mock_keyring)
    captured = {"path": "", "filter": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["filter"] = request.url.params.get("filter", "")
        return httpx.Response(
            200,
            json={"dataPoints": [{"name": f"users/me/dataTypes/{data_type}/dataPoints/1"}]},
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        ["--format", "json", command, "list", "--start", "2026-06-01", "--end", "2026-06-10"],
    )

    assert result.exit_code == 0
    assert captured["path"] == f"/v4/users/me/dataTypes/{data_type}/dataPoints"
    assert captured["filter"] == expected_filter


def test_food_list_shortcut_without_filter_calls_food_list(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured = {"path": "", "filter": None}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["filter"] = request.url.params.get("filter")
        return httpx.Response(200, json={"dataPoints": [{"name": "users/me/dataTypes/food/dataPoints/1"}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(app, ["--format", "json", "food", "list", "--limit", "1"])

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/food/dataPoints"
    assert captured["filter"] is None


def test_food_list_shortcut_with_time_filter_returns_structured_error(mock_keyring) -> None:
    _setup_auth(mock_keyring)
    result = runner.invoke(
        app,
        ["--format", "json", "food", "list", "--start", "2026-06-01", "--end", "2026-06-10"],
    )

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "unsupported_time_filter"
    assert data["error"]["details"]["data_type"] == "food"


def test_heart_rate_list_shortcut_builds_interval_filter(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured = {"path": "", "filter": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["filter"] = request.url.params.get("filter", "")
        return httpx.Response(
            200, json={"dataPoints": [{"name": "users/me/dataTypes/heart-rate/dataPoints/1"}]}
        )

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "heart-rate",
            "list",
            "--start",
            "2026-06-01T00:00:00Z",
            "--end",
            "2026-06-02T00:00:00Z",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/heart-rate/dataPoints"
    assert (
        captured["filter"] == 'heart_rate.sample_time.physical_time >= "2026-06-01T00:00:00Z" AND '
        'heart_rate.sample_time.physical_time < "2026-06-02T00:00:00Z"'
    )


def test_weight_list_shortcut_builds_sample_filter(mock_keyring, monkeypatch) -> None:
    _setup_auth(mock_keyring)
    captured = {"path": "", "filter": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["filter"] = request.url.params.get("filter", "")
        return httpx.Response(200, json={"dataPoints": [{"name": "users/me/dataTypes/weight/dataPoints/1"}]})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "weight",
            "list",
            "--start",
            "2026-01-01",
            "--end",
            "2026-06-10",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/weight/dataPoints"
    assert (
        captured["filter"] == 'weight.sample_time.civil_time >= "2026-01-01" AND '
        'weight.sample_time.civil_time < "2026-06-10"'
    )
