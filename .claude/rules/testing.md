---
paths:
  - "tests/**/*.py"
  - "samples/**"
---

# Testing rules

- **Every check needs tests** for the positive case, the negative case, and absent input (`None`, `""`, whitespace, and a missing key).
- **Write expectations from the requirement, not from current output.** If a test fails after a behavior change, decide whether the code or the test is wrong, and say which in the summary.
- **`samples/expected_output.json` is a reviewed artifact.** Regenerate it only for an intended behavior change:
  ```bash
  python -m item_quality samples/items.json --ai-stub > samples/expected_output.json
  git diff samples/expected_output.json
  ```
  Read the diff and update `EXPECTED` in `tests/test_samples.py` by hand.
- **Keep the safety tests passing**: input not mutated, no correction wording, and a failing suggester still returns rule findings.
- **CLI tests run the real entry point** via subprocess, not by calling `main()` directly.
