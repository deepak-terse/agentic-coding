"""Heuristic checks: keyword and length signals that need human judgment."""

import re
from typing import Any

from item_quality.fields import identity, text
from item_quality.models import Finding, Severity, Source

HEURISTIC_CONFIDENCE = 0.7

# Demo assumption: words that say what an item is, but not which one.
GENERIC_TERMS = frozenset(
	{"bearing", "valve", "part", "item", "misc", "spare", "tool", "kit", "assembly"}
)
MAX_VAGUE_WORDS = 2

# Demo assumption: common "no value" markers that slip past blank checks.
PLACEHOLDERS = frozenset(
	{"n/a", "na", "tbd", "tba", "none", "unknown", "-", "--", ".", "?", "0", "x"}
)

# Demo assumption: a tiny keyword -> category map, not a real taxonomy.
KEYWORD_CATEGORIES = {
	"bearing": "Mechanical",
	"gasket": "Mechanical",
	"valve": "Mechanical",
	"cable": "Electrical",
	"fuse": "Electrical",
	"relay": "Electrical",
	"resistor": "Electrical",
	"glove": "Safety",
	"helmet": "Safety",
}

WORD = re.compile(r"[a-z0-9]+")


def _words(description: str) -> list[str]:
	return WORD.findall(description.casefold())


def _heuristic_finding(
	row: dict[str, Any],
	index: int,
	issue_type: str,
	explanation: str,
	suggested_action: str,
	evidence: dict[str, Any],
) -> list[Finding]:
	"""Heuristics are review hints: always low severity and below-certain confidence."""
	return [
		Finding(
			row_index=index,
			item_id=identity(row, "item_id"),
			issue_type=issue_type,
			severity=Severity.LOW,
			confidence=HEURISTIC_CONFIDENCE,
			explanation=explanation,
			suggested_action=suggested_action,
			source=Source.HEURISTIC,
			evidence=evidence,
		)
	]


def _vague(row: dict[str, Any], index: int, description: str, reason: str) -> list[Finding]:
	return _heuristic_finding(
		row,
		index,
		"vague_description",
		f"Description '{description}' {reason}.",
		"Review the description and consider adding type, size, or part details.",
		{"item_description": row.get("item_description"), "word_count": len(_words(description))},
	)


def check_vague_description(row: dict[str, Any], index: int) -> list[Finding]:
	"""Short descriptions with no size, model, or spec detail are hard to match or buy."""
	description = text(row, "item_description")
	if description is None:
		return []  # absence is reported by the incomplete-row rule
	if description.casefold() in PLACEHOLDERS:
		return _vague(row, index, description, "looks like a placeholder, not a description")
	words = _words(description)
	has_attributes = any(ch.isdigit() for ch in description)
	if has_attributes or not words or len(words) > MAX_VAGUE_WORDS:
		return []
	# Two specific words ("Safety glasses") are usually enough; flag only all-generic
	# descriptions or a lone word.
	if all(w in GENERIC_TERMS for w in words):
		reason = "contains only generic terms (" + ", ".join(f"'{w}'" for w in words) + ")"
	elif len(words) == 1:
		reason = "is a single word with no size, model, or specification detail"
	else:
		return []
	return _vague(row, index, description, reason)


def expected_categories(description: str) -> dict[str, str]:
	"""Keywords found in the description (whole word, simple plural) and their categories."""
	words = set(_words(description))
	return {
		keyword: category
		for keyword, category in KEYWORD_CATEGORIES.items()
		if keyword in words or f"{keyword}s" in words
	}


def check_category_mismatch(row: dict[str, Any], index: int) -> list[Finding]:
	description = text(row, "item_description")
	category = text(row, "category")
	if description is None or category is None:
		return []  # nothing to compare; no guessing a missing category
	matches = expected_categories(description)
	expected = set(matches.values())
	# Abstain when no keyword matches or keywords disagree with each other.
	if len(expected) != 1:
		return []
	[expected_category] = expected
	if category.casefold() == expected_category.casefold():
		return []
	keywords = sorted(matches)
	return _heuristic_finding(
		row,
		index,
		"category_mismatch_candidate",
		f"Description mentions '{', '.join(keywords)}', which usually belongs to "
		f"{expected_category}, but category is '{category}'.",
		"Review the category assignment before approval.",
		{
			"item_description": row.get("item_description"),
			"category": row.get("category"),
			"matched_keywords": keywords,
			"candidate_category": expected_category,
		},
	)
