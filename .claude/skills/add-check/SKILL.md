---
name: add-check
description: Add a new data-quality check (deterministic rule or heuristic) end to end - function, registration, tests, sample, docs, review. Use when asked to detect a new kind of issue in item records.
---

# Add a check

Follow these steps in order. Stop and ask the user if the source type, severity, or confidence isn't clear from the request. Those are product decisions.

## 1. Agree the behavior

Before writing code, state:
- `issue_type` (snake_case, stable)
- the trigger condition and when the check **abstains**
- source: `deterministic_rule` (exact, confidence 1.0) or `heuristic` (below 1.0)
- severity and confidence, with a one-line reason
- the explanation and suggested-action wording

## 2. Write tests first

Add tests to `tests/test_rules.py` or `tests/test_heuristics.py`:
- the positive case, and the negative case
- `None`, `""`, whitespace, and a missing key
- at least one near miss, e.g. a partial word match or a different case

## 3. Implement

- Add the function to `rules.py` or `heuristics.py` with the signature `(row: dict[str, Any], index: int) -> list[Finding]`.
- Return findings through the module helper, `_rule_finding` or `_heuristic_finding`, which fixes the source and confidence. Don't construct `Finding` directly in a check.
- Use `fields.text` / `fields.is_blank`, and build `evidence` from original values.
- Add it to `engine.CHECKS` at the position where its findings should appear within a row.

## 4. Update the sample

- Add a row to `samples/items.json` that triggers the check, if no existing row does.
- Update `EXPECTED` in `tests/test_samples.py` by hand.
- Regenerate `samples/expected_output.json` and read the diff, following `.claude/rules/testing.md`.

## 5. Document

- Add a row to the checks table in `README.md`.
- If the check introduces a new assumption or tradeoff, add an entry to `docs/decisions.md`.

## 6. Verify

- Run `.venv/bin/pytest -q`. All tests must pass.
- Run the `finding-reviewer` agent on the diff and address what it finds.
- Summarize for the user: the behavior, the tests added, the sample diff, and any reviewer findings you didn't act on, with the reason.
