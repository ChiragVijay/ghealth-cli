from typing import Any

from ghealth.api.dates import build_civil_datetime
from ghealth.api.names import (
    add_optional_rollup_fields,
    data_point_name,
    data_source_family_name,
    pagination_params,
)


def list_path(data_type: str) -> str:
    return f"/v4/users/me/dataTypes/{data_type}/dataPoints"


def list_params(
    *,
    page_size: int | None = None,
    page_token: str | None = None,
    filter: str | None = None,
) -> dict:
    params = pagination_params(page_size=page_size, page_token=page_token)
    if filter is not None:
        params["filter"] = filter
    return params


def get_path(data_type: str, data_point: str) -> str:
    return f"/v4/{data_point_name(data_type, data_point)}"


def create_path(data_type: str) -> str:
    return f"/v4/users/me/dataTypes/{data_type}/dataPoints"


def update_path(data_type: str, data_point: str) -> str:
    return f"/v4/{data_point_name(data_type, data_point)}"


def update_params(*, update_mask: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if update_mask is not None:
        params["updateMask"] = update_mask
    return params


def batch_delete_path(data_type: str) -> str:
    return f"/v4/users/me/dataTypes/{data_type}/dataPoints:batchDelete"


def batch_delete_body(names: list[str]) -> dict[str, list[str]]:
    return {"names": names}


def export_exercise_tcx_path(data_point: str) -> str:
    return f"/v4/{data_point_name('exercise', data_point)}:exportExerciseTcx"


def export_exercise_tcx_params(*, partial_data: bool | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"alt": "media"}
    if partial_data is not None:
        params["partialData"] = partial_data
    return params


def reconcile_path(data_type: str) -> str:
    return f"/v4/users/me/dataTypes/{data_type}/dataPoints:reconcile"


def reconcile_params(
    *,
    page_size: int | None = None,
    page_token: str | None = None,
    filter: str | None = None,
    data_source_family: str | None = None,
) -> dict:
    params = pagination_params(page_size=page_size, page_token=page_token)
    if filter is not None:
        params["filter"] = filter
    if data_source_family is not None:
        params["dataSourceFamily"] = data_source_family_name(data_source_family)
    return params


def rollup_path(data_type: str) -> str:
    return f"/v4/users/me/dataTypes/{data_type}/dataPoints:rollUp"


def rollup_body(
    *,
    start_time: str,
    end_time: str,
    window_size: str,
    page_size: int | None = None,
    page_token: str | None = None,
    data_source_family: str | None = None,
) -> dict:
    body: dict[str, Any] = {
        "range": {"startTime": start_time, "endTime": end_time},
        "windowSize": window_size,
    }
    add_optional_rollup_fields(
        body,
        page_size=page_size,
        page_token=page_token,
        data_source_family=data_source_family,
    )
    return body


def daily_rollup_path(data_type: str) -> str:
    return f"/v4/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp"


def daily_rollup_body(
    *,
    start_date: str,
    end_date: str,
    window_size_days: int | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
    data_source_family: str | None = None,
) -> dict:
    body: dict[str, Any] = {
        "range": {
            "start": build_civil_datetime(start_date),
            "end": build_civil_datetime(end_date),
        },
    }
    if window_size_days is not None:
        body["windowSizeDays"] = window_size_days
    add_optional_rollup_fields(
        body,
        page_size=page_size,
        page_token=page_token,
        data_source_family=data_source_family,
    )
    return body
