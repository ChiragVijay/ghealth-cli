from typing import Any


def paired_device_name(device: str) -> str:
    if device.startswith("users/"):
        return device
    return f"users/me/pairedDevices/{device}"


def data_point_name(data_type: str, data_point: str) -> str:
    if data_point.startswith("users/"):
        return data_point
    return f"users/me/dataTypes/{data_type}/dataPoints/{data_point}"


def data_source_family_name(data_source_family: str) -> str:
    if data_source_family.startswith("users/"):
        return data_source_family
    return f"users/me/dataSourceFamilies/{data_source_family}"


def project_subscribers_parent(project: str) -> str:
    if project.startswith("projects/"):
        return f"{project.rstrip('/')}/subscribers"
    return f"projects/{project}/subscribers"


def pagination_params(
    *,
    page_size: int | None = None,
    page_token: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if page_size is not None:
        params["pageSize"] = page_size
    if page_token is not None:
        params["pageToken"] = page_token
    return params


def add_optional_rollup_fields(
    body: dict[str, Any],
    *,
    page_size: int | None,
    page_token: str | None,
    data_source_family: str | None,
) -> None:
    if page_size is not None:
        body["pageSize"] = page_size
    if page_token is not None:
        body["pageToken"] = page_token
    if data_source_family is not None:
        body["dataSourceFamily"] = data_source_family_name(data_source_family)
