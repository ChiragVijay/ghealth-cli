from typing import Any

from ghealth.api.names import pagination_params, project_subscribers_parent


def list_path(project: str) -> str:
    return f"/v4/{project_subscribers_parent(project)}"


def list_params(
    *,
    page_size: int | None = None,
    page_token: str | None = None,
) -> dict:
    return pagination_params(page_size=page_size, page_token=page_token)


def create_path(project: str) -> str:
    return f"/v4/{project_subscribers_parent(project)}"


def create_params(*, subscriber_id: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if subscriber_id is not None:
        params["subscriberId"] = subscriber_id
    return params


def resource_path(resource_name: str) -> str:
    return f"/v4/{resource_name}"


def update_params(*, update_mask: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if update_mask is not None:
        params["updateMask"] = update_mask
    return params


def delete_params(*, force: bool = False) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if force:
        params["force"] = force
    return params
