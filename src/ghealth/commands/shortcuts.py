import typer

from ghealth.api import GHealthApiClient, GHealthApiError
from ghealth.commands.context import CliState
from ghealth.commands.data_points import _data_points_table, _rollup_data_points_table
from ghealth.commands.shared import (
    apply_list_limit,
    build_optional_time_filter,
    raise_with_data_point_scope_details,
    require_data_type_operation,
    resolve_civil_date_range,
    run_with_api_client,
    validate_limit,
)
from ghealth.output import emit_list_by_format

steps_app = typer.Typer(help="Shortcut commands for step data")
sleep_app = typer.Typer(help="Shortcut commands for sleep data")
heart_rate_app = typer.Typer(help="Shortcut commands for heart rate data")
calories_app = typer.Typer(help="Shortcut commands for calorie data")
active_energy_app = typer.Typer(help="Shortcut commands for active energy data")
active_minutes_app = typer.Typer(help="Shortcut commands for active minutes data")
active_zone_minutes_app = typer.Typer(help="Shortcut commands for active zone minutes data")
distance_app = typer.Typer(help="Shortcut commands for distance data")
floors_app = typer.Typer(help="Shortcut commands for floor count data")
exercise_app = typer.Typer(help="Shortcut commands for exercise data")
weight_app = typer.Typer(help="Shortcut commands for weight data")
height_app = typer.Typer(help="Shortcut commands for height data")
body_fat_app = typer.Typer(help="Shortcut commands for body fat data")
hydration_app = typer.Typer(help="Shortcut commands for hydration data")
food_app = typer.Typer(help="Shortcut commands for food data")
nutrition_app = typer.Typer(help="Shortcut commands for nutrition data")

SHORTCUT_APPS = (
    ("steps", steps_app),
    ("sleep", sleep_app),
    ("heart-rate", heart_rate_app),
    ("calories", calories_app),
    ("active-energy", active_energy_app),
    ("active-minutes", active_minutes_app),
    ("active-zone-minutes", active_zone_minutes_app),
    ("distance", distance_app),
    ("floors", floors_app),
    ("exercise", exercise_app),
    ("weight", weight_app),
    ("height", height_app),
    ("body-fat", body_fat_app),
    ("hydration", hydration_app),
    ("food", food_app),
    ("nutrition", nutrition_app),
)


def _run_data_points_list_shortcut(
    state: CliState,
    *,
    data_type: str,
    start: str | None,
    end: str | None,
    filter_expr: str | None,
    page_size: int | None,
    page_token: str | None,
    all_pages: bool,
    limit: int | None,
) -> None:
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
        emit_list_by_format(state, data, "dataPoints", table_builder=_data_points_table)

    run_with_api_client(state, run)


def _run_daily_rollup_shortcut(
    state: CliState,
    *,
    data_type: str,
    start_date: str | None,
    end_date: str | None,
    last_days: int | None,
    window_size_days: int | None,
    page_size: int | None,
    page_token: str | None,
    data_source_family: str | None = None,
    limit: int | None = None,
) -> None:
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
        emit_list_by_format(state, data, "rollupDataPoints", table_builder=_rollup_data_points_table)

    run_with_api_client(state, run)


