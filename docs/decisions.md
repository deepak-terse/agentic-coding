# Decisions

Short records of choices that shape the code. Add a new entry when a decision changes behavior or a boundary, and don't rewrite old ones; supersede them.

<a id="001"></a>
## 001: Suggest, never correct

The tool outputs findings with `status: needs_review` and never modifies input. Data stewards own the decision, and a wrong automatic correction in master data spreads to other systems. This includes reading: a malformed value such as a numeric `item_id` is reported as `malformed_field`, not silently converted to text, because conversion would hide source-system mapping errors. A test checks that input is unchanged after a run, and another checks that output never claims a correction.

<a id="002"></a>
## 002: Checks are plain functions

Each check is `(row, index) -> list[Finding]`, listed in `engine.CHECKS`. With only a handful of checks, a plugin framework would add indirection without benefit. List order also fixes output order, which keeps golden-file diffs stable. Revisit this if checks need per-tenant configuration.

<a id="003"></a>
## 003: Three sources, labeled on every finding

`deterministic_rule` (exact, confidence 1.0), `heuristic` (signals that can be wrong, below 1.0), and `ai_assisted`. Reviewers need to know how much to trust a finding, and labeled findings can later be tracked against reviewer decisions. Rules and heuristics live in separate modules so the boundary is visible in code review.

<a id="004"></a>
## 004: AI suggestions are opt-in and validated like user input

**Decision.** A model can only propose. It never sets identity, provenance, or what was observed, and its output is discarded unless it passes validation.

- **Opt-in.** Suggestions run only when a suggester is passed (`--ai-stub` today).
- **Minimal input.** The suggester sees four fields: description, manufacturer, part number, and category.
- **Engine-owned fields.** `row_index`, `item_id`, `source`, `status`, and the observed values in `evidence` come from the record. Only allowlisted proposal keys come from the model.
- **Bounded claims.** Confidence is at most 0.9, severity at most `medium`, and text that claims a change was made is rejected.
- **Isolated failures.** If the suggester raises an error or returns malformed output, its suggestions are dropped with a warning and rule findings are unaffected.

**Why.** Model output can be wrong, inconsistent, or shaped by text inside the records (prompt injection). Treating it like untrusted user input keeps the finding contract intact whichever model is plugged in.

**Limits.** Validation checks the shape and wording of a suggestion, not whether it's right. A well-formed but wrong proposal still reaches the reviewer, which is why it's labelled `ai_assisted` and stays `needs_review`.

<a id="005"></a>
## 005: Deferred for v0.1

The following are deferred:
- Duplicate detection (next step: match on normalized manufacturer and part number)
- CSV input
- Real LLM integration
- Persisting review decisions
- A UI

Within the limited time, a few complete, tested checks were worth more than many partial ones. Known heuristic gaps (placeholder severity, hierarchical categories) are listed in the README limitations.

<a id="006"></a>
## 006: Severity and confidence by check

Severity is about the cost of not looking. Confidence is about how directly the evidence shows the issue.

| Check | Severity | Why | Confidence | Why |
|---|---|---|---|---|
| `malformed_row` | high | The row was not checked at all | 1.0 | Type test |
| `incomplete_row` | high | Item can't be identified or described | 1.0 | Presence test |
| `malformed_field` | medium | A mapping error that may hide other issues | 1.0 | Type test |
| `missing_part_number` | medium | Blocks matching and sourcing, but the item is usable | 1.0 | Presence test |
| `unsupported_unit_of_measure` | medium | Wrong unit risks quantity errors downstream | 1.0 | Allowlist test |
| `vague_description` | low | Quality problem, not a blocker | 0.7 | Word lists miss domain terms |
| `category_mismatch_candidate` | low | Keyword signal only; categories vary by system | 0.7 | Same |
| `description_suggestion` (AI) | low (max medium) | A proposal, not an observation | ≤ 0.9 | Model output is never certain |

The vague-description check flags placeholders, all-generic descriptions, and single words. Flagging every short description caught things like "Safety glasses" and buried the real cases. Placeholders stay `low` because the field is technically present; promoting them to `incomplete_row` is a product decision for later.
