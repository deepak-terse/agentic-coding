"""Deterministic checks: exact conditions, confidence 1.0."""

from typing import Any

from item_quality.fields import identity, is_blank, malformed_fields, text
from item_quality.models import Finding, Severity, Source

REQUIRED_FIELDS = ("item_id", "item_description")

# Demo assumption: a small allowlist, not an enterprise UoM standard.
SUPPORTED_UNITS = frozenset({"EA", "BOX", "PK", "SET", "KG", "G", "LB", "M", "CM", "FT", "L", "ML"})


def _rule_finding(
	row: Any,
	index: int,
	issue_type: str,
	severity: Severity,
	explanation: str,
	suggested_action: str,
	evidence: dict[str, Any],
) -> list[Finding]:
	"""A rule fires on an exact condition, so source and confidence are fixed here."""
	return [
		Finding(
			row_index=index,
			item_id=identity(row, "item_id") if isinstance(row, dict) else None,
			issue_type=issue_type,
			severity=severity,
			confidence=1.0,
			explanation=explanation,
			suggested_action=suggested_action,
			source=Source.DETERMINISTIC_RULE,
			evidence=evidence,
		)
	]


def check_malformed_row(row: Any, index: int) -> list[Finding]:
	"""Rows that are not JSON objects cannot be checked further."""
	if isinstance(row, dict):
		return []
	return _rule_finding(
		row,
		index,
		"malformed_row",
		Severity.HIGH,
		f"Row is a {type(row).__name__}, not a record object.",
		"Check the export from the source system; this row was not evaluated.",
		{"row": row},
	)


def check_malformed_fields(row: dict[str, Any], index: int) -> list[Finding]:
	bad = malformed_fields(row)
	if not bad:
		return []
	found = ", ".join(f"{name} ({type(row[name]).__name__})" for name in bad)
	return _rule_finding(
		row,
		index,
		"malformed_field",
		Severity.MEDIUM,
		f"Expected text values but found: {found}.",
		"Review the source mapping for these fields before approval.",
		{name: row[name] for name in bad},
	)


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
	described = ", ".join(_describe_absent(row, name) for name in missing)
	return _rule_finding(
		row,
		index,
		"incomplete_row",
		Severity.HIGH,
		f"Required field(s) missing or blank: {described}.",
		"Request the missing values from the source owner.",
		# Keys present in the row keep their original value; absent keys are omitted.
		{"missing_fields": missing, "observed": {name: row[name] for name in missing if name in row}},
	)


def check_missing_part_number(row: dict[str, Any], index: int) -> list[Finding]:
	manufacturer = text(row, "manufacturer")
	if manufacturer is None or not is_blank(row, "manufacturer_part_number"):
		return []
	return _rule_finding(
		row,
		index,
		"missing_part_number",
		Severity.MEDIUM,
		f"Manufacturer '{manufacturer}' is present but manufacturer part number is blank.",
		"Request the manufacturer part number from the source owner.",
		{
			"manufacturer": row.get("manufacturer"),
			"manufacturer_part_number": row.get("manufacturer_part_number"),
		},
	)


def check_unit_of_measure(row: dict[str, Any], index: int) -> list[Finding]:
	unit = text(row, "unit_of_measure")
	if unit is None or unit.upper() in SUPPORTED_UNITS:
		return []
	return _rule_finding(
		row,
		index,
		"unsupported_unit_of_measure",
		Severity.MEDIUM,
		f"Unit of measure '{unit}' is not in the supported list.",
		"Confirm the intended unit with the source owner before approval.",
		{"unit_of_measure": row.get("unit_of_measure")},
	)
