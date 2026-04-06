# Testing Guide: Patterns, Best Practices, and Gotchas

## Running Tests

```bash
# Unit/integration tests — parallel (2x CPU cores)
uv run pytest tests/ -n $(( $(nproc) * 2 )) -m "not serial"

# Snapshot tests — must run serially
uv run pytest tests/ -m serial

# Update snapshots after UI changes
uv run pytest tests/snapshots/test_snapshots.py --snapshot-update

# Single file
uv run pytest tests/editor/test_code_editor.py

# Run tests for a specific domain
uv run pytest tests/vscode/ -n auto -m "not serial"
```

Tests are I/O-bound (event loop waiting), so using 2x CPU cores as workers is optimal.

### Coverage: measuring tested code paths with pytest-cov

```bash
# Run with coverage (single file)
uv run pytest tests/test_cancellable_worker.py --cov --cov-report=term-missing

# Full coverage measurement (mirrors CI)
uv run pytest tests/ -n auto -m "not serial" --cov --cov-report=
uv run pytest tests/ -m serial --cov --cov-append --cov-report=
uv run coverage report --show-missing
```

Configuration lives in `pyproject.toml` under `[tool.coverage.run]` and
`[tool.coverage.report]`.  Key settings: `parallel = true` and
`concurrency = ["multiprocessing"]` ensure subprocess code spawned via
`run_cancellable` is measured.  The `fail_under` threshold is enforced in CI.

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

## Explorer Tree Helpers in `conftest.py`

Shared helpers for explorer tree tests (used by `test_explorer_tree_state.py` and
`test_explorer_file_ops_tree_state.py`):

```python
from tests.conftest import find_tree_node_by_path, get_tree_child_labels

# Get root children labels in display order
labels = get_tree_child_labels(tree)      # → ["dir_a", "file.py"]

# Walk tree to find a node by filesystem path
node = find_tree_node_by_path(tree, path) # → TreeNode | None
```

## User Config Isolation: `_isolate_user_config` autouse fixture

An `autouse` fixture in `conftest.py` monkeypatches `get_user_config_path()` so that
every test reads/writes user settings from a temporary path inside `tmp_path` instead
of the real `~/.config/textual-code/settings.toml`. This prevents a developer's
personal settings (theme, indent size, etc.) from causing test failures.

The fixture patches **both** `textual_code.config` and `textual_code.app` because
`app.py` imports the function with `from textual_code.config import ...`, creating a
separate name binding that a single-module patch would not cover.

Tests that pass an explicit `user_config_path` to `make_app()` or `TextualCode()` are
unaffected — `load_editor_settings()` skips `get_user_config_path()` when a path is
provided.

## File I/O: Always Specify `encoding="utf-8"`

All `Path.write_text()`, `Path.read_text()`, and `open()` calls in tests **must**
include `encoding="utf-8"`.  Without it, Python defaults to the system locale
encoding, which breaks on Windows with non-UTF-8 locales (e.g. cp949 Korean).

```python
# BAD — fails on Windows cp949 locale for non-ASCII content
f.write_text("öçşğü\n")
content = f.read_text()

# GOOD — works on all platforms
f.write_text("öçşğü\n", encoding="utf-8")
content = f.read_text(encoding="utf-8")
```

The ruff rule `PLW1514` enforces this — any `write_text`/`read_text`/`open` call
without `encoding=` will fail lint.  See `tests/config/test_encoding_safety.py` for
regression tests that simulate a cp949 locale via `io.text_encoding` monkeypatch.

## Path Comparison: Use `.as_posix()` for Cross-Platform Safety

When converting `Path` objects to strings for comparison in tests, use
`.as_posix()` instead of `str()`.  `str()` on a `WindowsPath` produces
backslash separators (`with\path\foo.txt`), which breaks assertions that
use hardcoded forward slashes.

