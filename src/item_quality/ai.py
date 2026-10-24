"""AI-assisted suggestion layer.

A Suggester receives a minimal view of one record and returns raw suggestion dicts,
the way an LLM response would arrive. Raw output is untrusted: it only becomes a
Finding after validate_ai_finding() accepts it.

The model contributes data only: an issue type, a proposed value, and a confidence.
Everything a reviewer reads as a statement (explanation, suggested action, severity)
comes from application-owned templates, as do row_index, item_id, source, status, and
the observed values in evidence. A model therefore cannot claim a change was made.

StubSuggester is a deterministic stand-in; it makes no network calls.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from item_quality.fields import identity, text
from item_quality.models import Finding, Severity, Source

# Only these fields are ever passed to a suggester (data minimization).
AI_INPUT_FIELDS = ("item_description", "manufacturer", "manufacturer_part_number", "category")

# AI suggestions are never certain.
MAX_AI_CONFIDENCE = 0.9

MAX_PROPOSAL_LENGTH = 200


@dataclass(frozen=True)
class AiIssue:
	"""What a suggester may propose for one issue type, and how it is presented."""

	proposal_key: str
	severity: Severity
	explanation: str  # formatted with {proposal}
	suggested_action: str


# Issue types a suggester may raise. Wording is owned here, never by the model.
AI_ISSUES: dict[str, AiIssue] = {
	"description_suggestion": AiIssue(
		proposal_key="proposed_description",
		severity=Severity.LOW,
		explanation="A more specific description could be '{proposal}'.",
		suggested_action="Review the proposed description; accept, edit, or reject it.",
	),
}


class Suggester(Protocol):
	name: str

	def suggest(self, record: Mapping[str, str | None]) -> list[dict[str, Any]]: ...


def build_ai_input(row: dict[str, Any]) -> dict[str, str | None]:
	"""The only view of a record a suggester sees: trimmed text for a few fields."""
	return {name: text(row, name) for name in AI_INPUT_FIELDS}


def _valid_confidence(value: Any) -> bool:
	# Range check before any float conversion: huge ints compare fine but overflow
	# float(), and NaN fails every comparison.
	if isinstance(value, bool) or not isinstance(value, (int, float)):
		return False
	return 0.0 <= value <= MAX_AI_CONFIDENCE


def _proposal(value: Any) -> str | None:
	if not isinstance(value, str) or not value.strip() or len(value) > MAX_PROPOSAL_LENGTH:
		return None
	return " ".join(value.split())


def validate_ai_finding(raw: Any, row: dict[str, Any], row_index: int) -> Finding | None:
	"""Turn raw suggester output into a Finding, or return None if it is not acceptable.

	Only the issue type, the allowlisted proposal, and the confidence are read from the
	model. Any explanation, action, severity, or identity fields it returns are ignored.
	"""
	if not isinstance(raw, dict):
		return None
	issue_type = raw.get("issue_type")
	# Type check first: an unhashable value would make the lookup raise.
	if not isinstance(issue_type, str) or issue_type not in AI_ISSUES:
		return None
	issue = AI_ISSUES[issue_type]
	confidence = raw.get("confidence")
	if not _valid_confidence(confidence):
		return None
	raw_evidence = raw.get("evidence")
	if not isinstance(raw_evidence, dict):
		return None
	proposal = _proposal(raw_evidence.get(issue.proposal_key))
	if proposal is None:
		return None
	observed = {name: row[name] for name in AI_INPUT_FIELDS if name in row}
	return Finding(
		row_index=row_index,
		item_id=identity(row, "item_id"),
		issue_type=issue_type,
		severity=issue.severity,
		confidence=float(confidence),
		explanation=issue.explanation.format(proposal=proposal),
		suggested_action=issue.suggested_action,
		source=Source.AI_ASSISTED,
		evidence={**observed, issue.proposal_key: proposal},
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
				"confidence": 0.5,
				"evidence": {"proposed_description": proposed},
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
