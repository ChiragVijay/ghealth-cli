import json
from pathlib import Path

import typer
from rich.table import Table

from ghealth.api import GHealthApiClient, GHealthApiError
from ghealth.commands.context import CliState
from ghealth.commands.shared import (
    apply_list_limit,
    build_optional_time_filter,
    data_type_from_data_point_name,
    raise_with_data_point_scope_details,
    read_json_body,
    require_confirmation,
    require_data_type_operation,
    require_write_scope,
    resolve_civil_date_range,
    run_with_api_client,
    validate_limit,
)
from ghealth.output import (
    FormatEnum,
    console,
    emit_json,
    emit_list_by_format,
    emit_object_by_format,
    print_cli_error,
)

app = typer.Typer(help="List and get health data points")


@app.command(name="list")
def data_points_list(
    ctx: typer.Context,
    data_type: str = typer.Argument(..., help="Data type ID (e.g. 'steps')."),
    start: str | None = typer.Option(None, "--start", help="Start time (RFC3339 or date)."),
    end: str | None = typer.Option(None, "--end", help="End time (RFC3339 or date)."),
    filter_expr: str | None = typer.Option(None, "--filter", help="Raw Google AIP-160 filter."),
    page_size: int | None = typer.Option(None, "--page-size", help="Number of data points per page."),
    page_token: str | None = typer.Option(None, "--page-token", help="Token for the next page."),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of data points to return."),
) -> None:
    """List data points for a data type."""
    state: CliState = ctx.obj
    limit = validate_limit(state, limit)

    info = require_data_type_operation(state, data_type, "list")
    built_filter = build_optional_time_filter(
        state,
        info,
        filter_expr=filter_expr,
        start=start,
        end=end,
    )

    def run(client: GHealthApiClient) -> None:
        try:
            if all_pages:
                data = client.list_all_data_points(
                    data_type,
                    page_size=page_size,
                    filter=built_filter,
                    limit=limit,
                )
            else:
                data = client.list_data_points(
                    data_type,
                    page_size=page_size,
                    page_token=page_token,
                    filter=built_filter,
                )
                data = apply_list_limit(data, "dataPoints", limit)
        except GHealthApiError as e:
            raise_with_data_point_scope_details(e, info)
        emit_list_by_format(
            state,
            data,
            "dataPoints",
            table_builder=_data_points_table,
        )

    run_with_api_client(state, run)


@app.command(name="reconcile")
def data_points_reconcile(
    ctx: typer.Context,
    data_type: str = typer.Argument(..., help="Data type ID (e.g. 'steps')."),
    start: str | None = typer.Option(None, "--start", help="Start time (RFC3339 or date)."),
    end: str | None = typer.Option(None, "--end", help="End time (RFC3339 or date)."),
    filter_expr: str | None = typer.Option(None, "--filter", help="Raw Google AIP-160 filter."),
    data_source_family: str | None = typer.Option(
        None,
        "--data-source-family",
        help="Data source family ID or full resource name.",
    ),
    page_size: int | None = typer.Option(None, "--page-size", help="Number of data points per page."),
    page_token: str | None = typer.Option(None, "--page-token", help="Token for the next page."),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of data points to return."),
) -> None:
    """Reconcile data points across data sources into one stream."""
    state: CliState = ctx.obj
    limit = validate_limit(state, limit)
    info = require_data_type_operation(state, data_type, "reconcile")
    built_filter = build_optional_time_filter(
        state,
        info,
        filter_expr=filter_expr,
        start=start,
        end=end,
    )

    def run(client: GHealthApiClient) -> None:
        try:
            if all_pages:
                data = client.list_all_reconciled_data_points(
                    data_type,
                    page_size=page_size,
                    filter=built_filter,
                    data_source_family=data_source_family,
                    limit=limit,
                )
            else:
                data = client.reconcile_data_points(
                    data_type,
                    page_size=page_size,
                    page_token=page_token,
                    filter=built_filter,
                    data_source_family=data_source_family,
                )
                data = apply_list_limit(data, "dataPoints", limit)
        except GHealthApiError as e:
            raise_with_data_point_scope_details(e, info)
        emit_list_by_format(
            state,
            data,
            "dataPoints",
            table_builder=_data_points_table,
            raw_name_key="dataPointName",
        )

    run_with_api_client(state, run)


