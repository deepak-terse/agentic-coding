import pytest

from conftest import ABSENT, MISSING, with_value
from item_quality import rules
from item_quality.models import Finding


def issue_types(findings: list[Finding]) -> list[str]:
	return [f.issue_type for f in findings]


# --- malformed row -------------------------------------------------------


@pytest.mark.parametrize("row", [["a", "b"], "1001", 42, None])
def test_non_object_row_is_malformed(row):
	[finding] = rules.check_malformed_row(row, 3)
	assert finding.issue_type == "malformed_row"
	assert finding.row_index == 3
	assert finding.item_id is None


def test_object_row_is_not_malformed(complete_row):
	assert rules.check_malformed_row(complete_row, 0) == []


# --- malformed fields ----------------------------------------------------


def test_non_string_field_values_are_flagged_not_coerced(complete_row):
	row = {**complete_row, "item_id": 1002, "manufacturer_part_number": ["6205"]}
	[finding] = rules.check_malformed_fields(row, 0)
	assert finding.issue_type == "malformed_field"
	assert finding.evidence == {"item_id": 1002, "manufacturer_part_number": ["6205"]}
	assert finding.item_id is None  # non-string id is not stringified


def test_evidence_does_not_share_objects_with_input(complete_row):
	row = {**complete_row, "manufacturer_part_number": ["6205"]}
	[finding] = rules.check_malformed_fields(row, 0)
	finding.evidence["manufacturer_part_number"].append("changed")
	assert row["manufacturer_part_number"] == ["6205"]


@pytest.mark.parametrize("value", ABSENT)
def test_absent_values_are_not_malformed(complete_row, value):
	assert rules.check_malformed_fields(with_value(complete_row, "category", value), 0) == []


def test_unknown_fields_are_ignored(complete_row):
	assert rules.check_malformed_fields({**complete_row, "extra_field": 123}, 0) == []


# --- required fields -----------------------------------------------------


@pytest.mark.parametrize("field", ["item_id", "item_description"])
@pytest.mark.parametrize("value", ABSENT)
def test_absent_required_field_is_incomplete(complete_row, field, value):
	[finding] = rules.check_required_fields(with_value(complete_row, field, value), 0)
	assert finding.issue_type == "incomplete_row"
	assert finding.severity == "high"
	assert finding.evidence["missing_fields"] == [field]


@pytest.mark.parametrize(
	"value, observed, wording",
	[
		(MISSING, {}, "not provided"),
		(None, {"item_description": None}, "null"),
		("", {"item_description": ""}, "empty"),
		("  ", {"item_description": "  "}, "whitespace only"),
	],
)
def test_incomplete_row_shows_what_was_observed(complete_row, value, observed, wording):
	[finding] = rules.check_required_fields(with_value(complete_row, "item_description", value), 0)
	assert finding.evidence["observed"] == observed
	assert f"item_description ({wording})" in finding.explanation


def test_missing_keys_are_incomplete():
	[finding] = rules.check_required_fields({"manufacturer": "SKF"}, 5)
	assert finding.evidence["missing_fields"] == ["item_id", "item_description"]
	assert finding.row_index == 5


def test_numeric_item_id_is_malformed_not_missing(complete_row):
	# near miss: present but wrong type is reported by check_malformed_fields only
	assert rules.check_required_fields({**complete_row, "item_id": 1002}, 0) == []


def test_complete_row_has_required_fields(complete_row):
	assert rules.check_required_fields(complete_row, 0) == []


# --- missing part number -------------------------------------------------


@pytest.mark.parametrize("value", ABSENT)
def test_manufacturer_without_part_number(complete_row, value):
	row = with_value(complete_row, "manufacturer_part_number", value)
	[finding] = rules.check_missing_part_number(row, 0)
	assert finding.issue_type == "missing_part_number"
	assert finding.source == "deterministic_rule"
	assert finding.confidence == 1.0
	assert "SKF" in finding.explanation


@pytest.mark.parametrize("value", ABSENT)
def test_no_manufacturer_means_no_part_number_finding(complete_row, value):
	row = with_value({**complete_row, "manufacturer_part_number": ""}, "manufacturer", value)
	assert rules.check_missing_part_number(row, 0) == []


def test_part_number_present(complete_row):
	assert rules.check_missing_part_number(complete_row, 0) == []


def test_non_string_part_number_is_left_to_malformed_check(complete_row):
	row = {**complete_row, "manufacturer_part_number": 6205}
	assert rules.check_missing_part_number(row, 0) == []


# --- unit of measure -----------------------------------------------------


@pytest.mark.parametrize("unit", ["EA", "ea", " kg ", "Box"])
def test_supported_units_ignore_case_and_whitespace(complete_row, unit):
	assert rules.check_unit_of_measure({**complete_row, "unit_of_measure": unit}, 0) == []


@pytest.mark.parametrize("unit", ["EACH", "PCS", "??", "E A"])
def test_unsupported_unit(complete_row, unit):
	[finding] = rules.check_unit_of_measure({**complete_row, "unit_of_measure": unit}, 0)
	assert finding.issue_type == "unsupported_unit_of_measure"
	assert finding.evidence == {"unit_of_measure": unit}


@pytest.mark.parametrize("value", ABSENT)
def test_absent_unit_is_not_flagged_as_unsupported(complete_row, value):
	assert rules.check_unit_of_measure(with_value(complete_row, "unit_of_measure", value), 0) == []
