from typing import Any

import httpx

API_ERROR_EXIT_CODES: dict[str, int] = {
    "api_bad_request": 2,
    "not_configured": 3,
    "not_authenticated": 3,
    "refresh_failed": 3,
    "api_unauthorized": 3,
    "missing_scope_or_forbidden": 3,
    "api_not_found": 4,
    "rate_limited": 4,
    "api_server_error": 4,
    "api_error": 4,
    "api_invalid_response": 4,
    "api_request_failed": 4,
    "pagination_limit_exceeded": 4,
}


class GHealthApiError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def parse_api_error(response: httpx.Response, path: str) -> GHealthApiError:
    status_code = response.status_code
    details: dict[str, Any] = {"status_code": status_code, "path": path}
    message = response.text or f"HTTP {status_code}"
    google_status: str | None = None
    google_reason: str | None = None

    try:
        body = response.json()
        if isinstance(body, dict):
            error_body = body.get("error")
            if isinstance(error_body, dict):
                message = error_body.get("message", message)
                google_status = error_body.get("status")
                error_details = error_body.get("details")
                if isinstance(error_details, list) and error_details:
                    first_detail = error_details[0]
                    if isinstance(first_detail, dict):
                        google_reason = first_detail.get("reason")
    except ValueError:
        pass

    if google_status:
        details["status"] = google_status
    if google_reason:
        details["reason"] = google_reason

    if status_code == 429:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            details["retry_after"] = retry_after

    if status_code == 400:
        code = "api_bad_request"
    elif status_code == 401:
        code = "api_unauthorized"
    elif status_code == 403:
        code = "missing_scope_or_forbidden"
    elif status_code == 404:
        code = "api_not_found"
    elif status_code == 429:
        code = "rate_limited"
    elif 500 <= status_code <= 599:
        code = "api_server_error"
    else:
        code = "api_error"

    return GHealthApiError(code, message, status_code=status_code, details=details)
