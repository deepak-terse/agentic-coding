# Item Quality Assistant

A small command-line tool that reviews item master records from multiple source systems and produces **review candidates**: structured, explainable findings for a human data steward.

It never changes data. Each finding says what looks wrong, why, how confident the tool is, and what a reviewer might do next. The reviewer decides.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m item_quality samples/items.json               # rules + heuristics
python -m item_quality samples/items.json --ai-stub     # + simulated AI suggestions

pytest                                                  # 165 tests
ruff format --check src tests && ruff check src tests   # format (tabs) + lint
```

Requires Python 3.11+. No runtime dependencies. The output is a JSON array on stdout. Bad input (unreadable file, invalid JSON, a non-array payload, `NaN` or `Infinity`) prints an error on stderr and exits with code 2.

## What it does

| Issue type | Source | Severity | Confidence | Trigger |
|---|---|---|---|---|
| `malformed_row` | deterministic_rule | high | 1.0 | Row is not a JSON object |
| `incomplete_row` | deterministic_rule | high | 1.0 | `item_id` or `item_description` missing, null, or blank |
| `malformed_field` | deterministic_rule | medium | 1.0 | A known field holds a non-string (e.g. numeric `item_id`) |
| `missing_part_number` | deterministic_rule | medium | 1.0 | Manufacturer present, part number absent |
| `unsupported_unit_of_measure` | deterministic_rule | medium | 1.0 | Unit not in the supported list |
| `vague_description` | heuristic | low | 0.7 | A placeholder (`N/A`, `TBD`), only generic terms ("spare part"), or a single word with no digits |
| `category_mismatch_candidate` | heuristic | low | 0.7 | A description keyword points to a different category |
| `description_suggestion` | ai_assisted | low | 0.5 | The stub proposes a fuller description (opt-in) |

**Confidence** is how strongly the evidence supports the observation. These are assigned values, not calibrated probabilities. **Severity** is review priority. The reasons for each value are in [decisions #006](docs/decisions.md#006).

```
src/item_quality/
  models.py      Finding contract (validated; status is always needs_review)
  fields.py      read-only field access: text() for comparison, identity() for output
  rules.py       deterministic checks        → _rule_finding()      source + confidence 1.0 fixed
  heuristics.py  keyword and length checks   → _heuristic_finding() source + low/0.7 fixed
  ai.py          Suggester protocol, validation, templates, offline stub
  engine.py      runs checks per row in a fixed order; isolates AI failures
  cli.py         strict JSON in, strict JSON out
