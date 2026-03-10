# Testing Conventions and Known Issues

## editor.text Direct Assignment: When Allowed and When Forbidden

`editor.text = "..."` directly modifies the `CodeEditor` reactive property,
but **does not update the rendered content of the `TextArea` widget**.

### Allowed: Verifying the reactive layer in unit tests

Direct assignment is appropriate in `test_code_editor.py`, `test_main_view.py`, and `test_app.py`.

- Purpose: testing `CodeEditor`'s reactive logic (`watch_text`, `update_title`,
  `has_unsaved_pane()`, etc.), not the actual typing flow
- No race conditions are exposed because `TextArea` visual content is not captured in snapshots

```python
# OK: verify reactive layer behaviour
editor.text = "modified\n"
await pilot.pause()
assert editor.title.endswith("*")
```

### Allowed: Snapshot tests that visualise state changes other than TextArea content

For UI elements like the `*` in a tab title, direct assignment is more stable than `pilot.press()`,
which can introduce visual noise such as cursor position.

```python
# used in test_snapshot_unsaved_marker - verifies tab title *
editor.text = "modified content\n"
await pilot.pause()
# snapshot: tab title shows *, TextArea still shows original content
```

### Forbidden: When snapshot behaviour depends on "file is modified" app logic

Flows controlled by `has_unsaved_pane()` — such as `app.action_quit()` or `ctrl+w` —
become **flaky** when direct assignment is used.

**Root cause**: after `pilot.pause()`, the Textual event loop may process `TextArea.Changed`
and overwrite `editor.text` with the TextArea's current (original) content. As a result,
`has_unsaved_pane()` returns False, the modal never opens, and the app exits immediately.

```python
# BAD: race condition possible
editor.text = "modified\n"
await pilot.pause()
app.action_quit()   # has_unsaved_pane() may return False
```

```python
# GOOD: goes through the full TextArea.Changed flow via pilot.press()
editor.action_focus()
await pilot.pause()
await pilot.press("x")
await pilot.pause()
app.action_quit()   # has_unsaved_pane() is reliably True
```

---

## ~~Known~~ Resolved Flaky Snapshot Tests (commit `5b2ec0c`)

> **Status: Fixed** — commit `5b2ec0c fix: eliminate flaky snapshot tests by removing focus race condition`

### Root cause (before fix)

`action_open_code_editor` in `app.py` scheduled focus asynchronously via
`editor.call_later(editor.action_focus)`. This deferred focus event raced with
the `run_before` callback of `snap_compare`, creating non-deterministic rendering state.

### Fix

Removed `call_later` and changed to a direct synchronous call to `editor.action_focus()`:

```python
# app.py - after fix
editor.action_focus()   # synchronous direct call → deterministic timing
```

The `@pytest.mark.xfail(strict=False)` marks were also removed, converting both tests
to normal passing tests.

---

## How to Regenerate Snapshots

Snapshots **must** be updated together with the full test suite.
Running `--snapshot-update` on `tests/test_snapshots.py` alone omits global state
left by non-snapshot tests, causing mismatches on the next full run.

```bash
# Correct: update with the full test suite
uv run pytest tests/ --snapshot-update

# Wrong: update snapshots in isolation (may cause partial failures on next full run)
uv run pytest tests/test_snapshots.py --snapshot-update
```
