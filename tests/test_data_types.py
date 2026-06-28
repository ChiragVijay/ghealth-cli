from ghealth.data_types import DataTypeRegistry


def test_registry_load() -> None:
    registry = DataTypeRegistry()
    all_types = registry.list_all()
    # There should be exactly 41 types registered
    assert len(all_types) == 41


def test_registry_get_valid() -> None:
    registry = DataTypeRegistry()
    steps_info = registry.get("steps")
    assert steps_info is not None
    assert steps_info.display_name == "Steps"
    assert steps_info.data_type == "steps"
    assert steps_info.filter_name == "steps"
    assert steps_info.record_type == "interval"
    assert steps_info.required_scope_family == "activity"
    assert steps_info.webhook_support is True
    assert steps_info.true_zero_support is True


def test_registry_uses_documented_record_shapes_for_shortcuts() -> None:
    registry = DataTypeRegistry()

    heart_rate = registry.get("heart-rate")
    hydration = registry.get("hydration-log")
    nutrition = registry.get("nutrition-log")

    assert heart_rate is not None
    assert hydration is not None
    assert nutrition is not None
    assert heart_rate.record_type == "sample"
    assert hydration.record_type == "interval"
    assert nutrition.record_type == "interval"


def test_registry_get_invalid() -> None:
    registry = DataTypeRegistry()
    assert registry.get("non-existent") is None


def test_registry_describe() -> None:
    registry = DataTypeRegistry()
    desc = registry.describe("steps")
    assert desc is not None
    assert "Display Name: Steps" in desc
    assert "Data Type ID: steps" in desc

    assert registry.describe("non-existent") is None
