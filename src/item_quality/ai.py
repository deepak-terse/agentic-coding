"""AI-assisted suggestion layer.

A Suggester receives a minimal view of one record and returns raw suggestion dicts,
the way an LLM response would arrive. Raw output is untrusted: it only becomes a
Finding after validate_ai_finding() accepts it. The engine owns row_index, item_id,
source, status, and the observed values in evidence, so a model cannot set them.

StubSuggester is a deterministic stand-in; it makes no network calls.
"""

import math
import re
from collections.abc import Mapping
from typing import Any, Protocol

from item_quality.fields import text
from item_quality.models import Finding, Severity, Source

# Only these fields are ever passed to a suggester (data minimization).
AI_INPUT_FIELDS = ("item_description", "manufacturer", "manufacturer_part_number", "category")

# Issue types a suggester may raise, and the proposal keys each may put in evidence.
ALLOWED_AI_ISSUES: dict[str, tuple[str, ...]] = {
	"description_suggestion": ("proposed_description",),
}

# AI suggestions are never certain and never top priority.
MAX_AI_CONFIDENCE = 0.9
ALLOWED_AI_SEVERITIES = frozenset({Severity.LOW, Severity.MEDIUM})

MAX_TEXT_LENGTH = 500

# Words that claim a change was made. Deliberately broad: a false reject only drops
# a suggestion, while a false accept tells a steward something changed when it didn't.
# Record values and proposals are removed before matching, so catalog text such as
# "Fixed flange bearing" in a description is not mistaken for a claim.
CHANGE_CLAIM = re.compile(
	r"\b(?:fixed|corrected|updated|changed|replaced|modified|overwritten|applied"
	r"|approved|auto[- ]?approved|now reads)\b",
	re.IGNORECASE,
)


class Suggester(Protocol):
	name: str

	def suggest(self, record: Mapping[str, str | None]) -> list[dict[str, Any]]: ...


def build_ai_input(row: dict[str, Any]) -> dict[str, str | None]:
	"""The only view of a record a suggester sees: trimmed text for a few fields."""
	return {name: text(row, name) for name in AI_INPUT_FIELDS}


def claims_change(value: str, known_values: tuple[str, ...] = ()) -> bool:
	"""True if the text claims a change, ignoring exact record values and proposals."""
	for known in sorted(known_values, key=len, reverse=True):
		value = re.sub(re.escape(known), " ", value, flags=re.IGNORECASE)
	return CHANGE_CLAIM.search(value) is not None


def _bounded_text(value: Any) -> str | None:
	if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT_LENGTH:
		return None
	return value.strip()


def _review_text(value: Any, known_values: tuple[str, ...]) -> str | None:
	cleaned = _bounded_text(value)
	return None if cleaned is None or claims_change(cleaned, known_values) else cleaned


def validate_ai_finding(raw: Any, row: dict[str, Any], row_index: int) -> Finding | None:
	"""Turn raw suggester output into a Finding, or return None if it is not acceptable.

	Only allowlisted proposal keys are taken from the model's evidence. Observed values
	are copied from the original row, so evidence always shows what was uploaded.
	"""
	if not isinstance(raw, dict):
		return None
	issue_type, severity = raw.get("issue_type"), raw.get("severity")
	# Type checks first: unhashable values would make the lookups below raise.
	if not isinstance(issue_type, str) or issue_type not in ALLOWED_AI_ISSUES:
		return None
	if not isinstance(severity, str) or severity not in ALLOWED_AI_SEVERITIES:
		return None
	confidence = raw.get("confidence")
	if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
		return None
	if not (math.isfinite(confidence) and 0.0 <= confidence <= MAX_AI_CONFIDENCE):
		return None
	raw_evidence = raw.get("evidence")
	if not isinstance(raw_evidence, dict):
		return None
	proposals = {}
	for key in ALLOWED_AI_ISSUES[issue_type]:
		value = _bounded_text(raw_evidence.get(key))
		if value is None:
			return None
		proposals[key] = value
	observed = {name: row[name] for name in AI_INPUT_FIELDS if name in row}
	known = tuple(
		v.strip() for v in [*observed.values(), *proposals.values()] if isinstance(v, str) and v.strip()
	)
	explanation = _review_text(raw.get("explanation"), known)
	action = _review_text(raw.get("suggested_action"), known)
	if explanation is None or action is None:
		return None
	return Finding(
		row_index=row_index,
		item_id=text(row, "item_id"),
		issue_type=issue_type,
		severity=Severity(severity),
		confidence=float(confidence),
		explanation=explanation,
		suggested_action=action,
		source=Source.AI_ASSISTED,
		evidence={**observed, **proposals},
	)


class StubSuggester:
	"""Simulates an LLM proposing a standardized description. Deterministic, offline."""

	name = "stub-description-v1"

	def suggest(self, record: Mapping[str, str | None]) -> list[dict[str, Any]]:
		description = record.get("item_description")
		if description is None:
			return []
		proposed = self._standardize(
			description, record.get("manufacturer"), record.get("manufacturer_part_number")
		)
		if proposed.casefold() == " ".join(description.split()).casefold():
			return []
		return [
			{
				"issue_type": "description_suggestion",
				"severity": "low",
				"confidence": 0.5,
				"explanation": f"A more specific description could be '{proposed}'.",
				"suggested_action": "Review the proposed description; accept, edit, or reject it.",
				"evidence": {"item_description": description, "proposed_description": proposed},
			}
		]

	@staticmethod
	def _standardize(description: str, manufacturer: str | None, part_number: str | None) -> str:
		words = " ".join(description.split())
		proposed = words[:1].upper() + words[1:]
		present = proposed.casefold()
		compact = re.sub(r"[^a-z0-9]", "", present)
		extras = [
			value
			for value in (manufacturer, part_number)
			if value and re.sub(r"[^a-z0-9]", "", value.casefold()) not in compact
		]
		return ", ".join([proposed, *extras])