```python
# BAD — fails on Windows because str(WindowsPath) uses backslashes
rel_paths = [str(p.relative_to(root)) for p in paths]
assert "src/main.py" in rel_paths  # False on Windows: 'src\\main.py'

# GOOD — .as_posix() always returns forward slashes
rel_paths = [p.relative_to(root).as_posix() for p in paths]
assert "src/main.py" in rel_paths  # True on all platforms
```

## `wait_for_scheduled_animations()` as the Default Settling Call

All tests use `pilot.wait_for_scheduled_animations()` instead of `pilot.pause()` for
event-loop settling.  `wait_for_scheduled_animations()` is strictly more thorough — it
calls `_wait_for_screen()` twice, waits for the animator to complete, and does a full
`wait_for_idle()`.  In contrast, `pilot.pause()` only calls `_wait_for_screen()` once
plus `wait_for_idle(0)`.

### Required after

| Situation | Why |
|-----------|-----|
| `editor.text = "..."` | Reactive property change — watchers need a cycle |
| `action_*()` calls | Actions often schedule deferred work via `call_next` |
| `app.run_test()` entry | First call waits for full app mount |

### Not required after

| Situation | Why |
|-----------|-----|
| `await pilot.press("a")` then assert | `press()` already waited |
| Two consecutive calls | Second is redundant (unless comment explains why) |

### When `pilot.pause(delay=...)` is still needed

Use `pilot.pause(delay=X)` (with a real-time delay) only when waiting for wall-clock
operations like debounce timers or async workers.  Prefer `wait_for_condition()` from
`conftest.py` which combines `wait_for_scheduled_animations()` with a delay-based
retry loop.

### Windows: extra settling often needed

On Windows the event loop processes tab switches, style changes, and modal pushes
slower than on Linux/macOS. A single `wait_for_scheduled_animations()` is frequently
insufficient after:

- `tc.active = pane_id` (tab switch + lazy mount/unmount)
- `styles.width = ...` (layout recalculation + reactive watchers)
- `post_message(...)` followed by `isinstance(app.screen, ...)` (modal push)
- `pilot.click("#button")` on a modal (button must be rendered first)
- `action_close_all()` / `action_close()` (async pane removal)
- `editor.action_find()` / `editor.action_replace()` (find/replace bar rendering)
- `input_widget.value = "..."` before `pilot.click("#next_match")` (input value propagation)
- `pilot.click("#use_regex")` (checkbox reactive state change)
- `widget.focus()` (focus change + footer/explorer sync)

Add a second `await pilot.wait_for_scheduled_animations()` with a comment explaining why.

### Guideline

If removing a settling call makes a test flaky, add it back with a comment explaining why.
Never leave two consecutive bare calls without justification.

## `editor.text` Direct Assignment vs `pilot.press()`: Race Condition Warning

`editor.text = "..."` changes the `CodeEditor` reactive property but does **not**
update the rendered content of the underlying `TextArea` widget.

### Safe: reactive-layer tests

```python
editor.text = "modified\n"
await pilot.wait_for_scheduled_animations()
assert editor.title.endswith("*")  # reactive metadata only
```

### Dangerous: when `has_unsaved_pane()` must return True

After settling, Textual may process `TextArea.Changed` and overwrite
`editor.text` with the original content, causing `has_unsaved_pane()` to return False.

```python
# BAD — race condition
editor.text = "modified\n"
await pilot.wait_for_scheduled_animations()
app.action_quit()  # modal may not appear

# GOOD — full TextArea flow
await pilot.press("x")
await pilot.wait_for_scheduled_animations()
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
await pilot.wait_for_scheduled_animations()
```

`Input.value` is a Textual reactive property. Setting it directly fires `Input.Changed`
just like typing would. Add `await pilot.wait_for_scheduled_animations()` after assignment to let watchers run.

**Keep `pilot.press()` when**: the test verifies the typing process itself (e.g. autocomplete,
incremental search, key-by-key validation).

## Snapshot Tests

### Windows: snapshots are skipped

