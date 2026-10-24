"""Read-only helpers for record fields. Nothing here modifies a record."""

from typing import Any

RECOGNIZED_FIELDS = (
	"item_id",
	"item_description",
	"manufacturer",
	"manufacturer_part_number",
	"category",
	"unit_of_measure",
	"source_system",
)


def is_blank(row: dict[str, Any], name: str) -> bool:
	"""True when the field is missing, None, or an empty/whitespace-only string."""
	value = row.get(name)
	return value is None or (isinstance(value, str) and not value.strip())


def text(row: dict[str, Any], name: str) -> str | None:
	"""Trimmed string value for comparison, or None if blank or not a string.

	Non-string values are reported by the malformed-field rule rather than coerced.
	"""
	value = row.get(name)
	if isinstance(value, str) and value.strip():
		return value.strip()
	return None


def identity(row: dict[str, Any], name: str) -> str | None:
	"""Exact original string for identifiers in output, or None if blank or not a string.

	Unlike text(), nothing is trimmed: " 1001 " stays " 1001 " so downstream matching
	sees what the source system sent. Use text() for comparisons only.
	"""
	value = row.get(name)
	return value if isinstance(value, str) and value.strip() else None


def malformed_fields(row: dict[str, Any]) -> list[str]:
	"""Recognized fields holding something other than a string or null."""
	return [
		name
		for name in RECOGNIZED_FIELDS
		if name in row and row[name] is not None and not isinstance(row[name], str)
	]
