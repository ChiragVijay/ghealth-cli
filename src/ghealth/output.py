import enum
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from ghealth.api import API_ERROR_EXIT_CODES, GHealthApiError

if TYPE_CHECKING:
    from ghealth.commands.context import CliState

console = Console()


class FormatEnum(enum.StrEnum):
    JSON = "json"
    TABLE = "table"
    RAW = "raw"


def emit_json(data: object) -> None:
    typer.echo(json.dumps(data, indent=2, sort_keys=True))


def emit_raw_lines(lines: list[str]) -> None:
    for line in lines:
        typer.echo(line)


def print_cli_error(
    state: "CliState",
    code: str,
    message: str,
    exit_code: int = 1,
    details: dict | None = None,
) -> NoReturn:
    if details is None:
        details = {}
    if state.output_format == FormatEnum.JSON:
        emit_json({"error": {"code": code, "message": message, "details": details}})
    elif not state.quiet:
        console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code=exit_code)


def handle_api_error(state: "CliState", error: GHealthApiError) -> NoReturn:
    exit_code = API_ERROR_EXIT_CODES.get(error.code, 4)
    print_cli_error(state, error.code, error.message, exit_code=exit_code, details=error.details)


def emit_object_by_format(
    state: "CliState",
    data: dict,
    *,
    table_builder: Callable[[dict], Table] | None = None,
    raw_builder: Callable[[dict], list[str]] | None = None,
) -> None:
    if state.quiet:
        return
    if state.output_format == FormatEnum.JSON:
        emit_json(data)
    elif state.output_format == FormatEnum.RAW:
        if raw_builder:
            emit_raw_lines(raw_builder(data))
        else:
            emit_json(data)
    elif table_builder:
        console.print(table_builder(data))


def emit_list_by_format(
    state: "CliState",
    data: dict,
    item_key: str,
    *,
    table_builder: Callable[[list[dict]], Table] | None = None,
    raw_name_key: str = "name",
) -> None:
    if state.quiet:
        return
    items = data.get(item_key, [])
    if state.output_format == FormatEnum.JSON:
        emit_json(data)
    elif state.output_format == FormatEnum.RAW:
        emit_raw_lines([item.get(raw_name_key, "") for item in items if item.get(raw_name_key)])
    elif table_builder:
        console.print(table_builder(items))
