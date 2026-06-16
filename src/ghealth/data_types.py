import json
from pathlib import Path

from pydantic import BaseModel


class DataTypeInfo(BaseModel):
    display_name: str
    data_type: str
    filter_name: str
    record_type: str
    supported_operations: list[str]
    required_scope_family: str
    webhook_support: bool
    true_zero_support: bool
    documentation_url: str


class DataTypeRegistry:
    def __init__(self, data_path: Path | None = None) -> None:
        if data_path is None:
            data_path = Path(__file__).parent / "data" / "data_types.json"

        with data_path.open(encoding="utf-8") as f:
            data = json.load(f)

        self._registry: dict[str, DataTypeInfo] = {k: DataTypeInfo(**v) for k, v in data.items()}

    def list_all(self) -> list[DataTypeInfo]:
        """Return all registered data types sorted by their data_type ID."""
        return sorted(self._registry.values(), key=lambda x: x.data_type)

    def get(self, data_type: str) -> DataTypeInfo | None:
        """Retrieve info for a single data type by kebab-case ID."""
        return self._registry.get(data_type)

    def describe(self, data_type: str) -> str | None:
        """Return a human-readable description string of the data type."""
        info = self.get(data_type)
        if not info:
            return None
        return (
            f"Display Name: {info.display_name}\n"
            f"Data Type ID: {info.data_type}\n"
            f"Filter Name: {info.filter_name}\n"
            f"Record Type: {info.record_type}\n"
            f"Required Scope Family: {info.required_scope_family}\n"
            f"Webhook Support: {'Yes' if info.webhook_support else 'No'}\n"
            f"True-Zero Support: {'Yes' if info.true_zero_support else 'No'}\n"
            f"Supported Operations: {', '.join(info.supported_operations)}\n"
            f"Documentation: {info.documentation_url}"
        )
