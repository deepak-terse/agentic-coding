---
paths:
  - "src/item_quality/ai.py"
  - "src/item_quality/engine.py"
---

# AI boundary rules

Changes here affect what a model can see and what it can claim. See `docs/architecture.md#ai-boundary`.

- **Don't widen `AI_INPUT_FIELDS`** without the user's explicit approval. Supplier, pricing, and customer fields must never be sent.
- **Suggester output is untrusted.** Every raw item must pass `validate_ai_finding()` before it becomes a `Finding`.
- **The engine sets `row_index`, `item_id`, `source`, `status`, and the observed values in evidence.** Never read them from suggester output. Only allowlisted proposal keys come from the model.
- **Never show model prose.** Explanation, action, and severity come from the `AI_ISSUES` template; the model supplies only a proposal and a confidence (at most `MAX_AI_CONFIDENCE`).
- **New AI issue types** go into `AI_ISSUES` only together with tests for invalid output of that type.
- **A suggester failure must never remove rule or heuristic findings.** Keep the `try/except` around `suggest()` and log a warning.
- **No network calls in tests.** Use stub or fake suggesters.
