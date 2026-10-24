---
paths:
  - "src/**/*.py"
---

# Review-safety rules

These rules apply to all source code. They protect the product promise in `docs/decisions.md` #001.

- **Never mutate input records.** Trim and case-fold only into local variables. `evidence` must hold original values (`row.get(...)`), not normalized ones.
- **Every check returns `list[Finding]`** from `models.py`. Don't add ad-hoc dicts or new fields without updating `docs/architecture.md`.
- **Label the source honestly.** Use `deterministic_rule` only when the condition is exact (confidence 1.0). Anything keyword-, length-, or threshold-based is `heuristic` with confidence below 1.0.
- **Use review wording.** Explanations and actions say "candidate", "needs review", "suggested", or "review before approval". Never use "fixed", "corrected", or "auto-approved".
- **Don't invent data.** Never fill a missing part number, category, or description as fact. Proposals belong in `evidence` and are presented as suggestions.
- **Use the absence helpers in `fields.py`** (`is_blank`, `text`). Don't write new blank checks.
- **Explanations quote the observed value** that triggered the finding.
- **Demo constants** (keyword maps, allowlists) stay module-level with a comment marking them as assumptions.
