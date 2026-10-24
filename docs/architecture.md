# Architecture

## Purpose

Read item master records from multiple source systems and produce **review candidates**: findings a human data steward approves, rejects, or investigates. The system suggests and never corrects. No code path writes back to the input or to any other data store.

## Data flow

```
items.json ──► cli.load_records ──► engine.review ──► [Finding] ──► JSON on stdout
                                        │
                     per row:           ├─ rules.check_malformed_row   (gate: non-objects stop here)
                                        ├─ rules.*                     deterministic_rule
                                        ├─ heuristics.*                heuristic
                                        └─ ai.Suggester (opt-in)       ai_assisted
                                              │
                                     build_ai_input ─► suggest() ─► validate_ai_finding
```

| Module | Responsibility |
|---|---|
| `models.py` | `Finding` contract plus `Severity` and `Source` enums. Rejects invalid confidence, severity, and source values at construction, and deep-copies evidence so findings never share objects with input. |
| `fields.py` | Read-only field access. Missing, `null`, `""`, and whitespace are all treated as absent. |
| `rules.py` | Deterministic checks with confidence 1.0. |
| `heuristics.py` | Keyword and length signals with confidence below 1.0. They abstain when the evidence is ambiguous. |
| `ai.py` | `Suggester` protocol, input minimization, output validation, and the offline stub. |
| `engine.py` | Runs every check per row in the order of `CHECKS`. Isolates suggester failures. |
| `cli.py` | Loads input and writes JSON. Input errors go to stderr with exit code 2. |

Each check is a plain function `(row: dict, index: int) -> list[Finding]`. Adding one means writing the function and adding it to `engine.CHECKS`, with no registry or plugin system (see [decisions](decisions.md#002)).

## Finding contract

| Field | Meaning |
|---|---|
| `row_index` | Zero-based input position. Always present, so rows with missing or duplicate IDs can still be found. |
| `item_id` | Original string ID exactly as uploaded (not trimmed), or `null` if absent, blank, or malformed |
| `issue_type` | Stable machine-readable name, e.g. `missing_part_number` |
| `severity` | `low` / `medium` / `high`: review priority |
| `confidence` | 0–1: how strongly the evidence supports the observation. Assigned, not calibrated. |
| `explanation` | Why it was flagged, quoting the observed value |
| `suggested_action` | What a reviewer might do, never a claim that something was changed |
| `source` | `deterministic_rule` / `heuristic` / `ai_assisted` |
| `evidence` | Original values that triggered the finding |
| `status` | Always `needs_review`. Not a constructor argument, so no check can set it. |

## Input handling

- The input must be a JSON array. An empty array is valid and produces no findings.
- JSON is parsed strictly: `NaN`, `Infinity`, and numbers too large for a float are rejected as invalid input, and output is written with `allow_nan=False`, so it is always standard JSON.
- A non-object row gets one `malformed_row` finding and the remaining rows are still processed.
- A non-string value in a known field is reported as `malformed_field` and is never converted to text. Other checks treat it as present, so it doesn't trigger a second, misleading finding.
- Values are trimmed and case-folded only into local variables for comparison. Evidence always shows what was uploaded.

## AI boundary

The AI layer is designed for a real model to replace the stub without changing the engine.

| Concern | Control |
|---|---|
| Data exposure | `build_ai_input` sends only description, manufacturer, part number, and category. |
| Untrusted output | The model supplies data only: an allowlisted issue type, one proposal (bounded length), and a confidence (0–0.9, not boolean). Each suggestion is validated separately, so one bad item doesn't drop the others. |
| Wording | Explanation, suggested action, and severity come from templates in `ai.AI_ISSUES`. Model prose is never shown, so it can't claim a change was made. |
| Evidence integrity | Observed values in evidence are copied from the original row. Only allowlisted proposal keys (e.g. `proposed_description`) are taken from the model. |
| Identity spoofing | `row_index`, `item_id`, `source`, and `status` are set by the engine. Values the model returns for them are ignored. |
| Availability | Suggester exceptions, non-list output, and validation errors are caught and logged, and rule and heuristic findings still return. |
| Opt-in | Suggestions only run with `--ai-stub` (later, a real provider flag). |

### Introducing a real model

1. Implement `Suggester.suggest()` against the provider using structured output and a timeout.
2. Add each new suggestion type to `AI_ISSUES`, with its proposal key and reviewed template wording.
3. Record the provider, model, and prompt version in `evidence` for audit.
4. Track reviewer accept/reject decisions per `issue_type` to calibrate confidence.
5. Don't expand `AI_INPUT_FIELDS` to supplier, pricing, or customer data without a data-handling review.
