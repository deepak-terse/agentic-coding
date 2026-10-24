"""Command-line entry point: item JSON in, review candidates JSON out."""

import argparse
import json
import logging
import sys
from pathlib import Path

from item_quality.ai import StubSuggester
from item_quality.engine import review

EXIT_INPUT_ERROR = 2


def load_records(path: Path) -> list:
	try:
		payload = json.loads(path.read_text(encoding="utf-8"))
	except OSError as exc:
		raise ValueError(f"cannot read {path}: {exc.strerror}") from exc
	except json.JSONDecodeError as exc:
		raise ValueError(f"{path} is not valid JSON: {exc.msg} (line {exc.lineno})") from exc
	if not isinstance(payload, list):
		raise ValueError(f"{path} must contain a JSON array of records")
	return payload


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		prog="item-quality",
		description="Flag item records that may need review. Input is never modified.",
	)
	parser.add_argument("input", type=Path, help="JSON file containing an array of item records")
	parser.add_argument(
		"--ai-stub",
		action="store_true",
		help="include AI-assisted description suggestions from the offline stub",
	)
	args = parser.parse_args(argv)
	logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

	try:
		records = load_records(args.input)
	except ValueError as exc:
		print(f"error: {exc}", file=sys.stderr)
		return EXIT_INPUT_ERROR

	findings = review(records, StubSuggester() if args.ai_stub else None)
	json.dump([f.to_dict() for f in findings], sys.stdout, indent=2)
	sys.stdout.write("\n")
	return 0
