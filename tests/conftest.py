import pytest


@pytest.fixture
def complete_row():
    """A record that should produce no findings."""
    return {
        "item_id": "1002",
        "item_description": "SKF Bearing 6205 ZZ",
        "manufacturer": "SKF",
        "manufacturer_part_number": "6205-ZZ",
        "category": "Mechanical",
        "unit_of_measure": "EA",
        "source_system": "ERP-B",
    }


MISSING = object()  # sentinel: remove the key entirely
ABSENT = [None, "", "   ", "\t", MISSING]


def with_value(row: dict, key: str, value) -> dict:
    """Copy of row with key set to value, or removed when value is MISSING."""
    updated = {k: v for k, v in row.items() if k != key}
    if value is not MISSING:
        updated[key] = value
    return updated
