import copy

import pytest

from item_quality.ai import StubSuggester
from item_quality.engine import review

WITH_AND_WITHOUT_AI = pytest.mark.parametrize(
	"suggester", [None, StubSuggester()], ids=["rules", "with-ai"]
)


def test_empty_input_has_no_findings():
	assert review([]) == []


def test_complete_row_has_no_findings(complete_row):
	assert review([complete_row]) == []


def test_bad_rows_do_not_stop_valid_rows(complete_row):
	findings = review(["not a record", {**complete_row, "manufacturer_part_number": ""}])
	assert [(f.row_index, f.issue_type) for f in findings] == [
		(0, "malformed_row"),
		(1, "missing_part_number"),
	]


def test_multiple_findings_per_row_in_stable_order():
	row = {"item_id": "", "manufacturer": "SKF", "unit_of_measure": "PCS", "category": 7}
	assert [f.issue_type for f in review([row])] == [
		"malformed_field",
		"incomplete_row",
		"missing_part_number",
		"unsupported_unit_of_measure",
	]


def test_duplicate_ids_are_located_by_row_index(complete_row):
	rows = [{**complete_row, "unit_of_measure": "PCS"}] * 2
	assert [f.row_index for f in review(rows)] == [0, 1]


@WITH_AND_WITHOUT_AI
def test_input_is_not_mutated(complete_row, suggester):
	records = [
		{**complete_row, "item_id": "  1001  ", "manufacturer_part_number": "   "},
		{"item_id": 5, "unit_of_measure": "pcs", "manufacturer_part_number": ["a"]},
		{"item_id": "9", "item_description": " valve ", "manufacturer": "Emerson"},
		["junk"],
	]
	snapshot = copy.deepcopy(records)
	findings = review(records, suggester)
	for finding in findings:  # consumers editing evidence must not reach the input
		for value in finding.evidence.values():
			if isinstance(value, (list, dict)):
				value.clear()
	assert records == snapshot


@WITH_AND_WITHOUT_AI
def test_output_never_claims_a_correction(complete_row, suggester):
	rows = [
		{},
		"junk",
		{**complete_row, "manufacturer_part_number": "", "unit_of_measure": "X", "item_id": 1},
		{"item_id": "2", "item_description": "valve", "manufacturer": "Emerson"},
	]
	findings = review(rows, suggester)
	assert suggester is None or "ai_assisted" in {f.source for f in findings}
	text = " ".join(f.explanation + " " + f.suggested_action for f in findings).lower()
	for banned in ("fixed", "corrected", "auto-approved"):
		assert banned not in text


def test_item_id_is_reported_exactly_as_uploaded_by_every_source():
	row = {
		"item_id": " 1001 ",
		"item_description": "bearing",
		"manufacturer": "SKF",
		"category": "Electrical",
	}
	findings = review([row], StubSuggester())
	assert {f.source for f in findings} == {"deterministic_rule", "heuristic", "ai_assisted"}
	assert {f.item_id for f in findings} == {" 1001 "}