def _register_daily_shortcut(
    app: typer.Typer,
    *,
    function_name: str,
    data_type: str,
    description: str,
) -> None:
    def command(
        ctx: typer.Context,
        start_date: str | None = typer.Option(
            None,
            "--start-date",
            help="Inclusive civil start date, YYYY-MM-DD.",
        ),
        end_date: str | None = typer.Option(
            None,
            "--end-date",
            help="Exclusive civil end date, YYYY-MM-DD.",
        ),
        last_days: int | None = typer.Option(
            None,
            "--last-days",
            help="Use the last N complete civil days ending today.",
        ),
        window_size_days: int | None = typer.Option(
            None,
            "--window-size-days",
            help="Aggregation window in days.",
        ),
        page_size: int | None = typer.Option(
            None,
            "--page-size",
            help="Number of rollup points per page.",
        ),
        page_token: str | None = typer.Option(None, "--page-token", help="Token for the next page."),
        limit: int | None = typer.Option(None, "--limit", help="Maximum number of rollup points to return."),
    ) -> None:
        _run_daily_rollup_shortcut(
            ctx.obj,
            data_type=data_type,
            start_date=start_date,
            end_date=end_date,
            last_days=last_days,
            window_size_days=window_size_days,
            page_size=page_size,
            page_token=page_token,
            limit=limit,
        )

    command.__name__ = function_name
    command.__doc__ = description
    app.command(name="daily")(command)


def _register_list_shortcut(
    app: typer.Typer,
    *,
    function_name: str,
    data_type: str,
    description: str,
) -> None:
    def command(
        ctx: typer.Context,
        start: str | None = typer.Option(None, "--start", help="Start time (RFC3339 or date)."),
        end: str | None = typer.Option(None, "--end", help="End time (RFC3339 or date)."),
        filter_expr: str | None = typer.Option(None, "--filter", help="Raw Google AIP-160 filter."),
        page_size: int | None = typer.Option(
            None,
            "--page-size",
            help="Number of data points per page.",
        ),
        page_token: str | None = typer.Option(None, "--page-token", help="Token for the next page."),
        all_pages: bool = typer.Option(False, "--all", help="Fetch all pages."),
        limit: int | None = typer.Option(None, "--limit", help="Maximum number of data points to return."),
    ) -> None:
        _run_data_points_list_shortcut(
            ctx.obj,
            data_type=data_type,
            start=start,
            end=end,
            filter_expr=filter_expr,
            page_size=page_size,
            page_token=page_token,
            all_pages=all_pages,
            limit=limit,
        )

    command.__name__ = function_name
    command.__doc__ = description
    app.command(name="list")(command)


DAILY_SHORTCUTS = (
    (steps_app, "steps_daily", "steps", "Daily step rollups."),
    (calories_app, "calories_daily", "total-calories", "Daily total calorie rollups."),
    (
        active_energy_app,
        "active_energy_daily",
        "active-energy-burned",
        "Daily active energy burned rollups.",
    ),
    (active_minutes_app, "active_minutes_daily", "active-minutes", "Daily active minutes rollups."),
    (
        active_zone_minutes_app,
        "active_zone_minutes_daily",
        "active-zone-minutes",
        "Daily active zone minutes rollups.",
    ),
    (distance_app, "distance_daily", "distance", "Daily distance rollups."),
    (floors_app, "floors_daily", "floors", "Daily floor count rollups."),
)


LIST_SHORTCUTS = (
    (sleep_app, "sleep_list", "sleep", "List sleep data points."),
    (heart_rate_app, "heart_rate_list", "heart-rate", "List heart rate data points."),
    (exercise_app, "exercise_list", "exercise", "List exercise data points."),
    (weight_app, "weight_list", "weight", "List weight data points."),
    (height_app, "height_list", "height", "List height data points."),
    (body_fat_app, "body_fat_list", "body-fat", "List body fat data points."),
    (hydration_app, "hydration_list", "hydration-log", "List hydration log data points."),
    (food_app, "food_list", "food", "List food data points."),
    (nutrition_app, "nutrition_list", "nutrition-log", "List nutrition log data points."),
)


for shortcut_app, callback_name, mapped_data_type, help_text in DAILY_SHORTCUTS:
    _register_daily_shortcut(
        shortcut_app,
        function_name=callback_name,
        data_type=mapped_data_type,
        description=help_text,
    )


for shortcut_app, callback_name, mapped_data_type, help_text in LIST_SHORTCUTS:
    _register_list_shortcut(
        shortcut_app,
        function_name=callback_name,
        data_type=mapped_data_type,
        description=help_text,
    )
