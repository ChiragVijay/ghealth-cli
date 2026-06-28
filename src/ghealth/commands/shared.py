import datetime as dt
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

import typer

from ghealth.api import (
    GHealthApiClient,
    GHealthApiError,
    build_civil_datetime,
    build_data_point_time_filter,
)
from ghealth.auth.scopes import SCOPE_ALIASES, SCOPE_MAPPINGS
from ghealth.auth.token_store import load_tokens
from ghealth.commands.context import CliState
from ghealth.data_types import DataTypeInfo
from ghealth.output import FormatEnum, handle_api_error, print_cli_error


def suggested_login_scope(family: str) -> str | None:
    return suggested_scope(family, "read")


def suggested_scope(family: str, access: str) -> str | None:
    scope_url = SCOPE_MAPPINGS.get(family, {}).get(access)
    if not scope_url:
        return None
    for alias, url in SCOPE_ALIASES.items():
        if url == scope_url:
            return alias
    return scope_url


def enrich_data_point_forbidden_details(details: dict, info: DataTypeInfo) -> dict:
    enriched = dict(details)
    scope_arg = suggested_login_scope(info.required_scope_family)
    if scope_arg:
        enriched["suggested_scope"] = scope_arg
        enriched["suggested_login_command"] = f"ghealth auth login --scopes {scope_arg}"
    return enriched


def activity_read_scope_details(details: dict) -> dict:
    enriched = dict(details)
    scope_arg = suggested_login_scope("activity")
    scope_url = SCOPE_ALIASES.get(scope_arg, scope_arg) if scope_arg else None
    if scope_arg and scope_url:
        enriched["required_scope"] = scope_url
        enriched["suggested_scope"] = scope_arg
        enriched["suggested_login_command"] = f"ghealth auth login --scopes {scope_arg}"
        enriched["suggested_combined_login_command"] = "ghealth auth login --with-webhooks"
    return enriched


def require_data_type_operation(
    state: CliState,
    data_type: str,
    operation: str,
) -> DataTypeInfo:
    info = state.registry.get(data_type)
    if not info:
        print_cli_error(
            state,
            "data_type_not_found",
            f"Data type '{data_type}' not found in registry.",
            exit_code=2,
        )
    if operation not in info.supported_operations:
        print_cli_error(
            state,
            "unsupported_operation",
            f"Data type '{data_type}' does not support {operation}.",
            exit_code=2,
            details={"data_type": data_type, "operation": operation},
        )
    return info


def build_optional_time_filter(
    state: CliState,
    info: DataTypeInfo,
    *,
    filter_expr: str | None,
    start: str | None,
    end: str | None,
) -> str | None:
    if filter_expr and (start or end):
        print_cli_error(
            state,
            "invalid_filter_options",
            "Cannot combine --filter with --start or --end.",
            exit_code=2,
        )
    if filter_expr:
        return filter_expr
    if start or end:
        try:
            return build_data_point_time_filter(info, start=start, end=end)
        except ValueError as e:
            print_cli_error(
                state,
                "unsupported_time_filter",
                str(e),
                exit_code=2,
                details={
                    "data_type": info.data_type,
                    "record_type": info.record_type,
                    "documentation_url": info.documentation_url,
                },
            )
    return None


def raise_with_data_point_scope_details(error: GHealthApiError, info: DataTypeInfo) -> NoReturn:
    if error.code == "missing_scope_or_forbidden":
        error.details = enrich_data_point_forbidden_details(error.details, info)
    raise error