```

- **The AI layer supplies data only.** The model returns an issue type, a proposal and a confidence (at most 0.9). The explanation, suggested action and severity come from application templates, so a model can't claim it changed anything. It sees four fields and is off unless `--ai-stub` is passed.
- **Input is never mutated.** Evidence holds deep copies of the uploaded values, and IDs appear exactly as uploaded.

Data flow, the finding contract and the AI controls are in [`docs/architecture.md`](docs/architecture.md).

## Sample input and output

[`samples/items.json`](samples/items.json) has nine rows, chosen so every check fires at least once. It also includes one clean row and one duplicate from another system (a known gap). The full output is in [`samples/expected_output.json`](samples/expected_output.json): 14 findings with `--ai-stub`, 10 without.

```json
{"item_id": "1001", "item_description": "bearing", "manufacturer": "SKF", "manufacturer_part_number": "", "category": "Mechanical", "unit_of_measure": "EA", "source_system": "ERP-A"}
```

This row produces `missing_part_number`, `vague_description` and, with `--ai-stub`, a `description_suggestion`. The first of these:

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

## Tests

There are 165 pytest tests, which run in about a second.

| File | Tests | Covers |
|---|---|---|
| `test_rules.py` | 55 | Each rule's positive and negative cases, and absent input in five forms (missing key, `None`, `""`, spaces, tab) |
| `test_heuristics.py` | 42 | Positive and negative cases, near misses (partial words, 3-word boundary, conflicting keywords), placeholders, and abstaining on a missing category |
| `test_ai.py` | 32 | Untrusted model output (bad types, NaN, overflow, out-of-range confidence), ignored model prose, a regression test for the change-claim bypass, data minimization, and failure isolation |
| `test_cli.py` | 12 | The real CLI as a subprocess: valid file, empty array, invalid JSON, non-array payload, missing file, non-finite numbers, strict-JSON output |
| `test_models.py` | 11 | The `Finding` contract: confidence bounds and type, unknown enum values, `status` can't be set |
| `test_engine.py` | 10 | Ordering, a bad row not stopping the others, input not mutated, no correction wording (with AI on and off), item IDs kept as uploaded |
| `test_samples.py` | 3 | Hand-written expectations for every sample row, plus the golden file |

The expectations in `test_samples.py` were written from the design before the sample was first run. The golden file is regenerated only for intended changes, and its diff is read by hand (see [`.claude/rules/testing.md`](.claude/rules/testing.md)).

## Assumptions and tradeoffs

**Assumptions**
- Input is a JSON array of objects. Unknown fields are ignored. `item_id` and `item_description` are required.
- The unit-of-measure allowlist, generic-term and placeholder lists, and the keyword-to-category map are small demo assumptions, marked as such in code. A real deployment would load them from reference data.
- Duplicate `item_id`s are accepted and reported per row. No identity resolution is attempted.

**Tradeoffs.** Each one is recorded in [`docs/decisions.md`](docs/decisions.md).
- **Suggest, never correct**, including when reading input: malformed values are reported, not converted.
- **Checks are plain functions in a list**, with no plugin framework, because a few checks don't justify one.
- **Fewer complete checks over many partial ones.** Duplicate detection, CSV input and a real LLM are deferred.
- **Heuristics abstain when unsure.** They don't flag unknown terms, conflicting keywords or a blank category, which favours precision over recall.
- **AI output is treated as untrusted input.** Templated wording makes AI findings less expressive, but no model output can claim a change was made.

## How AI was used

The project was built with Claude Code, step by step, with a human approving each step.

- **Delegated to the agent:**
  - scaffolding and first drafts of every check
  - test cases and sample data
  - documentation drafts
  - the formatter and lint setup
- **Kept as human decisions:**
  - scope and what to defer
  - the suggest-never-correct behaviour
  - severity and confidence values
  - which review findings to fix and which to document as limitations
- **How AI output was verified:**
  - Tests were written for every check, and the golden output was compared against expectations written by hand.
  - A read-only reviewer agent ([`.claude/agents/finding-reviewer.md`](.claude/agents/finding-reviewer.md)) ran twice. It found 11 issues on the first pass, including invented AI evidence and shared evidence objects, and 3 regressions on the second.
  - A separate independent review then found a way around the change-claim filter. That led to replacing the filter with app-owned templates ([decisions #004](docs/decisions.md#004)).

The agent setup is part of the repo, so others get the same guardrails:

```
CLAUDE.md                          entry point: commands, where things are, what needs approval
.claude/settings.json              hook: runs ruff format on every Python file the agent edits
.claude/rules/                     path-scoped rules: review safety, AI boundary, testing
.claude/skills/add-check/          workflow for a new check: behaviour > tests > code > sample > docs > review
.claude/agents/finding-reviewer.md read-only reviewer, run before a change is done
docs/                              architecture and decision log, shared by people and agents
```

## Next steps

1. **Duplicate detection.** Match on normalized manufacturer and part number (`6205-ZZ` == `6205ZZ`). Sample row 6 duplicates row 1 and isn't flagged today.
2. **Smarter heuristics.** Promote placeholders to `incomplete_row`, compare hierarchical categories (`Mechanical > Bearings`) on their top level, and handle abbreviations and non-English text (`BRG`, `Kugellager`).
3. **A review workflow.** Persist approve and reject decisions with an audit trail, then use them to calibrate confidence for each `issue_type`.
4. **A real LLM behind `Suggester`.** Use structured output and timeouts, record the model and prompt version on each finding, and only target rows that already have a vague description. The stub currently over-suggests.
5. **Scale.** Add CSV input, and stream review and output for very large files. Today everything is held in memory.
