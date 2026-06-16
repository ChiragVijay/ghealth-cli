from typing import Any

from ghealth.api.names import pagination_params


def list_path(subscriber_name: str) -> str:
    return f"/v4/{subscriber_name}/subscriptions"


def list_params(
    *,
    filter: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
) -> dict:
    params = pagination_params(page_size=page_size, page_token=page_token)
    if filter is not None:
        params["filter"] = filter
    return params


def create_path(subscriber_name: str) -> str:
    return f"/v4/{subscriber_name}/subscriptions"


def create_params(*, subscription_id: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if subscription_id is not None:
        params["subscriptionId"] = subscription_id
    return params


def resource_path(resource_name: str) -> str:
    return f"/v4/{resource_name}"


def update_params(*, update_mask: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if update_mask is not None:
        params["updateMask"] = update_mask
    return params
