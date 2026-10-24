import json
import subprocess
import sys

import pytest


def run_cli(*args):
	return subprocess.run(
		[sys.executable, "-m", "item_quality", *map(str, args)],
		capture_output=True,
		text=True,
	)


def write(tmp_path, content, name="items.json"):
	path = tmp_path / name
	path.write_text(content, encoding="utf-8")
	return path


def test_valid_file_prints_findings_json(tmp_path):
	path = write(
		tmp_path,
		json.dumps([{"item_id": "1", "item_description": "Ball bearing 6205", "manufacturer": "SKF"}]),
	)
	result = run_cli(path)
	assert result.returncode == 0, result.stderr
	[finding] = json.loads(result.stdout)
	assert finding["issue_type"] == "missing_part_number"
	assert finding["status"] == "needs_review"


def test_ai_stub_is_opt_in(tmp_path):
	path = write(
		tmp_path, json.dumps([{"item_id": "1", "item_description": "bearing", "manufacturer": "SKF"}])
	)
	default_sources = {f["source"] for f in json.loads(run_cli(path).stdout)}
	with_ai = json.loads(run_cli(path, "--ai-stub").stdout)
	assert "ai_assisted" not in default_sources
	assert [f["issue_type"] for f in with_ai if f["source"] == "ai_assisted"] == [
		"description_suggestion"
	]


def test_empty_array(tmp_path):
	result = run_cli(write(tmp_path, "[]"))
	assert result.returncode == 0
	assert json.loads(result.stdout) == []


def test_invalid_json(tmp_path):
	result = run_cli(write(tmp_path, "[{not json"))
	assert result.returncode == 2
	assert "not valid JSON" in result.stderr
	assert result.stdout == ""


def test_non_array_payload(tmp_path):
	result = run_cli(write(tmp_path, '{"item_id": "1"}'))
	assert result.returncode == 2
	assert "JSON array" in result.stderr


def test_missing_file(tmp_path):
	result = run_cli(tmp_path / "nope.json")
	assert result.returncode == 2
	assert "cannot read" in result.stderr


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e400", "-1e400"])
def test_non_finite_numbers_are_rejected(tmp_path, number):
	result = run_cli(write(tmp_path, f'[{{"item_id": "1", "category": {number}}}]'))
	assert result.returncode == 2
	assert "not valid JSON" in result.stderr
	assert result.stdout == ""


def test_output_is_strict_json(tmp_path):
	path = write(tmp_path, '[{"item_id": "1", "category": 1e300, "unit_of_measure": -0.0}]')
	result = run_cli(path)
	assert result.returncode == 0, result.stderr
	json.loads(result.stdout, parse_constant=lambda name: pytest.fail(f"emitted {name}"))
