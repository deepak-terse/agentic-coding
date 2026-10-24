# Item Quality Assistant

A small command-line tool that reviews item master records from multiple source systems and produces **review candidates**: structured, explainable findings for a human data steward.

It never changes data. Each finding says what looks wrong, why, how confident the tool is, and what a reviewer might do next. The reviewer decides.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest                                                  # 165 tests
ruff format src tests                                   # tabs, 2-column display width
python -m item_quality samples/items.json               # rules + heuristics
python -m item_quality samples/items.json --ai-stub     # + simulated AI suggestions
```

Requires Python 3.11+. No runtime dependencies.

## Example

Input (`samples/items.json`, excerpt):

```json
{"item_id": "1001", "item_description": "bearing", "manufacturer": "SKF", "manufacturer_part_number": "", "category": "Mechanical", "unit_of_measure": "EA", "source_system": "ERP-A"}
```

Output (one of three findings for this row):

```json
{
  "row_index": 0,
  "item_id": "1001",
  "issue_type": "missing_part_number",
  "severity": "medium",
  "confidence": 1.0,
  "explanation": "Manufacturer 'SKF' is present but manufacturer part number is blank.",
  "suggested_action": "Request the manufacturer part number from the source owner.",
  "source": "deterministic_rule",
  "evidence": {"manufacturer": "SKF", "manufacturer_part_number": ""},
  "status": "needs_review"
}
```

The full expected output for the sample is in [`samples/expected_output.json`](samples/expected_output.json).

## Checks

| Issue type | Source | Severity | Confidence | Trigger |
|---|---|---|---|---|
| `malformed_row` | deterministic_rule | high | 1.0 | Row is not a JSON object |
| `malformed_field` | deterministic_rule | medium | 1.0 | A known field holds a non-string (e.g. numeric `item_id`) |
| `incomplete_row` | deterministic_rule | high | 1.0 | `item_id` or `item_description` missing, null, or blank |
| `missing_part_number` | deterministic_rule | medium | 1.0 | Manufacturer present, part number absent |
| `unsupported_unit_of_measure` | deterministic_rule | medium | 1.0 | Unit not in the supported list |
| `vague_description` | heuristic | low | 0.7 | A placeholder (`N/A`, `TBD`), only generic terms ("spare part"), or a single word with no digits |
| `category_mismatch_candidate` | heuristic | low | 0.7 | Description keyword points to a different category |
| `description_suggestion` | ai_assisted | low | 0.5 | Stub proposes a fuller description (opt-in; AI is capped at medium / 0.9) |

**Confidence** is how strongly the evidence supports the observation, not the probability that a change is needed. These are assigned values, not calibrated scores. **Severity** is review priority. The reasons for each value are in [`docs/decisions.md`](docs/decisions.md#006).

## Design

```
src/item_quality/
  models.py      Finding contract, Severity and Source enums
  fields.py      read-only field access; null / blank / whitespace = absent
  rules.py       deterministic checks
  heuristics.py  keyword and length checks
  ai.py          Suggester protocol, output validation, offline stub
  engine.py      runs checks per row in a fixed order
  cli.py         JSON in, JSON out; errors to stderr with exit code 2
```

- **Each check is a plain function** `(row, index) -> list[Finding]`, registered in `engine.CHECKS`.
- **Rules, heuristics, and AI suggestions are separate**, and every finding says which one produced it.
- **Input is read-only**, and evidence always shows the uploaded values.
- **AI output is opt-in and untrusted.** A suggester sees a minimal view of the record, its output is validated before use, and if it fails the other findings are still returned.

Details are in [`docs/architecture.md`](docs/architecture.md), and the reasoning behind them is in [`docs/decisions.md`](docs/decisions.md).

## Assumptions

- Input is a JSON array of objects. Unknown fields are ignored.
- `item_id` and `item_description` are required. Other fields are optional.
- The unit-of-measure allowlist, generic-term list, and keyword-to-category map are small demo assumptions marked as such in code. A real deployment would load them from reference data.
- Duplicate `item_id`s are accepted and reported per row. Identity resolution is not attempted yet.

## Limitations and next steps

- **Duplicate detection** is not implemented. `samples/items.json` row 6 is the same SKF bearing as row 1 from another system (`6205-ZZ` vs `6205ZZ`) and is not flagged. Next step: match on normalized manufacturer and part number.
- **Abbreviations and non-English text** (`BRG`, `VLV`, `Kugellager`) aren't recognized, so the heuristics abstain. A synonym table or a real model would help.
- **Placeholder values** like `N/A` or `TBD` get only a low-severity `vague_description`, not the high-severity `incomplete_row`. The placeholder list is short and English-only.
- **Hierarchical categories** (`Mechanical > Bearings`) are compared as exact strings, so they produce false category mismatches. Matching on the top-level segment would fix this.
- **The AI wording filter is conservative.** If a model uses words like "fixed" or "updated" in its own sentence, outside the record values, the suggestion is dropped.
- **The AI stub over-suggests.** It proposes adding the manufacturer even to good descriptions. That's fine for showing the boundary, but a real suggester should target rows that already have a vague description.
- **Confidence values are not calibrated.** Tracking reviewer accept/reject decisions per `issue_type` would let them be tuned.
- **No review workflow yet**: no persistence of approve/reject decisions or audit history.
- **CSV input** is not supported.
- **Real LLM integration**: implement `Suggester` against a provider, with timeouts, structured output, and model and prompt version recorded on each finding.

## Working on this repo with AI agents

The repo includes a small Claude Code setup, so contributors working with an AI agent follow the same conventions:

```
CLAUDE.md                          entry point: commands, where things are, what needs approval
.claude/settings.json              hook: runs ruff format on every Python file the agent edits
.claude/rules/                     path-scoped rules, loaded only for matching files
  review-safety.md                 src/**     no mutation, honest source labels, review wording
  ai-boundary.md                   ai.py, engine.py   data minimization, output validation
  testing.md                       tests/**, samples/**   test expectations, golden-file process
.claude/skills/add-check/          repeatable workflow: behavior > tests > code > sample > docs > review
.claude/agents/finding-reviewer.md read-only reviewer run before a change is done
docs/                              architecture and decision log, shared by people and agents
```

To scale this, add a rule when a review catches a new class of mistake, add a skill when a workflow is repeated, and record boundary changes in `docs/decisions.md`.
