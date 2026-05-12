# Project: scrytalk

An Anthropic Skill for natural-language *Magic: The Gathering* card search via
the Scryfall API. See `README.md` for the project overview and `SKILL.md` for
the skill itself.

## Stack
- Python 3.10+. The shipped skill (`scripts/scryfall_search.py`) is **standard
  library only** — zero runtime dependencies, so it runs anywhere Python 3 is
  installed with no `pip install` step.
- `uv` manages the development environment; `pyproject.toml` is the source of
  truth. The only dev dependencies are `pytest` and `pytest-cov`.
- Tests run against a local mock HTTP server (`tests/conftest.py`) — never the
  live Scryfall API.

## Hard rules (these are enforced by hooks; don't try to bypass)
- NEVER use `git commit --no-verify` or `git push --no-verify`.
- NEVER add a third-party **runtime** dependency to `scripts/scryfall_search.py`.
  The stdlib-only constraint is the whole point — `urllib` over `requests` is a
  deliberate trade for zero-install portability. Dev-only deps go in
  `pyproject.toml` via `uv add --dev`.
- NEVER `pip install` outside a virtualenv; use `uv add` to update
  `pyproject.toml`.
- NEVER edit `.env`, `.env.local`, or files under a tooling-managed directory
  without explicit user instruction.
- NEVER mark a task complete without running `uv run pytest -x` and reading the
  output.

## Workflow
- Plan-mode FIRST for any task > 30 LoC. Output plans to `./plans/`.
- One ticket = one branch = one PR. Branch naming: `claude/<short-slug>`.
- Commit messages: Conventional Commits. Footer should reference an issue
  (`Refs #N` / `Closes #N`) when one exists.
- Before opening a PR: run `/red-team`. Address every BLOCK and
  REQUEST_CHANGES finding or justify rejecting it in the PR body.

## Testing discipline
- Every new public function needs a test in `tests/`.
- Every bug fix starts with a failing test that reproduces the bug, committed
  first.
- The `pre-push` hook runs `pytest --cov --cov-fail-under=85`. Keep coverage
  above 85%; aim for 100% on changed lines (`uv run pytest --cov
  --cov-report=term-missing`).

## Code design preferences
- Prefer explicit over clever. Prefer plain functions over classes.
- Prefer `pathlib.Path` over `os.path`.
- `mypy --strict` runs in pre-commit, so type-annotate **every** function —
  public and internal alike. No `Any` without a `# noqa`/comment explaining it.
- Comments only where the *why* isn't obvious (Scryfall's quirks — the 30s 429
  lockout, the heavier search rate-limit tier — are worth a comment).
- Error messages should be useful to a human reading them in a terminal.

## When stuck
- Re-read this file and `SKILL.md`. If still stuck, STOP and ask.
- Don't write defensive code to paper over a confusing API — fix the API or
  surface the question.