@app.command(name="rollup")
def data_points_rollup(
    ctx: typer.Context,
    data_type: str = typer.Argument(..., help="Data type ID (e.g. 'steps')."),
    start: str = typer.Option(..., "--start", help="Inclusive RFC3339 start timestamp."),
    end: str = typer.Option(..., "--end", help="Exclusive RFC3339 end timestamp."),
    window_size: str = typer.Option(..., "--window-size", help="Aggregation window duration, e.g. 3600s."),
    data_source_family: str | None = typer.Option(
        None,
        "--data-source-family",
        help="Data source family ID or full resource name.",
    ),
    page_size: int | None = typer.Option(None, "--page-size", help="Number of rollup points per page."),
    page_token: str | None = typer.Option(None, "--page-token", help="Token for the next page."),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of rollup points to return."),
) -> None:
    """Roll up data points over physical time windows."""
    state: CliState = ctx.obj
    limit = validate_limit(state, limit)
    info = require_data_type_operation(state, data_type, "rollUp")

    def run(client: GHealthApiClient) -> None:
        try:
            if all_pages:
                data = client.list_all_rollup_data_points(
                    data_type,
                    start_time=start,
                    end_time=end,
                    window_size=window_size,
                    page_size=page_size,
                    data_source_family=data_source_family,
                    limit=limit,
                )
            else:
                data = client.rollup_data_points(
                    data_type,
                    start_time=start,
                    end_time=end,
                    window_size=window_size,
                    page_size=page_size,
                    page_token=page_token,
                    data_source_family=data_source_family,
                )
                data = apply_list_limit(data, "rollupDataPoints", limit)
        except GHealthApiError as e:
            raise_with_data_point_scope_details(e, info)
        emit_list_by_format(
            state,
            data,
            "rollupDataPoints",
            table_builder=_rollup_data_points_table,
        )

    run_with_api_client(state, run)