def read_json_body(state: CliState, body: Path) -> dict:
    try:
        data = json.loads(body.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print_cli_error(state, "body_file_not_found", f"Body file not found: {body}", exit_code=2)
    except json.JSONDecodeError as e:
        print_cli_error(state, "invalid_body_json", f"Invalid JSON body file: {e}", exit_code=2)
    except OSError as e:
        print_cli_error(state, "body_file_read_failed", f"Could not read body file: {e}", exit_code=2)
    if not isinstance(data, dict):
        print_cli_error(state, "invalid_body_json", "Body JSON must be an object.", exit_code=2)
    return data


def require_confirmation(
    state: CliState,
    *,
    yes: bool,
    action: str,
    target: str,
) -> None:
    if yes:
        return
    is_non_interactive = os.environ.get("GHEALTH_NONINTERACTIVE") == "1" or not sys.stdin.isatty()
    if is_non_interactive or state.output_format == FormatEnum.JSON:
        print_cli_error(
            state,
            "confirmation_required",
            f"{action} requires explicit confirmation. Re-run with --yes to confirm.",
            exit_code=2,
            details={"action": action, "target": target},
        )
    if not typer.confirm(f"{action} {target}?"):
        print_cli_error(
            state,
            "confirmation_rejected",
            f"{action} cancelled.",
            exit_code=1,
            details={"action": action, "target": target},
        )


def require_write_scope(state: CliState, info: DataTypeInfo) -> None:
    scope_arg = suggested_scope(info.required_scope_family, "write")
    if not scope_arg:
        return
    tokens = load_tokens()
    if not tokens:
        return
    token_scopes = set(tokens.get("scope", "").split())
    scope_url = SCOPE_ALIASES.get(scope_arg, scope_arg)
    if scope_url in token_scopes:
        return
    print_cli_error(
        state,
        "write_scope_required",
        f"This command requires write access for {info.required_scope_family} data.",
        exit_code=3,
        details={
            "required_scope": scope_url,
            "suggested_scope": scope_arg,
            "suggested_login_command": f"ghealth auth login --scopes {scope_arg}",
        },
    )


def require_cloud_platform_scope(state: CliState) -> None:
    tokens = load_tokens()
    if not tokens:
        return
    scope_url = SCOPE_ALIASES["cloud-platform"]
    token_scopes = set(tokens.get("scope", "").split())
    if scope_url in token_scopes:
        return
    print_cli_error(
        state,
        "cloud_platform_scope_required",
        "Webhook management commands require Google Cloud Platform scope.",
        exit_code=3,
        details={
            "required_scope": scope_url,
            "suggested_scope": "cloud-platform",
            "suggested_login_command": "ghealth auth login --scopes cloud-platform",
        },
    )


def data_type_from_data_point_name(data_point: str) -> str | None:
    parts = data_point.split("/")
    try:
        index = parts.index("dataTypes")
    except ValueError:
        return None
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def project_name(project: str) -> str:
    return project if project.startswith("projects/") else f"projects/{project}"


def subscriber_name(project: str, subscriber: str) -> str:
    if subscriber.startswith("projects/"):
        return subscriber
    return f"{project_name(project)}/subscribers/{subscriber}"


def subscription_name(subscriber: str, subscription: str) -> str:
    if subscription.startswith("projects/"):
        return subscription
    return f"{subscriber.rstrip('/')}/subscriptions/{subscription}"


def validate_subscriber_name(state: CliState, value: str) -> None:
    parts = value.split("/")
    if len(parts) != 4 or parts[0] != "projects" or parts[2] != "subscribers":
        print_cli_error(
            state,
            "invalid_subscriber_name",
            "Subscriber name must have format projects/{project}/subscribers/{subscriber}.",
            exit_code=2,
            details={"value": value},
        )


def validate_subscription_name(state: CliState, value: str) -> None:
    parts = value.split("/")
    if len(parts) != 6 or parts[0] != "projects" or parts[2] != "subscribers" or parts[4] != "subscriptions":
        print_cli_error(
            state,
            "invalid_subscription_name",
            "Subscription name must have format "
            "projects/{project}/subscribers/{subscriber}/subscriptions/{subscription}.",
            exit_code=2,
            details={"value": value},
        )


def split_csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def validate_limit(state: CliState, limit: int | None) -> int | None:
    if limit is not None and limit <= 0:
        print_cli_error(
            state,
            "invalid_limit",
            "--limit must be greater than 0.",
            exit_code=2,
            details={"limit": limit},
        )
    return limit


def current_civil_date() -> dt.date:
    return dt.date.today()


def resolve_civil_date_range(
    state: CliState,
    *,
    start_date: str | None,
    end_date: str | None,
    last_days: int | None,
) -> tuple[str, str]:
    if last_days is not None:
        if start_date is not None or end_date is not None:
            print_cli_error(
                state,
                "invalid_date_range",
                "Pass either --last-days or both --start-date and --end-date, not both.",
                exit_code=2,
            )
        if last_days <= 0:
            print_cli_error(
                state,
                "invalid_last_days",
                "--last-days must be greater than 0.",
                exit_code=2,
                details={"last_days": last_days},
            )
        end = current_civil_date()
        start = end - dt.timedelta(days=last_days)
        return start.isoformat(), end.isoformat()

    if start_date is None or end_date is None:
        print_cli_error(
            state,
            "date_range_required",
            "Pass both --start-date and --end-date, or pass --last-days.",
            exit_code=2,
        )

    try:
        build_civil_datetime(start_date)
        build_civil_datetime(end_date)
    except ValueError as e:
        print_cli_error(state, "invalid_date", str(e), exit_code=2)
    return start_date, end_date


def apply_list_limit(data: dict, item_key: str, limit: int | None) -> dict:
    if limit is None:
        return data
    items = data.get(item_key)
    if not isinstance(items, list) or len(items) <= limit:
        return data
    limited = dict(data)
    limited[item_key] = items[:limit]
    limited["limited"] = True
    limited["limit"] = limit
    return limited


def subscriber_payload(
    *,
    endpoint_uri: str,
    data_types: str,
    authorization_secret: str,
    subscription_create_policy: str,
) -> dict:
    return {
        "endpointUri": endpoint_uri,
        "subscriberConfigs": [
            {
                "dataTypes": split_csv_values(data_types),
                "subscriptionCreatePolicy": subscription_create_policy,
            },
        ],
        "endpointAuthorization": {"secret": authorization_secret},
    }


def subscription_payload(*, user: str, data_types: str) -> dict:
    return {
        "user": user,
        "dataTypes": split_csv_values(data_types),
    }


def run_with_api_client(state: CliState, callback: Callable[[GHealthApiClient], None]) -> None:
    try:
        api_client = state.create_authenticated_client()
    except GHealthApiError as e:
        handle_api_error(state, e)

    try:
        try:
            callback(api_client)
        except GHealthApiError as e:
            handle_api_error(state, e)
    finally:
        api_client.close()
