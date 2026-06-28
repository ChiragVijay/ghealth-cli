from datetime import date

from ghealth.data_types import DataTypeInfo


def _uses_physical_time(value: str) -> bool:
    return value.endswith("Z") or "+" in value[10:] or "-" in value[10:]


def _require_civil_time(info: DataTypeInfo, uses_physical_time: bool) -> None:
    if uses_physical_time:
        msg = f"{info.data_type} time filters support date-only civil ranges."
        raise ValueError(msg)


def build_data_point_time_filter(
    info: DataTypeInfo,
    *,
    start: str | None = None,
    end: str | None = None,
) -> str:
    """Build a simple AIP-160 time-range filter for a data type."""
    filter_name = info.filter_name
    record_type = info.record_type

    first_bound = start or end or ""
    uses_physical_time = _uses_physical_time(first_bound)

    if record_type == "interval":
        if info.data_type in {"hydration-log", "nutrition-log"}:
            _require_civil_time(info, uses_physical_time)
            field = f"{filter_name}.interval.civil_start_time"
        else:
            suffix = "start_time" if uses_physical_time else "civil_start_time"
            field = f"{filter_name}.interval.{suffix}"
    elif record_type == "sample":
        suffix = "physical_time" if uses_physical_time else "civil_time"
        field = f"{filter_name}.sample_time.{suffix}"
    elif record_type == "daily":
        field = f"{filter_name}.date"
    elif record_type == "session":
        if info.data_type == "sleep":
            suffix = "end_time" if uses_physical_time else "civil_end_time"
            field = f"{filter_name}.interval.{suffix}"
        elif info.data_type == "exercise":
            _require_civil_time(info, uses_physical_time)
            field = f"{filter_name}.interval.civil_start_time"
        else:
            suffix = "start_time" if uses_physical_time else "civil_start_time"
            field = f"{filter_name}.{suffix}"
    else:
        field = None

    if field is None:
        msg = f"Unsupported record type '{record_type}' for time filter."
        raise ValueError(msg)

    if start and end:
        return f'{field} >= "{start}" AND {field} < "{end}"'
    if start:
        return f'{field} >= "{start}"'
    if end:
        return f'{field} < "{end}"'
    return ""


def build_civil_datetime(value: str) -> dict:
    """Build a Google Health CivilDateTime object from a YYYY-MM-DD date."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError as e:
        msg = "Daily rollup dates must use YYYY-MM-DD format."
        raise ValueError(msg) from e
    return {"date": {"year": parsed.year, "month": parsed.month, "day": parsed.day}}
