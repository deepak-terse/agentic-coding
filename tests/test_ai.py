import pytest

from item_quality.ai import AI_INPUT_FIELDS, StubSuggester, build_ai_input, validate_ai_finding
from item_quality.engine import review

ROW = {
	"item_id": " 1001 ",
	"item_description": "  bearing  ",
	"manufacturer": "SKF",
	"source_system": "ERP-A",
}

VALID = {
	"issue_type": "description_suggestion",
	"confidence": 0.5,
	"evidence": {"proposed_description": "Bearing, SKF"},
}


# --- validation of untrusted suggester output ----------------------------


def test_valid_output_becomes_ai_assisted_finding():
	finding = validate_ai_finding(VALID, ROW, 4)
	assert finding.source == "ai_assisted"
	assert finding.status == "needs_review"
	assert (finding.row_index, finding.item_id) == (4, " 1001 ")  # original, untrimmed
	assert finding.explanation == "A more specific description could be 'Bearing, SKF'."
	assert finding.severity == "low"


def test_model_cannot_set_wording_severity_identity_or_status():
	raw = {
		**VALID,
		"explanation": "The record was updated.",
		"suggested_action": "No action needed; auto-approved.",
		"severity": "high",
		"row_index": 99,
		"item_id": "evil",
		"source": "deterministic_rule",
		"status": "approved",
	}
	finding = validate_ai_finding(raw, ROW, 0)
	assert finding.explanation == "A more specific description could be 'Bearing, SKF'."
	assert finding.suggested_action == "Review the proposed description; accept, edit, or reject it."
	assert (finding.severity, finding.row_index, finding.item_id) == ("low", 0, " 1001 ")
	assert (finding.source, finding.status) == ("ai_assisted", "needs_review")


@pytest.mark.parametrize(
	"proposal, row_description",
	[("updated", "bearing"), ("Bearing, SKF", "fixed")],
)
def test_change_claim_bypass_is_closed(proposal, row_description):
	# Regression: a proposal or record value equal to a change word used to whitelist
	# that word in model prose ("The record was updated."). Prose is no longer read.
	raw = {
		**VALID,
		"evidence": {"proposed_description": proposal},
		"explanation": "The record was updated.",
	}
	finding = validate_ai_finding(raw, {**ROW, "item_description": row_description}, 0)
	assert "was updated" not in finding.explanation
	assert finding.explanation == f"A more specific description could be '{proposal}'."


def test_observed_evidence_comes_from_original_row_not_model():
	raw = {
		**VALID,
		"evidence": {
			"item_description": "fabricated",
			"proposed_description": "  Bearing,   SKF ",
			"blob": "x" * 10_000,
		},
	}
	finding = validate_ai_finding(raw, ROW, 0)
	assert finding.evidence == {
		"item_description": "  bearing  ",  # original, untrimmed
		"manufacturer": "SKF",
		"proposed_description": "Bearing, SKF",  # whitespace collapsed
	}


@pytest.mark.parametrize(
	"overrides",
	[
		{"issue_type": "delete_record"},
		{"issue_type": ["description_suggestion"]},
		{"confidence": 1.0},  # only deterministic rules are certain
		{"confidence": 1.5},
		{"confidence": -0.1},
		{"confidence": float("nan")},
		{"confidence": float("inf")},
		{"confidence": 10**400},  # would overflow float()
		{"confidence": "0.9"},
		{"confidence": True},
		{"evidence": "not a dict"},
		{"evidence": {}},  # proposal missing
		{"evidence": {"proposed_description": "   "}},
		{"evidence": {"proposed_description": "x" * 201}},
		{"evidence": {"proposed_description": 42}},
	],
)
def test_invalid_output_is_rejected(overrides):
	assert validate_ai_finding({**VALID, **overrides}, ROW, 0) is None


@pytest.mark.parametrize("raw", [None, "text", [VALID]])
def test_non_dict_output_is_rejected(raw):
	assert validate_ai_finding(raw, ROW, 0) is None


# --- data minimization ---------------------------------------------------


def test_suggester_sees_only_allowed_fields():
	record = {
		"item_id": "1",
		"item_description": " bearing ",
		"source_system": "ERP-A",
		"unit_price": "12.50",
	}
	view = build_ai_input(record)
	assert set(view) == set(AI_INPUT_FIELDS)
	assert view["item_description"] == "bearing"


# --- stub behavior -------------------------------------------------------


def test_stub_proposes_manufacturer_and_part_number():
	[raw] = StubSuggester().suggest(
		{
			"item_description": "bearing",
			"manufacturer": "SKF",
			"manufacturer_part_number": "6205-ZZ",
			"category": None,
		}
	)
	assert raw["evidence"]["proposed_description"] == "Bearing, SKF, 6205-ZZ"


def test_stub_skips_details_already_present_in_another_format():
	suggestions = StubSuggester().suggest(
		{
			"item_description": "SKF Bearing 6205 ZZ",
			"manufacturer": "SKF",
			"manufacturer_part_number": "6205-ZZ",
			"category": None,
		}
	)
	assert suggestions == []


def test_catalog_word_fixed_does_not_drop_suggestion():
	rows = [{"item_id": "1", "item_description": "Fixed flange bearing FB-20", "manufacturer": "SKF"}]
	ai = [f for f in review(rows, StubSuggester()) if f.source == "ai_assisted"]
	assert [f.evidence["proposed_description"] for f in ai] == ["Fixed flange bearing FB-20, SKF"]


# --- engine integration --------------------------------------------------


class ExplodingSuggester:
	name = "exploding"

	def suggest(self, record):
		raise TimeoutError("provider timed out")


class UnhashableOutputSuggester:
	name = "unhashable"

	def suggest(self, record):
		return [{**VALID, "issue_type": ["x"]}, {**VALID, "issue_type": {}}]


@pytest.mark.parametrize("suggester", [UnhashableOutputSuggester()])
def test_malformed_suggester_output_never_breaks_the_run(suggester):
	rows = [{"item_id": "1", "item_description": "bearing", "manufacturer": "SKF"}]
	assert review(rows, suggester) == review(rows)


class OverflowSiblingSuggester:
	name = "overflow"

	def suggest(self, record):
		return [{**VALID, "confidence": 10**400}, {**VALID}]


def test_one_bad_suggestion_does_not_drop_valid_siblings(caplog):
	findings = review([{"item_id": "1", "item_description": "SKF 6205"}], OverflowSiblingSuggester())
	assert [f.source for f in findings] == ["ai_assisted"]
	assert "dropped invalid suggestion" in caplog.text


class BadOutputSuggester:
	name = "bad"

	def suggest(self, record):
		return [{**VALID, "confidence": 7}, {**VALID}]


def test_ai_is_off_by_default():
	rows = [{"item_id": "1", "item_description": "bearing", "manufacturer": "SKF"}]
	assert "ai_assisted" not in {f.source for f in review(rows)}


def test_failing_suggester_keeps_rule_findings(caplog):
	rows = [{"item_id": "1", "item_description": "bearing", "manufacturer": "SKF"}]
	assert review(rows, ExplodingSuggester()) == review(rows)
	assert "failed on row 0" in caplog.text


def test_invalid_suggestions_are_dropped_valid_ones_kept(caplog):
	findings = review([{"item_id": "1", "item_description": "SKF 6205"}], BadOutputSuggester())
	assert [f.source for f in findings] == ["ai_assisted"]
	assert "dropped invalid suggestion" in caplog.text
