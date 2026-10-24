"""End-to-end checks on samples/items.json.

EXPECTED was written by hand from docs/architecture.md before the sample was run.
The golden file guards the full output (wording, evidence) against accidental change;
regenerate it only on purpose and review the diff.
"""

import json
import subprocess
import sys
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

D, H, A = "deterministic_rule", "heuristic", "ai_assisted"

EXPECTED = [
	(0, "missing_part_number", D),  # SKF with blank part number
	(0, "vague_description", H),  # "bearing" alone
	(0, "description_suggestion", A),
	(1, "category_mismatch_candidate", H),  # bearing filed under Electrical
	# row 2: complete, consistent record -> no findings
	(3, "incomplete_row", D),  # whitespace-only description
	(3, "unsupported_unit_of_measure", D),  # "EACH"
	(4, "malformed_field", D),  # numeric item_id
	(4, "description_suggestion", A),
	(5, "incomplete_row", D),  # null item_id
	(5, "vague_description", H),  # "relay" alone
	(5, "description_suggestion", A),
	# row 6: same item as 1002 from another system; duplicates are out of scope for now
	(7, "malformed_row", D),  # "N/A" instead of an object
	(8, "missing_part_number", D),
	(8, "description_suggestion", A),
]


def run(*args):
	result = subprocess.run(
		[sys.executable, "-m", "item_quality", str(SAMPLES / "items.json"), *args],
		capture_output=True,
		text=True,
		check=True,
	)
	return json.loads(result.stdout)


def test_sample_findings_match_hand_written_expectations():
	findings = run("--ai-stub")
	assert [(f["row_index"], f["issue_type"], f["source"]) for f in findings] == EXPECTED


def test_sample_output_matches_golden_file():
	expected = json.loads((SAMPLES / "expected_output.json").read_text(encoding="utf-8"))
	assert run("--ai-stub") == expected


def test_without_ai_only_rule_and_heuristic_findings():
	findings = run()
	assert {f["source"] for f in findings} == {D, H}
	assert len(findings) == len([e for e in EXPECTED if e[2] != A])
