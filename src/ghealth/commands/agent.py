import time
from typing import Any

import typer
from rich.table import Table

from ghealth.auth.scopes import SCOPE_MAPPINGS
from ghealth.auth.token_store import load_tokens
from ghealth.commands.context import CliState
from ghealth.config import load_config
from ghealth.output import FormatEnum, console, emit_json

app = typer.Typer(help="Agent-oriented diagnostics and examples")


@app.command(name="doctor")
def doctor(ctx: typer.Context) -> None:
    """Report local CLI readiness without exposing secrets."""
    state: CliState = ctx.obj
    data = build_doctor_report()

    if state.quiet:
        return
    if state.output_format in (FormatEnum.JSON, FormatEnum.RAW):
        emit_json(data)
        return

    table = Table(title="G Health Doctor", show_header=False)
    table.add_column("Check", style="cyan")
    table.add_column("Value")
    table.add_row("Configured", str(data["configured"]))
    table.add_row("Authenticated", str(data["authenticated"]))
    table.add_row("Token expired", str(data["token"].get("expired")))
    table.add_row("Storage", str(data["config"].get("token_storage_backend", "")))
    table.add_row("Client ID", str(data["config"].get("client_id", "")))
    table.add_row("Scopes", ", ".join(data["token"].get("scopes", [])))
    table.add_row("Next action", str(data["next_action"]))
    console.print(table)


@app.command(name="examples")
def examples(ctx: typer.Context) -> None:
    """Show safe command examples for humans and AI agents."""
    state: CliState = ctx.obj
    data = build_examples()

    if state.quiet:
        return
    if state.output_format in (FormatEnum.JSON, FormatEnum.RAW):
        emit_json(data)
        return

    table = Table(title="G Health Examples")
    table.add_column("Group", style="cyan")
    table.add_column("Command")
    table.add_column("Notes")
    for group in data["groups"]:
        for example in group["examples"]:
            table.add_row(group["name"], example["command"], example.get("notes", ""))
    console.print(table)


def build_doctor_report() -> dict[str, Any]:
    config = load_config()
    tokens = load_tokens()
    now = int(time.time())
    expires_at = int(tokens.get("expires_at", 0)) if tokens else None
    scopes = _split_scopes(tokens.get("scope", "")) if tokens else []
    missing_common_read_scopes = sorted(_common_read_scopes() - set(scopes))

    configured = config is not None
    authenticated = bool(tokens and tokens.get("access_token"))
    expired = bool(expires_at is not None and now >= expires_at)

    if not configured:
        next_action = "Run ghealth auth configure --credentials PATH_TO_CLIENT_SECRET_JSON."
    elif not authenticated:
        next_action = "Run ghealth auth login."
    elif expired:
        next_action = "Run ghealth auth refresh or ghealth auth login."
    elif missing_common_read_scopes:
        next_action = "Run ghealth auth login if read commands need more scopes."
    else:
        next_action = "Ready for read commands."

    return {
        "configured": configured,
        "authenticated": authenticated,
        "config": {
            "token_storage_backend": config.token_storage if config else None,
            "client_id": _redact_client_id(config.client_id) if config else None,
            "user_email": config.user_email if config else None,
            "auth_uri_configured": bool(config.auth_uri) if config else False,
            "token_uri_configured": bool(config.token_uri) if config else False,
        },
        "token": {
            "present": tokens is not None,
            "expires_at": expires_at,
            "expired": expired if tokens else None,
            "expires_in_seconds": max(0, expires_at - now) if expires_at is not None else None,
            "scopes": scopes,
            "missing_common_read_scopes": missing_common_read_scopes,
        },
        "next_action": next_action,
        "privacy": {
            "secrets_redacted": True,
            "tokens_printed": False,
        },
    }


def build_examples() -> dict[str, Any]:
    return {
        "default_format": "json",
        "safety": [
            "Health data is sensitive.",
            "Use the narrowest date range possible.",
            "Use --limit when exploring unknown data.",
            "Do not write, delete, export large files, or revoke auth unless explicitly requested.",
        ],
        "groups": [
            {
                "name": "check",
                "examples": [
                    {
                        "command": "ghealth --format json doctor",
                        "notes": "Check config, auth, scopes, and next action without printing secrets.",
                    },
                    {
                        "command": "ghealth --format json auth status",
                        "notes": "Show current auth status.",
                    },
                ],
            },
            {
                "name": "discover",
                "examples": [
                    {
                        "command": "ghealth --format json data-types list",
                        "notes": "List supported data types.",
                    },
                    {
                        "command": "ghealth --format json data-types describe steps",
                        "notes": "Inspect one data type before querying it.",
                    },
                    {
                        "command": "ghealth --format json auth scopes",
                        "notes": "Check authorized OAuth scopes.",
                    },
                ],
            },
            {
                "name": "read",
                "examples": [
                    {
                        "command": "ghealth --format json steps daily --last-days 5",
                        "notes": "Read daily step rollups.",
                    },
                    {
                        "command": "ghealth --format json calories daily --last-days 5",
                        "notes": "Read daily total calorie rollups. Maps to the total-calories data type.",
                    },
                    {
                        "command": "ghealth --format json distance daily --last-days 5",
                        "notes": "Read daily distance rollups.",
                    },
                    {
                        "command": "ghealth --format json active-minutes daily --last-days 5",
                        "notes": "Read daily active minutes rollups.",
                    },
                    {
                        "command": (
                            "ghealth --format json sleep list --start 2026-06-01 --end 2026-06-10 --limit 25"
                        ),
                        "notes": "Read a bounded sleep range.",
                    },
                    {
                        "command": "ghealth --format json exercise list --start 2026-06-01 --limit 25",
                        "notes": "Read bounded exercise sessions.",
                    },
                    {
                        "command": "ghealth --format json devices list --limit 25",
                        "notes": "List paired devices.",
                    },
                    {
                        "command": "ghealth --format json user profile",
                        "notes": "Read the current user's profile.",
                    },
                ],
            },
            {
                "name": "webhooks",
                "examples": [
                    {
                        "command": "ghealth --format json subscribers list --project PROJECT_ID --limit 25",
                        "notes": "Requires cloud-platform scope and webhook infrastructure.",
                    },
                ],
            },
            {
                "name": "destructive",
                "examples": [
                    {
                        "command": "ghealth data-points batch-delete DATA_TYPE --name DATA_POINT_NAME --yes",
                        "notes": "Only after explicit user confirmation.",
                        "requires_explicit_user_confirmation": True,
                    },
                    {
                        "command": "ghealth auth revoke",
                        "notes": "Only if the user asks to revoke local Google Health auth.",
                        "requires_explicit_user_confirmation": True,
                    },
                ],
            },
        ],
    }


def _split_scopes(scope_value: str) -> list[str]:
    return [scope for scope in scope_value.split() if scope]


def _common_read_scopes() -> set[str]:
    scopes: set[str] = set()
    for access_map in SCOPE_MAPPINGS.values():
        scope = access_map.get("read")
        if scope:
            scopes.add(scope)
    return scopes


def _redact_client_id(client_id: str) -> str:
    if len(client_id) <= 8:
        return "***"
    return f"{client_id[:4]}...{client_id[-4:]}"
