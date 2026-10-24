import pytest

from conftest import ABSENT, with_value
from item_quality import heuristics


def row(description, category="Mechanical"):
    return {"item_id": "1", "item_description": description, "category": category}


# --- vague description ---------------------------------------------------

@pytest.mark.parametrize("description", ["bearing", "  Valve ", "PART", "spare part", "relay"])
def test_generic_or_single_word_descriptions_are_vague(description):
    [finding] = heuristics.check_vague_description(row(description), 0)
    assert finding.issue_type == "vague_description"
    assert finding.source == "heuristic"
    assert finding.confidence < 1.0
    assert finding.evidence["item_description"] == description  # original, untrimmed


def test_generic_term_is_named_in_explanation():
    [finding] = heuristics.check_vague_description(row("bearing"), 0)
    assert "generic terms ('bearing')" in finding.explanation


@pytest.mark.parametrize(
    "description",
    [
        "SKF Bearing 6205 ZZ",
        "valve 2in",
        "M8 bolt",
        "Safety glasses",          # two specific words
        "gate valve",              # one specific word qualifies the generic one
        "ball bearing assembly",   # three words: just over the limit
        "N/A connector",           # placeholder text inside a real description
    ],
)
def test_specific_descriptions_are_not_vague(description):
    assert heuristics.check_vague_description(row(description), 0) == []


@pytest.mark.parametrize("description", ["N/A", "tbd", " - ", "0", "Unknown"])
def test_placeholder_descriptions_are_vague(description):
    [finding] = heuristics.check_vague_description(row(description), 0)
    assert "placeholder" in finding.explanation


@pytest.mark.parametrize("value", ABSENT)
def test_absent_description_is_left_to_incomplete_row_rule(value):
    assert heuristics.check_vague_description(with_value(row("x"), "item_description", value), 0) == []


# --- category mismatch ---------------------------------------------------

def test_bearing_in_electrical_is_a_candidate():
    [finding] = heuristics.check_category_mismatch(row("SKF Bearing 6205 ZZ", " Electrical "), 0)
    assert finding.issue_type == "category_mismatch_candidate"
    assert finding.evidence["candidate_category"] == "Mechanical"
    assert finding.evidence["matched_keywords"] == ["bearing"]
    assert finding.evidence["category"] == " Electrical "  # original, untrimmed
    assert "Review" in finding.suggested_action


@pytest.mark.parametrize("category", ["Mechanical", "mechanical", " MECHANICAL "])
def test_matching_category_ignores_case(category):
    assert heuristics.check_category_mismatch(row("ball bearing", category), 0) == []


def test_plural_keyword_matches():
    assert len(heuristics.check_category_mismatch(row("bearings, pack of 10", "Electrical"), 0)) == 1


@pytest.mark.parametrize("description", ["bearingless mount", "seal kit", "BRG 6205"])
def test_partial_words_and_unknown_terms_abstain(description):
    assert heuristics.check_category_mismatch(row(description, "Electrical"), 0) == []


def test_conflicting_keywords_abstain():
    assert heuristics.check_category_mismatch(row("valve relay assembly", "Safety"), 0) == []


@pytest.mark.parametrize("value", ABSENT)
def test_absent_category_is_not_guessed(value):
    assert heuristics.check_category_mismatch(with_value(row("bearing 6205"), "category", value), 0) == []


@pytest.mark.parametrize("value", ABSENT)
def test_absent_description_abstains(value):
    assert heuristics.check_category_mismatch(with_value(row("x", "Electrical"), "item_description", value), 0) == []
