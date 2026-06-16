import json

import typer
from rich.table import Table

from ghealth.api import GHealthApiClient, GHealthApiError
from ghealth.commands.context import CliState
from ghealth.commands.shared import (
    activity_read_scope_details,
    apply_list_limit,
    run_with_api_client,
    validate_limit,
)
from ghealth.output import emit_list_by_format, emit_object_by_format

user_app = typer.Typer(help="Read current user identity, profile, and settings")
devices_app = typer.Typer(help="List and get paired devices")


def _identity_raw_lines(data: dict) -> list[str]:
    lines: list[str] = []
    if name := data.get("name"):
        lines.append(name)
    for key in ("healthUserId", "legacyUserId"):
        if value := data.get(key):
            lines.append(f"{key}: {value}")
    return lines or [json.dumps(data)]


@user_app.command(name="identity")
def user_identity(ctx: typer.Context) -> None:
    """Get the current user's identity."""
    state: CliState = ctx.obj

    def run(client: GHealthApiClient) -> None:
        data = client.get_identity()
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _user_identity_table(d),
            raw_builder=_identity_raw_lines,
        )

    run_with_api_client(state, run)


@user_app.command(name="profile")
def user_profile(ctx: typer.Context) -> None:
    """Get the current user's profile."""
    state: CliState = ctx.obj

    def run(client: GHealthApiClient) -> None:
        data = client.get_profile()
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _user_resource_table("Profile", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


@user_app.command(name="settings")
def user_settings(ctx: typer.Context) -> None:
    """Get the current user's settings."""
    state: CliState = ctx.obj

    def run(client: GHealthApiClient) -> None:
        data = client.get_settings()
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _user_resource_table("Settings", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


def _user_identity_table(data: dict) -> Table:
    table = Table(title="User Identity", show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    for key in ("name", "healthUserId", "legacyUserId"):
        if key in data:
            table.add_row(key, str(data[key]))
    return table


def _user_resource_table(title: str, data: dict) -> Table:
    table = Table(title=title, show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    if name := data.get("name"):
        table.add_row("name", name)
    for key, value in sorted(data.items()):
        if key == "name":
            continue
        if isinstance(value, (dict, list)):
            table.add_row(key, json.dumps(value))
        else:
            table.add_row(key, str(value))
    return table


@devices_app.command(name="list")
def devices_list(
    ctx: typer.Context,
    page_size: int | None = typer.Option(None, "--page-size", help="Number of devices per page."),
    page_token: str | None = typer.Option(None, "--page-token", help="Token for the next page."),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of devices to return."),
) -> None:
    """List paired devices for the current user."""
    state: CliState = ctx.obj
    limit = validate_limit(state, limit)

    def run(client: GHealthApiClient) -> None:
        try:
            if all_pages:
                data = client.list_all_paired_devices(page_size=page_size, limit=limit)
            else:
                data = client.list_paired_devices(page_size=page_size, page_token=page_token)
                data = apply_list_limit(data, "pairedDevices", limit)
        except GHealthApiError as e:
            if e.code == "missing_scope_or_forbidden":
                e.details = activity_read_scope_details(e.details)
            raise
        emit_list_by_format(
            state,
            data,
            "pairedDevices",
            table_builder=_paired_devices_table,
        )

    run_with_api_client(state, run)


@devices_app.command(name="get")
def devices_get(
    ctx: typer.Context,
    device: str = typer.Argument(..., help="Paired device ID or full resource name."),
) -> None:
    """Get a paired device by ID or resource name."""
    state: CliState = ctx.obj

    def run(client: GHealthApiClient) -> None:
        try:
            data = client.get_paired_device(device)
        except GHealthApiError as e:
            if e.code == "missing_scope_or_forbidden":
                e.details = activity_read_scope_details(e.details)
            raise
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _paired_device_table(d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


def _paired_devices_table(items: list[dict]) -> Table:
    table = Table(title="Paired Devices")
    table.add_column("Device ID", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Product", style="green")
    table.add_column("Battery", style="yellow")
    table.add_column("Last Sync", style="blue")
    for item in items:
        table.add_row(
            _resource_leaf(item.get("name", "")),
            item.get("deviceType", ""),
            item.get("deviceVersion", ""),
            _format_device_battery(item),
            item.get("lastSyncTime", ""),
        )
    return table


def _paired_device_table(data: dict) -> Table:
    table = Table(title="Paired Device", show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    for key in (
        "name",
        "deviceType",
        "deviceVersion",
        "batteryStatus",
        "batteryLevel",
        "lastSyncTime",
        "macAddress",
        "features",
    ):
        if key in data:
            value = data[key]
            if isinstance(value, list):
                table.add_row(key, ", ".join(str(item) for item in value))
            else:
                table.add_row(key, str(value))
    return table


def _format_device_battery(item: dict) -> str:
    status = item.get("batteryStatus")
    level = item.get("batteryLevel")
    if status and level is not None:
        return f"{status} ({level}%)"
    if status:
        return str(status)
    if level is not None:
        return f"{level}%"
    return ""


def _resource_leaf(resource_name: str) -> str:
    if not resource_name:
        return ""
    return resource_name.rstrip("/").rsplit("/", maxsplit=1)[-1]
