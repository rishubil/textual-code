# Testing Guide: Patterns, Best Practices, and Gotchas

## Running Tests

```bash
# Unit/integration tests — parallel (2x CPU cores)
uv run pytest tests/ -n $(( $(nproc) * 2 )) -m "not serial"

# Snapshot tests — must run serially
uv run pytest tests/ -m serial

# Update snapshots after UI changes
uv run pytest tests/test_snapshots.py --snapshot-update

# Single file
uv run pytest tests/test_code_editor.py
```

Tests are I/O-bound (event loop waiting), so using 2x CPU cores as workers is optimal.

## Test App: `make_app()` and `light` Mode

All integration tests create a `TextualCode` app via the `make_app()` factory in `conftest.py`.

```python
from tests.conftest import make_app

app = make_app(workspace, open_file=sample_py_file)  # full app with sidebar
app = make_app(workspace, open_file=sample_py_file, light=True)  # no sidebar
```

### When to use `light=True`

Use `light=True` when the test does **not** interact with the sidebar or explorer.
This skips mounting `Sidebar`, `FilteredDirectoryTree`, and `WorkspaceSearchPane`,
reducing per-test overhead by ~11%.

### When to use the full app (default)

- Tests that reference `app.sidebar`, explorer, or workspace search
- Snapshot tests (the SVG captures the full UI including sidebar)
- Tests that use absolute mouse coordinates affected by sidebar width

## `pilot.pause()`: When Required and When Redundant

`pilot.press()` internally calls `_wait_for_screen()`, which processes pending widget
events and settles the screen. `pilot.pause()` does the same plus `wait_for_idle(0)`.

### Required after

| Situation | Why |
|-----------|-----|
| `editor.text = "..."` | Reactive property change — watchers need a cycle |
| `action_*()` calls | Actions often schedule deferred work via `call_next` |
| `app.run_test()` entry | First pause waits for full app mount |
| `pilot.pause(0.5)` | Explicit delay for animations or async workers |

### Not required after

| Situation | Why |
|-----------|-----|
| `await pilot.press("a")` then assert | `press()` already waited |
| Two consecutive `pause()` calls | Second is redundant (unless comment explains why) |

### Guideline

If removing a `pause()` makes a test flaky, add it back with a comment explaining why.
Never leave two consecutive bare `pause()` calls without justification.

## `editor.text` Direct Assignment vs `pilot.press()`: Race Condition Warning

`editor.text = "..."` changes the `CodeEditor` reactive property but does **not**
update the rendered content of the underlying `TextArea` widget.

### Safe: reactive-layer tests

```python
editor.text = "modified\n"
await pilot.pause()
assert editor.title.endswith("*")  # reactive metadata only
```

### Dangerous: when `has_unsaved_pane()` must return True

After `pilot.pause()`, Textual may process `TextArea.Changed` and overwrite
`editor.text` with the original content, causing `has_unsaved_pane()` to return False.

```python
# BAD — race condition
editor.text = "modified\n"
await pilot.pause()
app.action_quit()  # modal may not appear

# GOOD — full TextArea flow
await pilot.press("x")
await pilot.pause()
app.action_quit()  # modal appears reliably
```

### Rule of thumb

- Testing reactive metadata (title, unsaved marker) → `editor.text =` is fine
- Testing user-facing flows that depend on "file is modified" → use `pilot.press()`
- Snapshot capturing modified text in the editor area → use `pilot.press()`

## Input Widget: Direct Value Assignment vs Character Typing

For `Input` widgets (find bar, replace bar, modals), prefer direct `value` assignment
over character-by-character `pilot.press()` when the test only needs the **result**.

```python
# SLOW — one event-loop cycle per character
for ch in "search term":
    await pilot.press(ch)

# FAST — one event-loop cycle total
input_widget.value = "search term"
await pilot.pause()
```

`Input.value` is a Textual reactive property. Setting it directly fires `Input.Changed`
just like typing would. Add `await pilot.pause()` after assignment to let watchers run.

**Keep `pilot.press()` when**: the test verifies the typing process itself (e.g. autocomplete,
incremental search, key-by-key validation).

## Snapshot Tests

### Structure

All snapshot tests live in `tests/test_snapshots.py` and are marked `@pytest.mark.serial`.
They use a fixed terminal size `(120, 40)` and fixed workspace paths under
`/tmp/tc_snapshot_ws/<test_name>/` for deterministic footer content.

### Fixtures

| Fixture | Purpose |
|---------|---------|
| `snapshot_workspace` | Fixed-path workspace (not `tmp_path`) for stable snapshots |
| `snapshot_py_file` | `hello.py` in the snapshot workspace |
| `snapshot_json_file` | `data.json` in the snapshot workspace |

### Helpers

| Helper | Purpose |
|--------|---------|
| `_focus_editor(app)` | Returns a `run_before` callback that settles and focuses the editor |
| `_open_editor_modal(app, action_fn)` | Opens a modal triggered from the active editor |
| `_open_app_modal(app, action_fn)` | Opens a modal triggered from the app level |

### Adding a new snapshot

1. Write the test function using `snap_compare`:
   ```python
   def test_snapshot_my_feature(snap_compare, snapshot_workspace, snapshot_py_file):
       app = make_app(snapshot_workspace, open_file=snapshot_py_file)
       assert snap_compare(app, run_before=_focus_editor(app), terminal_size=TERMINAL_SIZE)
   ```
2. Generate the initial SVG:
   ```bash
   uv run pytest tests/test_snapshots.py::test_snapshot_my_feature --snapshot-update
   ```
3. Visually inspect the generated SVG in `tests/__snapshots__/`.
4. Snapshot tests use the **full app** (no `light=True`) because the SVG must include the sidebar.

### Snapshot workspace path stability

Snapshot tests use `/tmp/tc_snapshot_ws/<test_name>/` instead of `tmp_path` so the file
path displayed in the footer is identical across runs. Using `tmp_path` would cause
snapshot failures due to randomized directory names.

## Parallelism and Markers

### `@pytest.mark.serial`

Tests that cannot run in parallel (snapshot tests, tests writing to shared paths).
Run separately with `uv run pytest tests/ -m serial`.

### `-n $(( $(nproc) * 2 ))`

Non-serial tests run in parallel via `pytest-xdist` with 2x CPU cores as workers.
Each worker is a separate process with its own `tmp_path`, so tests are naturally isolated.

## File Watcher Polling in Tests

`CodeEditor.set_interval(2.0, self._poll_file_change)` is disabled in headless mode
(`app.is_headless`). Tests that verify file-change detection call `editor._poll_file_change()`
directly rather than waiting for the timer.

## Tree-Sitter Language Registration in Tests

Custom tree-sitter languages (dockerfile, typescript, etc.) are registered lazily in
`watch_language()` — only when a file of that type is opened. This means opening a `.py`
file does not register the dockerfile grammar. Tests for specific languages should open
a file with the appropriate extension.

## Test File Organization

| File pattern | Tests for |
|-------------|-----------|
| `test_code_editor.py` | CodeEditor widget: language detection, save, close, delete |
| `test_multi_cursor.py` | Multi-cursor editing operations |
| `test_split_view.py` | Split pane management |
| `test_find.py` / `test_replace.py` | Find and replace functionality |
| `test_snapshots.py` | Visual regression (serial only) |
| `test_modals.py` | Modal screens in isolation (lightweight apps) |
| `test_file_watcher.py` | External file change detection |
| `test_light_app.py` | Lightweight app mode (skip_sidebar) validation |
