# Decisions

Short records of choices that shape the code. Add a new entry when a decision changes behavior or a boundary, and don't rewrite old ones; supersede them.

<a id="001"></a>
## 001: Suggest, never correct

The tool outputs findings with `status: needs_review` and never modifies input. Data stewards own the decision, and a wrong automatic correction in master data spreads to other systems. A test checks that input is unchanged after a run, and another checks that output never claims a correction.

<a id="002"></a>
## 002: Checks are plain functions

Each check is `(row, index) -> list[Finding]`, listed in `engine.CHECKS`. With only a handful of checks, a plugin framework would add indirection without benefit. List order also fixes output order, which keeps golden-file diffs stable. Revisit this if checks need per-tenant configuration.

<a id="003"></a>
## 003: Three sources, labeled on every finding

`deterministic_rule` (exact, confidence 1.0), `heuristic` (signals that can be wrong, below 1.0), and `ai_assisted`. Reviewers need to know how much to trust a finding, and labeled findings can later be tracked against reviewer decisions. Rules and heuristics live in separate modules so the boundary is visible in code review.

<a id="004"></a>
## 004: AI output is opt-in and untrusted

Suggesters see a minimal record view and return raw dicts, and the engine validates them before any becomes a `Finding`. A suggester failure never hides rule findings. Because model output is treated like user input, no change to the model can bypass the contract.

<a id="005"></a>
## 005: Malformed values are reported, not converted

A numeric `item_id` is reported as `malformed_field` instead of being turned into `"1005"`. Silently converting it would hide source-system mapping errors that a steward should see.

<a id="006"></a>
## 006: Deferred for v0.1

The following are deferred:
- Duplicate detection (next step: match on normalized manufacturer and part number)
- CSV input
- Real LLM integration
- Persisting review decisions
- A UI

Within the limited time, a few complete, tested checks were worth more than many partial ones. Known heuristic gaps (placeholder severity, hierarchical categories) are listed in the README limitations.

<a id="007"></a>
## 007: Severity and confidence by check

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
