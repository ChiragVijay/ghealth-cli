from ghealth.api.names import pagination_params, paired_device_name


def list_path() -> str:
    return "/v4/users/me/pairedDevices"


def list_params(
    *,
    page_size: int | None = None,
    page_token: str | None = None,
) -> dict:
    return pagination_params(page_size=page_size, page_token=page_token)


def get_path(device: str) -> str:
    return f"/v4/{paired_device_name(device)}"
