"""Runs every check over a list of records and returns findings in stable order."""

import logging
from collections.abc import Callable
from typing import Any

from item_quality import heuristics, rules
from item_quality.ai import Suggester, build_ai_input, validate_ai_finding
from item_quality.models import Finding

log = logging.getLogger(__name__)

Check = Callable[[dict[str, Any], int], list[Finding]]

# Order here is the order findings appear within a row.
CHECKS: tuple[Check, ...] = (
	rules.check_malformed_fields,
	rules.check_required_fields,
	rules.check_missing_part_number,
	rules.check_unit_of_measure,
	heuristics.check_vague_description,
	heuristics.check_category_mismatch,
)


def review(records: list[Any], suggester: Suggester | None = None) -> list[Finding]:
	"""Return review candidates for each record. Records are never modified.

	AI-assisted suggestions are opt-in. If the suggester fails or returns invalid
	output, that output is dropped and the rule and heuristic findings still return.
	"""
	findings: list[Finding] = []
	for index, row in enumerate(records):
			shape = rules.check_malformed_row(row, index)
			if shape:
					findings.extend(shape)
					continue
			for check in CHECKS:
					findings.extend(check(row, index))
			if suggester is not None:
					findings.extend(_ai_findings(suggester, row, index))
	return findings


def _ai_findings(suggester: Suggester, row: dict[str, Any], index: int) -> list[Finding]:
	try:
		raw_items = suggester.suggest(build_ai_input(row))
		if not isinstance(raw_items, list):
			raise TypeError(f"expected a list, got {type(raw_items).__name__}")
		validated = [validate_ai_finding(raw, row, index) for raw in raw_items]
	except Exception:
		log.warning("suggester %s failed on row %d; skipping AI suggestions", suggester.name, index, exc_info=True)
		return []
	accepted = []
	for finding in validated:
		if finding is None:
			log.warning("dropped invalid suggestion from %s on row %d", suggester.name, index)
		else:
			accepted.append(finding)
	return accepted
