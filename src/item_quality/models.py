"""The review-candidate contract shared by every check."""

import copy
import math
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"


class Source(StrEnum):
	DETERMINISTIC_RULE = "deterministic_rule"
	HEURISTIC = "heuristic"
	AI_ASSISTED = "ai_assisted"


# Shallow freeze: evidence stays mutable to keep construction and serialization simple.
@dataclass(frozen=True)
class Finding:
	"""A candidate issue for a human reviewer. Never a correction."""

	row_index: int
	item_id: str | None
	issue_type: str
	severity: Severity
	confidence: float
	explanation: str
	suggested_action: str
	source: Source
	evidence: dict[str, Any] = field(default_factory=dict)
	# Not settable: approval belongs to a human workflow, never to a check.
	status: str = field(default="needs_review", init=False)

	def __post_init__(self) -> None:
		if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
			raise ValueError(f"confidence must be a number, got {self.confidence!r}")
		if not (math.isfinite(self.confidence) and 0.0 <= self.confidence <= 1.0):
			raise ValueError(f"confidence must be in [0, 1], got {self.confidence!r}")
		# Fail fast on typos: these raise ValueError for unknown values.
		Severity(self.severity)
		Source(self.source)
		# Evidence must not share lists/dicts with input records.
		object.__setattr__(self, "evidence", copy.deepcopy(self.evidence))

	def to_dict(self) -> dict[str, Any]:
		data = asdict(self)
		data["severity"] = str(self.severity)
		data["source"] = str(self.source)
		return data