Snapshot SVG rendering differs between Linux and Windows (path separators, font
metrics). A `pytest_collection_modifyitems` hook in `conftest.py` automatically
skips any test that uses the `snap_compare` fixture on Windows. Snapshot tests
should be verified on Linux CI.

### Structure

All snapshot tests live in `tests/snapshots/test_snapshots.py` and are marked `@pytest.mark.serial`.
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

### Animations are disabled in tests

`make_app()` sets `animation_level = "none"` on every app instance.  This prevents
non-deterministic tab-underline widths and other CSS transitions from causing
snapshot mismatches between runs.  If a test specifically needs animations, override
the level after creating the app:

```python
app = make_app(workspace)
app.animation_level = "full"  # only if testing animation behaviour
```

### Cursor blinking is disabled in snapshot tests

The `snap_compare` fixture in `conftest.py` wraps the upstream fixture to set
`cursor_blink = False` on all `TextArea` and `Input` widgets right before the
screenshot is captured.  This is separate from `animation_level` — cursor blinking
uses a 0.5s timer that runs even in headless mode, so without this wrapper the
cursor may or may not be visible at capture time, causing non-deterministic failures.

The wrapper is transparent: tests use `snap_compare` exactly as before.  Cursor-blink
disable happens automatically before and after `run_before`, and the wrapper finishes
with `_wait_for_stable_screen(pilot)` to ensure the screen is fully settled before
the screenshot is captured.

### Adding a new snapshot

1. Write the test function using `snap_compare`:
   ```python
   def test_snapshot_my_feature(snap_compare, snapshot_workspace, snapshot_py_file):
       app = make_app(snapshot_workspace, open_file=snapshot_py_file)
       assert snap_compare(app, run_before=_focus_editor(app), terminal_size=TERMINAL_SIZE)
   ```
2. Generate the initial SVG:
   ```bash
   uv run pytest tests/snapshots/test_snapshots.py::test_snapshot_my_feature --snapshot-update
   ```
3. Visually inspect the generated SVG in `tests/__snapshots__/`.
4. Snapshot tests use the **full app** (no `light=True`) because the SVG must include the sidebar.

### Snapshot `run_before`: use `wait_for_scheduled_animations()` for settling

All snapshot `run_before` callbacks use `pilot.wait_for_scheduled_animations()`
instead of `pilot.pause()` between actions.  `wait_for_scheduled_animations()` is
strictly more thorough — it calls `_wait_for_screen()` twice, waits for the
animator to complete, and does a full `wait_for_idle()`.

```python
async def run_before(pilot):
    await pilot.wait_for_scheduled_animations()
    editor = app.main_view.get_active_code_editor()
    if editor is not None:
        editor.action_focus()
    await pilot.wait_for_scheduled_animations()
```

The `snap_compare` wrapper automatically calls `_wait_for_stable_screen(pilot)`
after `run_before` completes, so individual callbacks do not need a final
stability check.

### Snapshot tests with split panes

When a snapshot test creates a split and opens files in multiple panes, the active tab
underline can vary between runs.  To stabilise:

```python
# After split + file open, explicitly set active tab on each pane
pane_ids = dtc.get_ordered_pane_ids()
if pane_ids:
    dtc.active = pane_ids[0]
await _wait_for_stable_screen(pilot, stability_count=3)
```

### Screen stability wait: `_wait_for_stable_screen` for complex async operations

When a snapshot test triggers **cascading deferred work** — markdown preview rendering,
split creation with pane moves, threaded workers, or any code path using
`call_after_refresh` — use `_wait_for_stable_screen(pilot)` (defined in
`tests/snapshots/test_snapshots.py`).  It repeatedly calls `wait_for_scheduled_animations()` and
compares consecutive `export_screenshot()` results, returning when the output stabilises.

```python
await app.main_view.action_open_markdown_preview()
await _wait_for_stable_screen(pilot)  # adapts to system speed
```

For multi-phase operations, call it after each phase:

