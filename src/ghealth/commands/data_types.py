import typer
from rich.table import Table

from ghealth.auth.scopes import SCOPE_MAPPINGS
from ghealth.commands.context import CliState
from ghealth.output import FormatEnum, console, emit_json, emit_raw_lines, print_cli_error

app = typer.Typer(help="Manage and query G Health data types registry")


@app.command(name="list")
def list_types(ctx: typer.Context) -> None:
    """List all registered G Health data types."""
    state: CliState = ctx.obj
    types = state.registry.list_all()

    if state.output_format == FormatEnum.JSON:
        if not state.quiet:
            emit_json([t.model_dump() for t in types])
    elif state.output_format == FormatEnum.RAW:
        if not state.quiet:
            emit_raw_lines([t.data_type for t in types])
    elif not state.quiet:
        table = Table(title="G Health Data Types")
        table.add_column("Data Type ID", style="cyan")
        table.add_column("Display Name", style="magenta")
        table.add_column("Record Type", style="green")
        table.add_column("Scope Family", style="yellow")
        table.add_column("Operations", style="blue")

        for t in types:
            table.add_row(
                t.data_type,
                t.display_name,
                t.record_type,
                t.required_scope_family,
                ", ".join(t.supported_operations),
            )
        console.print(table)


@app.command(name="describe")
def describe_type(
    ctx: typer.Context,
    data_type: str = typer.Argument(..., help="The kebab-case ID of the data type (e.g. 'steps')"),
) -> None:
    """Show details of a specific data type."""
    state: CliState = ctx.obj
    info = state.registry.get(data_type)
    if not info:
        error_msg = f"Data type '{data_type}' not found in registry."
        print_cli_error(state, "data_type_not_found", error_msg, exit_code=2)

    if state.output_format in (FormatEnum.JSON, FormatEnum.RAW):
        if not state.quiet:
            if state.output_format == FormatEnum.JSON:
                emit_json(info.model_dump())
            else:
                raw = state.registry.describe(data_type)
                if raw:
                    console.print(raw)
    elif not state.quiet:
        table = Table(title=f"Data Type: {info.display_name}", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        table.add_row("Display Name", info.display_name)
        table.add_row("Data Type ID", info.data_type)
        table.add_row("Filter Name", info.filter_name)
        table.add_row("Record Type", info.record_type)
        table.add_row("Required Scope Family", info.required_scope_family)
        table.add_row("Webhook Support", "Yes" if info.webhook_support else "No")
        table.add_row("True-Zero Support", "Yes" if info.true_zero_support else "No")
        table.add_row("Supported Operations", ", ".join(info.supported_operations))
        table.add_row("Documentation", info.documentation_url)
        console.print(table)


@app.command(name="operations")
def operations_type(
    ctx: typer.Context,
    data_type: str = typer.Argument(..., help="The kebab-case ID of the data type"),
) -> None:
    """List supported operations for a specific data type."""
    state: CliState = ctx.obj
    info = state.registry.get(data_type)
    if not info:
        error_msg = f"Data type '{data_type}' not found in registry."
        print_cli_error(state, "data_type_not_found", error_msg, exit_code=2)

    if state.output_format == FormatEnum.JSON:
        if not state.quiet:
            emit_json(info.supported_operations)
    elif not state.quiet:
        emit_raw_lines(info.supported_operations)


@app.command(name="scopes")
def scopes_type(
    ctx: typer.Context,
    data_type: str = typer.Argument(..., help="The kebab-case ID of the data type"),
) -> None:
    """List required OAuth scopes for a specific data type."""
    state: CliState = ctx.obj
    info = state.registry.get(data_type)
    if not info:
        error_msg = f"Data type '{data_type}' not found in registry."
        print_cli_error(state, "data_type_not_found", error_msg, exit_code=2)

    scopes_dict = SCOPE_MAPPINGS.get(info.required_scope_family, {})
    scopes_list = list(scopes_dict.values())

    if state.output_format == FormatEnum.JSON:
        if not state.quiet:
            emit_json(scopes_list)
    elif not state.quiet:
        emit_raw_lines(scopes_list)
