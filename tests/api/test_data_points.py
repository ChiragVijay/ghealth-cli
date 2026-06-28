import json
import time

import httpx
import pytest

from ghealth.api import (
    GHealthApiClient,
    build_civil_datetime,
    build_data_point_time_filter,
)
from ghealth.config import Config
from ghealth.data_types import DataTypeRegistry


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


def test_list_data_points_sends_filter_and_pagination() -> None:
    captured_path = ""
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path
        captured_path = request.url.path
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json={"dataPoints": []})

    client = _make_client(httpx.MockTransport(handler))
    client.list_data_points(
        "steps",
        page_size=25,
        page_token="tok",
        filter='steps.interval.start_time >= "2026-06-01T00:00:00Z"',
    )

    assert captured_path == "/v4/users/me/dataTypes/steps/dataPoints"
    assert captured_params["pageSize"] == "25"
    assert captured_params["pageToken"] == "tok"
    assert captured_params["filter"] == 'steps.interval.start_time >= "2026-06-01T00:00:00Z"'


def test_reconcile_data_points_sends_query_params() -> None:
    captured_path = ""
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path
        captured_path = request.url.path
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json={"dataPoints": []})

    client = _make_client(httpx.MockTransport(handler))
    client.reconcile_data_points(
        "steps",
        page_size=25,
        page_token="tok",
        filter='steps.interval.start_time >= "2026-06-01T00:00:00Z"',
        data_source_family="google-wearables",
    )

    assert captured_path == "/v4/users/me/dataTypes/steps/dataPoints:reconcile"
    assert captured_params["pageSize"] == "25"
    assert captured_params["pageToken"] == "tok"
    assert captured_params["filter"] == 'steps.interval.start_time >= "2026-06-01T00:00:00Z"'
    assert captured_params["dataSourceFamily"] == "users/me/dataSourceFamilies/google-wearables"


def test_rollup_data_points_sends_json_body() -> None:
    captured_path = ""
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path, captured_body
        captured_path = request.url.path
        captured_body = request.read()
        return httpx.Response(200, json={"rollupDataPoints": []})

    client = _make_client(httpx.MockTransport(handler))
    client.rollup_data_points(
        "steps",
        start_time="2026-06-01T00:00:00Z",
        end_time="2026-06-02T00:00:00Z",
        window_size="3600s",
        page_size=10,
        page_token="tok",
        data_source_family="users/me/dataSourceFamilies/google-sources",
    )

    body = json.loads(captured_body)
    assert captured_path == "/v4/users/me/dataTypes/steps/dataPoints:rollUp"
    assert body == {
        "range": {
            "startTime": "2026-06-01T00:00:00Z",
            "endTime": "2026-06-02T00:00:00Z",
        },
        "windowSize": "3600s",
        "pageSize": 10,
        "pageToken": "tok",
        "dataSourceFamily": "users/me/dataSourceFamilies/google-sources",
    }


def test_daily_rollup_data_points_sends_civil_range_body() -> None:
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = request.read()
        return httpx.Response(200, json={"rollupDataPoints": []})

    client = _make_client(httpx.MockTransport(handler))
    client.daily_rollup_data_points(
        "steps",
        start_date="2026-06-01",
        end_date="2026-06-03",
        window_size_days=1,
    )

    body = json.loads(captured_body)
    assert body == {
        "range": {
            "start": {"date": {"year": 2026, "month": 6, "day": 1}},
            "end": {"date": {"year": 2026, "month": 6, "day": 3}},
        },
        "windowSizeDays": 1,
    }


def test_create_data_point_sends_documented_path_and_body() -> None:
    captured_path = ""
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path, captured_body
        captured_path = request.url.path
        captured_body = request.read()
        return httpx.Response(200, json={"name": "operations/create-1"})

    client = _make_client(httpx.MockTransport(handler))
    body = {"name": "users/me/dataTypes/weight/dataPoints/point-1", "weight": {"kg": 72}}
    result = client.create_data_point("weight", body)

    assert captured_path == "/v4/users/me/dataTypes/weight/dataPoints"
    assert json.loads(captured_body) == body
    assert result["name"] == "operations/create-1"


def test_update_data_point_sends_patch_body_and_update_mask() -> None:
    captured_path = ""
    captured_params: dict[str, str] = {}
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path, captured_body
        captured_path = request.url.path
        captured_params.update(dict(request.url.params))
        captured_body = request.read()
        return httpx.Response(200, json={"name": "operations/update-1"})

    client = _make_client(httpx.MockTransport(handler))
    body = {"weight": {"kg": 73}}
    client.update_data_point("weight", "point-1", body, update_mask="weight.kg")

    assert captured_path == "/v4/users/me/dataTypes/weight/dataPoints/point-1"
    assert captured_params["updateMask"] == "weight.kg"
    assert json.loads(captured_body) == body


def test_batch_delete_data_points_sends_names_body() -> None:
    captured_path = ""
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path, captured_body
        captured_path = request.url.path
        captured_body = request.read()
        return httpx.Response(200, json={"name": "operations/delete-1"})

    client = _make_client(httpx.MockTransport(handler))
    names = ["users/me/dataTypes/weight/dataPoints/point-1"]
    client.batch_delete_data_points("weight", names)

    assert captured_path == "/v4/users/me/dataTypes/weight/dataPoints:batchDelete"
    assert json.loads(captured_body) == {"names": names}


