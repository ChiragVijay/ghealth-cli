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


def test_heart_rate_list_shortcut_builds_sample_filter(mock_keyring, monkeypatch) -> None:
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


def test_data_points_create_posts_body_with_yes(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 72}}), encoding="utf-8")
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = request.read()
        return httpx.Response(200, json={"name": "operations/create-1", "done": False})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        ["--format", "json", "data-points", "create", "weight", "--body", str(body_file), "--yes"],
    )

    assert result.exit_code == 0
    assert json.loads(captured_body) == {"weight": {"kg": 72}}
    data = json.loads(result.stdout)
    assert data["name"] == "operations/create-1"


def test_data_points_create_requires_write_scope(tmp_path, mock_keyring) -> None:
    _setup_auth(mock_keyring)
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 72}}), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--format", "json", "data-points", "create", "weight", "--body", str(body_file), "--yes"],
    )

    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "write_scope_required"
    assert "health_metrics_and_measurements.writeonly" in data["error"]["details"]["suggested_scope"]


def test_data_points_create_requires_yes_in_json_mode(tmp_path, mock_keyring) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 72}}), encoding="utf-8")

    result = runner.invoke(
        app, ["--format", "json", "data-points", "create", "weight", "--body", str(body_file)]
    )

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "confirmation_required"


def test_data_points_update_derives_data_type_from_full_name(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 73}}), encoding="utf-8")
    captured = {"path": "", "mask": "", "body": b""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["mask"] = request.url.params.get("updateMask", "")
        captured["body"] = request.read()
        return httpx.Response(200, json={"name": "operations/update-1"})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "update",
            "users/me/dataTypes/weight/dataPoints/point-1",
            "--body",
            str(body_file),
            "--update-mask",
            "weight.kg",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/weight/dataPoints/point-1"
    assert captured["mask"] == "weight.kg"
    assert json.loads(captured["body"]) == {"weight": {"kg": 73}}


def test_data_points_update_short_name_requires_data_type(tmp_path, mock_keyring) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 73}}), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--format", "json", "data-points", "update", "point-1", "--body", str(body_file), "--yes"],
    )

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "data_type_required"


def test_data_points_batch_delete_reads_names_file(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    names_file = tmp_path / "names.txt"
    names_file.write_text("users/me/dataTypes/weight/dataPoints/point-1\n", encoding="utf-8")
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = request.read()
        return httpx.Response(200, json={"name": "operations/delete-1"})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "batch-delete",
            "weight",
            "--names-file",
            str(names_file),
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(captured_body) == {"names": ["users/me/dataTypes/weight/dataPoints/point-1"]}


def test_data_points_export_exercise_tcx_writes_output(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(
        mock_keyring,
        scope=(
            "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly "
            "https://www.googleapis.com/auth/googlehealth.location.readonly"
        ),
    )
    output = tmp_path / "exercise.tcx"
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, text="<TrainingCenterDatabase />")

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "export-exercise-tcx",
            "exercise-1",
            "--partial-data",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert captured_params == {"alt": "media", "partialData": "true"}
    assert output.read_text(encoding="utf-8") == "<TrainingCenterDatabase />"
    data = json.loads(result.stdout)
    assert data["exported"] is True


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


def test_subscribers_delete_requires_yes_in_json_mode(mock_keyring) -> None:
    _setup_auth(mock_keyring, scope="https://www.googleapis.com/auth/cloud-platform")

    result = runner.invoke(
        app,
        ["--format", "json", "subscribers", "delete", "projects/my-project/subscribers/my-sub"],
    )

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "confirmation_required"


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


def test_subscriptions_invalid_resource_name_exits_code_2(mock_keyring) -> None:
    _setup_auth(mock_keyring, scope="https://www.googleapis.com/auth/cloud-platform")

    result = runner.invoke(app, ["--format", "json", "subscriptions", "list", "--subscriber", "bad"])

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "invalid_subscriber_name"


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


def test_invalid_data_type_exits_code_2(mock_keyring) -> None:
    _setup_auth(mock_keyring)
    result = runner.invoke(app, ["--format", "json", "data-points", "list", "invalid-type"])
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "data_type_not_found"


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