@app.command(name="daily-rollup")
def data_points_daily_rollup(
    ctx: typer.Context,
    data_type: str = typer.Argument(..., help="Data type ID (e.g. 'steps')."),
    start_date: str | None = typer.Option(
        None, "--start-date", help="Inclusive civil start date, YYYY-MM-DD."
    ),
    end_date: str | None = typer.Option(None, "--end-date", help="Exclusive civil end date, YYYY-MM-DD."),
    last_days: int | None = typer.Option(
        None,
        "--last-days",
        help="Use the last N complete civil days ending today.",
    ),
    window_size_days: int | None = typer.Option(
        None,
        "--window-size-days",
        help="Aggregation window in days. Defaults to API behavior.",
    ),
    data_source_family: str | None = typer.Option(
        None,
        "--data-source-family",
        help="Data source family ID or full resource name.",
    ),
    page_size: int | None = typer.Option(None, "--page-size", help="Number of rollup points per page."),
    page_token: str | None = typer.Option(None, "--page-token", help="Token for the next page."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of rollup points to return."),
) -> None:
    """Roll up data points over civil-day windows."""
    state: CliState = ctx.obj
    limit = validate_limit(state, limit)
    info = require_data_type_operation(state, data_type, "dailyRollUp")
    start_date, end_date = resolve_civil_date_range(
        state,
        start_date=start_date,
        end_date=end_date,
        last_days=last_days,
    )

    def run(client: GHealthApiClient) -> None:
        try:
            data = client.daily_rollup_data_points(
                data_type,
                start_date=start_date,
                end_date=end_date,
                window_size_days=window_size_days,
                page_size=page_size,
                page_token=page_token,
                data_source_family=data_source_family,
            )
            data = apply_list_limit(data, "rollupDataPoints", limit)
        except GHealthApiError as e:
            raise_with_data_point_scope_details(e, info)
        emit_list_by_format(
            state,
            data,
            "rollupDataPoints",
            table_builder=_rollup_data_points_table,
        )

    run_with_api_client(state, run)


@app.command(name="create")
def data_points_create(
    ctx: typer.Context,
    data_type: str = typer.Argument(..., help="Data type ID (e.g. 'weight')."),
    body: Path = typer.Option(..., "--body", help="Path to a JSON DataPoint request body."),
    yes: bool = typer.Option(False, "--yes", help="Confirm creation without prompting."),
) -> None:
    """Create a single identifiable data point from a JSON body."""
    state: CliState = ctx.obj
    info = require_data_type_operation(state, data_type, "create")
    require_write_scope(state, info)
    data_point_body = read_json_body(state, body)
    require_confirmation(state, yes=yes, action="Create data point", target=data_type)

    def run(client: GHealthApiClient) -> None:
        try:
            data = client.create_data_point(data_type, data_point_body)
        except GHealthApiError as e:
            raise_with_data_point_scope_details(e, info)
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _operation_table("Create Data Point Operation", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


@app.command(name="update")
def data_points_update(
    ctx: typer.Context,
    data_point: str = typer.Argument(..., help="Data point ID or full resource name."),
    body: Path = typer.Option(..., "--body", help="Path to a JSON DataPoint request body."),
    data_type: str | None = typer.Option(
        None,
        "--data-type",
        help="Data type ID. Required when DATA_POINT is not a full resource name.",
    ),
    update_mask: str | None = typer.Option(None, "--update-mask", help="Comma-separated field mask."),
    yes: bool = typer.Option(False, "--yes", help="Confirm update without prompting."),
) -> None:
    """Update a single identifiable data point from a JSON body."""
    state: CliState = ctx.obj
    resolved_data_type = data_type or data_type_from_data_point_name(data_point)
    if not resolved_data_type:
        print_cli_error(
            state,
            "data_type_required",
            "Pass --data-type when DATA_POINT is not a full users/.../dataTypes/... resource name.",
            exit_code=2,
        )
    info = require_data_type_operation(state, resolved_data_type, "update")
    require_write_scope(state, info)
    data_point_body = read_json_body(state, body)
    require_confirmation(state, yes=yes, action="Update data point", target=data_point)

    def run(client: GHealthApiClient) -> None:
        try:
            data = client.update_data_point(
                resolved_data_type,
                data_point,
                data_point_body,
                update_mask=update_mask,
            )
        except GHealthApiError as e:
            raise_with_data_point_scope_details(e, info)
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _operation_table("Update Data Point Operation", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


@app.command(name="batch-delete")
def data_points_batch_delete(
    ctx: typer.Context,
    data_type: str = typer.Argument(..., help="Data type ID, or '-' to delete across data type collections."),
    names: list[str] | None = typer.Option(
        None,
        "--name",
        help="Full data point resource name. Repeat for multiple data points.",
    ),
    names_file: Path | None = typer.Option(
        None,
        "--names-file",
        help="File containing one full data point resource name per line.",
    ),
    yes: bool = typer.Option(False, "--yes", help="Confirm deletion without prompting."),
) -> None:
    """Delete identifiable data points in one batch."""
    state: CliState = ctx.obj
    info = None if data_type == "-" else require_data_type_operation(state, data_type, "batchDelete")
    if info:
        require_write_scope(state, info)
    data_point_names = _collect_delete_names(state, names=names or [], names_file=names_file)
    require_confirmation(
        state,
        yes=yes,
        action="Delete data points",
        target=f"{len(data_point_names)} item(s)",
    )

    def run(client: GHealthApiClient) -> None:
        try:
            data = client.batch_delete_data_points(data_type, data_point_names)
        except GHealthApiError as e:
            if info:
                raise_with_data_point_scope_details(e, info)
            raise
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _operation_table("Batch Delete Operation", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


@app.command(name="export-exercise-tcx")
def data_points_export_exercise_tcx(
    ctx: typer.Context,
    data_point: str = typer.Argument(..., help="Exercise data point ID or full resource name."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Path to write TCX output."),
    partial_data: bool | None = typer.Option(
        None,
        "--partial-data/--no-partial-data",
        help="Include partial TCX data when GPS data is unavailable.",
    ),
) -> None:
    """Export an exercise data point as raw TCX."""
    state: CliState = ctx.obj
    require_data_type_operation(state, "exercise", "exportExerciseTcx")

    def run(client: GHealthApiClient) -> None:
        data = client.export_exercise_tcx(data_point, partial_data=partial_data)
        if output is not None:
            output.write_text(data, encoding="utf-8")
            if state.output_format == FormatEnum.JSON:
                emit_json({"exported": True, "output": str(output)})
            elif not state.quiet:
                console.print(f"[green]Success:[/green] TCX written to {output}")
            return
        if state.quiet:
            return
        if state.output_format == FormatEnum.JSON:
            emit_json({"tcxData": data})
        else:
            typer.echo(data)

    run_with_api_client(state, run)


@app.command(name="get")
def data_points_get(
    ctx: typer.Context,
    data_type: str = typer.Argument(..., help="Data type ID (e.g. 'steps')."),
    data_point: str = typer.Argument(..., help="Data point ID or full resource name."),
) -> None:
    """Get a data point by ID or resource name."""
    state: CliState = ctx.obj

    info = require_data_type_operation(state, data_type, "get")

    def run(client: GHealthApiClient) -> None:
        try:
            data = client.get_data_point(data_type, data_point)
        except GHealthApiError as e:
            raise_with_data_point_scope_details(e, info)
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _data_point_table(d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


def _data_points_table(items: list[dict]) -> Table:
    table = Table(title="Data Points")
    table.add_column("Name", style="cyan")
    table.add_column("Start Time", style="magenta")
    for item in items:
        start_time = ""
        for value in item.values():
            if isinstance(value, dict):
                interval = value.get("interval")
                if isinstance(interval, dict) and "startTime" in interval:
                    start_time = interval["startTime"]
                    break
                sample_time = value.get("sampleTime")
                if isinstance(sample_time, dict) and "physicalTime" in sample_time:
                    start_time = sample_time["physicalTime"]
                    break
        table.add_row(item.get("name", item.get("dataPointName", "")), start_time)
    return table


def _rollup_data_points_table(items: list[dict]) -> Table:
    table = Table(title="Rollup Data Points")
    table.add_column("Window Start", style="cyan")
    table.add_column("Window End", style="magenta")
    table.add_column("Values", style="green")
    for item in items:
        start = item.get("startTime") or _format_civil_datetime(item.get("civilStartTime"))
        end = item.get("endTime") or _format_civil_datetime(item.get("civilEndTime"))
        value_keys = [
            key
            for key, value in item.items()
            if key not in ("startTime", "endTime", "civilStartTime", "civilEndTime")
            and isinstance(value, dict)
        ]
        table.add_row(str(start or ""), str(end or ""), ", ".join(value_keys))
    return table


def _format_civil_datetime(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    date_value = value.get("date")
    if not isinstance(date_value, dict):
        return ""
    year = date_value.get("year")
    month = date_value.get("month")
    day = date_value.get("day")
    if not isinstance(year, int) or not isinstance(month, int) or not isinstance(day, int):
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def _collect_delete_names(
    state: CliState,
    *,
    names: list[str],
    names_file: Path | None,
) -> list[str]:
    collected = list(names)
    if names_file is not None:
        try:
            collected.extend(
                line.strip() for line in names_file.read_text(encoding="utf-8").splitlines() if line.strip()
            )
        except FileNotFoundError:
            print_cli_error(state, "names_file_not_found", f"Names file not found: {names_file}", exit_code=2)
        except OSError as e:
            print_cli_error(state, "names_file_read_failed", f"Could not read names file: {e}", exit_code=2)
    if not collected:
        print_cli_error(
            state,
            "missing_data_point_names",
            "Pass at least one --name or a --names-file.",
            exit_code=2,
        )
    if len(collected) > 10000:
        print_cli_error(
            state,
            "too_many_data_point_names",
            "batch-delete supports at most 10000 names per request.",
            exit_code=2,
            details={"count": len(collected)},
        )
    return collected


def _operation_table(title: str, data: dict) -> Table:
    table = Table(title=title, show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    for key, value in sorted(data.items()):
        if isinstance(value, (dict, list)):
            table.add_row(key, json.dumps(value))
        else:
            table.add_row(key, str(value))
    return table


def _data_point_table(data: dict) -> Table:
    table = Table(title="Data Point", show_header=False)
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
