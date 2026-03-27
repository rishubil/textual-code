# Agent Instructions

**CRITICAL RULES:**
- Put the truth and the correct answer above all else. Feel free to criticize user's opinion, and do not use false empathy with the user. Keep a dry and realistic perspective.
- Use qmd to check documentation on every task to maintain consistency
- **Always run Python with `uv`**: never call `python` or `pip` directly; always use `uv run python`, `uv run pytest`, `uv run ruff`, etc.
- **Avoid `$()` in Bash tool calls**: `$()` command substitution triggers extra user confirmation in Claude Code. Split into separate Bash tool calls instead:
  ```
  # BAD — single Bash call with nested $() requires extra confirmation
  uv run pytest tests/ -n $(( $(nproc) * 2 )) -m "not serial"

  # GOOD — two separate Bash tool calls
  Call 1: nproc          → returns e.g. "4"
  Call 2: uv run pytest tests/ -n 8 -m "not serial"
  ```
  Read the output of the first call and substitute the value directly into the second call.
- Use WebFetch proactively. Always check the latest development docs and search for anything unclear.
- All code comments, docstrings, and documentation (including files in `docs/`) must be written in **English**.
- **Never use `ty: ignore`, `type: ignore`, or `# noqa`**: these comments suppress checker errors and hide real bugs. Fix the underlying issue instead — use `assert isinstance()`, `cast()` with the precise target type (never `cast(Any, ...)`), proper type annotations, or `monkeypatch.setattr()` for test monkey-patches.

## Test Strategy: Red-Green TDD

> See `docs/testing-guide.md` for test patterns, best practices, and gotchas (`make_app(light=True)`, `pilot.pause()` rules, snapshot conventions, etc.)

**Before starting work, check and run existing tests:**

1. **Find test files**: use Glob/Grep to find test files related to the code you are modifying
2. **Run existing tests**: run tests before starting work to understand the current state (pass/fail)
3. **Establish a baseline**: know which tests pass before your changes so you can detect regressions

**Apply Red-Green TDD to modification tasks:**

- **Red**: first write or identify a test that verifies the behaviour to be changed (failing state)
- **Green**: implement the minimum code needed to make the test pass
- **Verify**: confirm that all pre-existing tests still pass

**When modifying code with no tests:**
- Add tests before modifying if possible
- If adding tests is out of scope, state it explicitly: "This change has no tests"

**When adding new UI (modal / widget / screen):**
- A snapshot test is **mandatory**. Add it to `tests/test_snapshots.py` before the implementation is merged.
- Use `_open_editor_modal` helper for editor-triggered modals; use `_open_app_modal` for app-level modals.
- Run `uv run pytest tests/test_snapshots.py --snapshot-update` after adding the test to generate the SVG.

## Textual Official Documentation

When Textual framework behaviour (API, Widget, Screen, Worker, reactive, etc.) is uncertain, **always search the local docs before implementing**.

- **Local docs**: `docs/libs/textual/` (MkDocs format, mirrored from textual.textualize.io)
- Key topics: App · ModalScreen · push_screen · dismiss · Message · on_* · reactive · watch_* · Worker · @work · BINDINGS · Binding · action_* · CommandPalette · Provider · TCSS · TabbedContent · TabPane · DirectoryTree · TextArea

**No guessing**: if behaviour is unclear, search the local docs first.

---

See @README.md for project overview