def test_export_exercise_tcx_uses_alt_media_and_returns_text() -> None:
    captured_path = ""
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path
        captured_path = request.url.path
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, text="<TrainingCenterDatabase />")

    client = _make_client(httpx.MockTransport(handler))
    result = client.export_exercise_tcx("exercise-1", partial_data=True)

    assert captured_path == "/v4/users/me/dataTypes/exercise/dataPoints/exercise-1:exportExerciseTcx"
    assert captured_params == {"alt": "media", "partialData": "true"}
    assert result == "<TrainingCenterDatabase />"


def test_build_data_point_time_filter_for_interval() -> None:
    registry = DataTypeRegistry()
    info = registry.get("steps")
    assert info is not None
    result = build_data_point_time_filter(
        info,
        start="2026-06-01T00:00:00Z",
        end="2026-06-02T00:00:00Z",
    )
    assert result == (
        'steps.interval.start_time >= "2026-06-01T00:00:00Z" AND '
        'steps.interval.start_time < "2026-06-02T00:00:00Z"'
    )


def test_build_data_point_time_filter_for_interval_civil_dates() -> None:
    registry = DataTypeRegistry()
    info = registry.get("steps")
    assert info is not None
    result = build_data_point_time_filter(info, start="2026-06-01", end="2026-06-02")

    assert result == (
        'steps.interval.civil_start_time >= "2026-06-01" AND steps.interval.civil_start_time < "2026-06-02"'
    )


def test_build_data_point_time_filter_for_sleep_uses_session_end_time() -> None:
    registry = DataTypeRegistry()
    info = registry.get("sleep")
    assert info is not None
    result = build_data_point_time_filter(info, start="2026-06-01", end="2026-06-10")

    assert result == (
        'sleep.interval.civil_end_time >= "2026-06-01" AND sleep.interval.civil_end_time < "2026-06-10"'
    )


def test_build_data_point_time_filter_for_sleep_physical_timestamps() -> None:
    registry = DataTypeRegistry()
    info = registry.get("sleep")
    assert info is not None
    result = build_data_point_time_filter(
        info,
        start="2026-06-01T00:00:00Z",
        end="2026-06-10T00:00:00Z",
    )

    assert result == (
        'sleep.interval.end_time >= "2026-06-01T00:00:00Z" AND '
        'sleep.interval.end_time < "2026-06-10T00:00:00Z"'
    )


def test_build_data_point_time_filter_for_exercise_uses_civil_start_time() -> None:
    registry = DataTypeRegistry()
    info = registry.get("exercise")
    assert info is not None
    result = build_data_point_time_filter(info, start="2026-06-01", end="2026-06-10")

    assert result == (
        'exercise.interval.civil_start_time >= "2026-06-01" AND '
        'exercise.interval.civil_start_time < "2026-06-10"'
    )


def test_build_data_point_time_filter_for_exercise_rejects_physical_time() -> None:
    registry = DataTypeRegistry()
    info = registry.get("exercise")
    assert info is not None

    with pytest.raises(ValueError, match="date-only civil ranges"):
        build_data_point_time_filter(info, start="2026-06-01T00:00:00Z")


def test_build_data_point_time_filter_for_heart_rate_uses_sample_time() -> None:
    registry = DataTypeRegistry()
    info = registry.get("heart-rate")
    assert info is not None
    result = build_data_point_time_filter(
        info,
        start="2026-06-01T00:00:00Z",
        end="2026-06-02T00:00:00Z",
    )

    assert result == (
        'heart_rate.sample_time.physical_time >= "2026-06-01T00:00:00Z" AND '
        'heart_rate.sample_time.physical_time < "2026-06-02T00:00:00Z"'
    )


def test_build_data_point_time_filter_for_hydration_uses_interval_civil_start_time() -> None:
    registry = DataTypeRegistry()
    info = registry.get("hydration-log")
    assert info is not None
    result = build_data_point_time_filter(info, start="2026-06-01", end="2026-06-10")

    assert result == (
        'hydration_log.interval.civil_start_time >= "2026-06-01" AND '
        'hydration_log.interval.civil_start_time < "2026-06-10"'
    )


def test_build_data_point_time_filter_for_nutrition_uses_interval_civil_start_time() -> None:
    registry = DataTypeRegistry()
    info = registry.get("nutrition-log")
    assert info is not None
    result = build_data_point_time_filter(info, start="2026-06-01", end="2026-06-10")

    assert result == (
        'nutrition_log.interval.civil_start_time >= "2026-06-01" AND '
        'nutrition_log.interval.civil_start_time < "2026-06-10"'
    )


def test_build_data_point_time_filter_for_sample_civil_dates() -> None:
    registry = DataTypeRegistry()
    info = registry.get("weight")
    assert info is not None
    result = build_data_point_time_filter(info, start="2026-06-01", end="2026-06-10")

    assert result == (
        'weight.sample_time.civil_time >= "2026-06-01" AND weight.sample_time.civil_time < "2026-06-10"'
    )


def test_build_civil_datetime_validates_date_only() -> None:
    assert build_civil_datetime("2026-06-01") == {"date": {"year": 2026, "month": 6, "day": 1}}
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_civil_datetime("2026-06-01T00:00:00")
