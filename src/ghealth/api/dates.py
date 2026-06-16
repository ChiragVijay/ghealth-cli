from datetime import date

from ghealth.data_types import DataTypeInfo


def build_data_point_time_filter(
    info: DataTypeInfo,
    *,
    start: str | None = None,
    end: str | None = None,
) -> str:
    """Build a simple AIP-160 time-range filter for a data type."""
    filter_name = info.filter_name
    record_type = info.record_type

    field_map = {
        "interval": f"{filter_name}.interval.start_time",
        "sample": f"{filter_name}.sample_time.physical_time",
        "daily": f"{filter_name}.date",
        "session": f"{filter_name}.interval.start_time",
    }
    field = field_map.get(record_type)
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