```python
await app.main_view.action_open_markdown_preview()
await _wait_for_stable_screen(pilot)

new_leaf = await app.main_view._create_empty_split("horizontal", "after")
await app.main_view._move_pane_to_leaf(pane_id, new_leaf)
await _wait_for_stable_screen(pilot)

app.main_view._set_active_leaf(left_leaf)
await _wait_for_stable_screen(pilot)
```

For threaded workers (search, image, git diff), use `stability_count=3` to ensure the
worker result is reflected:

```python
pane._run_search()
await _wait_for_stable_screen(pilot, stability_count=3)
```

**When to use:** markdown preview, split + move combos, threaded workers, or any
operation that triggers multiple rounds of `call_after_refresh` / reactive watchers.

**When NOT to use:** simple single-action tests where `wait_for_scheduled_animations()`
suffices.

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

## Explorer `select_file()` in Tests

`Explorer.select_file()` recursively expands collapsed directories using
`call_after_refresh`, with a retry limit (`_MAX_SELECT_RETRIES = 10`).
For deeply nested paths (2+ levels), the retries may exhaust before the tree
finishes loading.  Use polling with re-trigger:

```python
explorer = app.sidebar.query_one(Explorer)
await app.main_view.action_open_code_editor(nested_file)
for attempt in range(100):
    await pilot.wait_for_scheduled_animations()
    node = explorer.directory_tree.cursor_node
    if node is not None and node.data is not None and node.data.path == nested_file:
        break
    # Re-trigger if retries exhausted but tree still loading
    if explorer._pending_path is None and attempt % 10 == 9:
        explorer.select_file(nested_file)
```

## File Watcher Polling in Tests

The central poll timer in `MainView.on_mount()` is skipped in headless mode
(`if not self.app.is_headless`). Tests that verify file-change detection call
`editor._poll_file_change()` directly rather than waiting for the timer.

The same pattern applies to `_poll_editorconfig_change()`. To simulate an `.editorconfig`
file modification, use the `_bump_ec_mtimes(editor)` helper (in `test_editorconfig.py`)
which decrements stored mtimes to force mismatch detection on the next poll call.

## Lazy Tab Mounting: Accessing Editors and Modifying Text

Inactive tabs have their `CodeEditor` removed from the DOM (see internals.md for
details). Tests that need to modify an editor's text — regardless of whether it is
currently mounted — should use the `set_editor_text(main, pane_id, text)` helper
from `conftest.py` instead of accessing `editor.text` directly:

```python
from tests.conftest import set_editor_text

set_editor_text(app.main_view, py_pane_id, "new content\n")
await pilot.wait_for_scheduled_animations()
```

`set_editor_text` updates the mounted editor's `text` reactive (if the editor is in the
DOM) or directly patches `_editor_states[pane_id].text` (if unmounted), keeping both
paths consistent.

## Tree-Sitter Language Registration in Tests

Custom tree-sitter languages (dockerfile, typescript, etc.) are registered lazily in
`watch_language()` — only when a file of that type is opened. This means opening a `.py`
file does not register the dockerfile grammar. Tests for specific languages should open
a file with the appropriate extension.

## Test File Organization

Tests are organized into domain-based subdirectories under `tests/`:

| Directory | Description | Count |
|-----------|-------------|-------|
| `tests/vscode/` | Tests ported from VS Code test suite | 12 |
| `tests/snapshots/` | Visual regression tests (serial only) | 1 |
| `tests/editor/` | Text editing, cursor, selection, indentation | 19 |
| `tests/explorer/` | File browser tree operations | 13 |
| `tests/config/` | Settings, encoding, themes, shortcuts | 17 |
| `tests/find/` | Search, replace, workspace search | 8 |
| `tests/split/` | Split views, resize, drag | 10 |
| `tests/widgets/` | UI components: tabs, sidebar, modals | 20 |
| `tests/app/` | App integration, CLI, file I/O | 10 |

Run tests for a specific domain:
```bash
uv run pytest tests/vscode/ -n auto -m "not serial"
uv run pytest tests/editor/ -n auto -m "not serial"
```
