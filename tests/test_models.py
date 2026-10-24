import math

import pytest

from item_quality.models import Finding


def make(**overrides):
	base = {
		"row_index": 0,
		"item_id": "1",
		"issue_type": "x",
		"severity": "low",
		"confidence": 0.5,
		"explanation": "e",
		"suggested_action": "a",
		"source": "heuristic",
	}
	return Finding(**{**base, **overrides})


@pytest.mark.parametrize("confidence", [-0.1, 1.01, math.nan, math.inf, True, "0.5", None])
def test_confidence_must_be_finite_and_bounded(confidence):
	with pytest.raises(ValueError):
		make(confidence=confidence)


@pytest.mark.parametrize("field, value", [("severity", "urgent"), ("source", "magic")])
def test_unknown_enum_values_rejected(field, value):
	with pytest.raises(ValueError):
		make(**{field: value})


def test_to_dict_defaults_to_needs_review():
	data = make().to_dict()
	assert data["status"] == "needs_review"
	assert data["severity"] == "low"
	assert data["source"] == "heuristic"


def test_status_cannot_be_set_by_a_check():
	with pytest.raises(TypeError):
		make(status="approved")
