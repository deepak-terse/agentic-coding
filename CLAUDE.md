# CLAUDE.md

Item Quality Assistant: a Python CLI that reads item master records (JSON) and outputs **review candidates** for a human data steward. It suggests; it never corrects.

## Commands

```bash
pip install -e ".[dev]"                                  # install into .venv
.venv/bin/pytest -q                                      # run all tests
.venv/bin/ruff format src tests                          # format (tabs, width 2)
.venv/bin/ruff check src tests                           # lint
python -m item_quality samples/items.json [--ai-stub]    # run on sample input
```

## Where things are

- `docs/architecture.md`: data flow, module responsibilities, the finding contract, and the AI boundary
- `docs/decisions.md`: why the code is shaped this way. Read it before changing a boundary, and add an entry when you do.
- `.claude/rules/`: path-scoped rules that load when you work on `src/`, `tests/`, or the AI layer
- `.claude/skills/add-check`: the step-by-step workflow for adding a new check
- `.claude/agents/finding-reviewer`: read-only reviewer. Run it before you consider a change done.

## Always

- Never mutate input records, and never claim a correction was made. Every output is `needs_review`.
- Use the `Finding` contract in `src/item_quality/models.py` for every check.
- Run `.venv/bin/pytest -q` before reporting work as done, and report failures as they are.
- Python 3.11+, standard library only at runtime. Keep functions small, with no frameworks.
- Indent with tabs (2 columns wide). Python files are formatted automatically after every edit by a hook in `.claude/settings.json`, so don't hand-format.

## Ask first

- Expanding scope beyond `docs/decisions.md` #005 (duplicates, CSV, real LLM, persistence, UI)
- Changing severity or confidence values, or what the AI layer can see
- Regenerating `samples/expected_output.json` for anything other than an intended behavior change
