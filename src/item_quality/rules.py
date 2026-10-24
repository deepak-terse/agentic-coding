"""Deterministic checks: exact conditions, confidence 1.0."""

from typing import Any

from item_quality.fields import is_blank, malformed_fields, text
from item_quality.models import Finding, Severity, Source

REQUIRED_FIELDS = ("item_id", "item_description")

# Demo assumption: a small allowlist, not an enterprise UoM standard.
SUPPORTED_UNITS = frozenset({"EA", "BOX", "PK", "SET", "KG", "G", "LB", "M", "CM", "FT", "L", "ML"})


def check_malformed_row(row: Any, index: int) -> list[Finding]:
	"""Rows that are not JSON objects cannot be checked further."""
	if isinstance(row, dict):
		return []
	return [
		Finding(
			row_index=index,
			item_id=None,
			issue_type="malformed_row",
			severity=Severity.HIGH,
			confidence=1.0,
			explanation=f"Row is a {type(row).__name__}, not a record object.",
			suggested_action="Check the export from the source system; this row was not evaluated.",
			source=Source.DETERMINISTIC_RULE,
			evidence={"row": row},
		)
	]


def check_malformed_fields(row: dict[str, Any], index: int) -> list[Finding]:
	bad = malformed_fields(row)
	if not bad:
			return []
	return [
		Finding(
			row_index=index,
			item_id=text(row, "item_id"),
			issue_type="malformed_field",
			severity=Severity.MEDIUM,
			confidence=1.0,
			explanation="Expected text values but found: "
			+ ", ".join(f"{name} ({type(row[name]).__name__})" for name in bad)
			+ ".",
			suggested_action="Review the source mapping for these fields before approval.",
			source=Source.DETERMINISTIC_RULE,
			evidence={name: row[name] for name in bad},
		)
	]


def _describe_absent(row: dict[str, Any], name: str) -> str:
	if name not in row:
			return f"{name} (not provided)"
	if row[name] is None:
			return f"{name} (null)"
	return f"{name} ({'empty' if row[name] == '' else 'whitespace only'})"


def check_required_fields(row: dict[str, Any], index: int) -> list[Finding]:
	missing = [name for name in REQUIRED_FIELDS if is_blank(row, name)]
	if not missing:
		return []
	return [
		Finding(
			row_index=index,
			item_id=text(row, "item_id"),
			issue_type="incomplete_row",
			severity=Severity.HIGH,
			confidence=1.0,
			explanation="Required field(s) missing or blank: "
			+ ", ".join(_describe_absent(row, name) for name in missing)
			+ ".",
			suggested_action="Request the missing values from the source owner.",
			source=Source.DETERMINISTIC_RULE,
			# Keys present in the row keep their original value; absent keys are omitted.
			evidence={
				"missing_fields": missing,
				"observed": {name: row[name] for name in missing if name in row},
			},
		)
	]


def check_missing_part_number(row: dict[str, Any], index: int) -> list[Finding]:
	manufacturer = text(row, "manufacturer")
	if manufacturer is None or not is_blank(row, "manufacturer_part_number"):
		return []
	return [
		Finding(
			row_index=index,
			item_id=text(row, "item_id"),
			issue_type="missing_part_number",
			severity=Severity.MEDIUM,
			confidence=1.0,
			explanation=f"Manufacturer '{manufacturer}' is present but manufacturer part number is blank.",
			suggested_action="Request the manufacturer part number from the source owner.",
			source=Source.DETERMINISTIC_RULE,
			evidence={
				"manufacturer": row.get("manufacturer"),
				"manufacturer_part_number": row.get("manufacturer_part_number"),
			},
		)
	]


def check_unit_of_measure(row: dict[str, Any], index: int) -> list[Finding]:
	unit = text(row, "unit_of_measure")
	if unit is None or unit.upper() in SUPPORTED_UNITS:
		return []
	return [
		Finding(
			row_index=index,
			item_id=text(row, "item_id"),
			issue_type="unsupported_unit_of_measure",
			severity=Severity.MEDIUM,
			confidence=1.0,
			explanation=f"Unit of measure '{unit}' is not in the supported list.",
			suggested_action="Confirm the intended unit with the source owner before approval.",
			source=Source.DETERMINISTIC_RULE,
			evidence={"unit_of_measure": row.get("unit_of_measure")},
		)
	]
