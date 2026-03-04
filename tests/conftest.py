"""
Shared fixtures for the textual-code test suite.

== Rule: editor.text direct assignment vs pilot.press() in snapshot tests ==

`editor.text = "..."` changes the CodeEditor reactive property but does NOT
update the underlying TextArea widget's rendered content.

Use `editor.text = "..."` when:
- Testing metadata that depends only on the reactive value (e.g. the unsaved
  marker "*" in the tab title, or has_unsaved_pane() return value).
- The snapshot is intentionally showing the original TextArea content while
  only testing title/state changes.
- Stability is important and cursor movement would introduce visual noise.

Use `await pilot.press(...)` when:
- The snapshot needs to show the modified text in the editor area (e.g. for
  snapshots of modals that open *because* the file is unsaved, where
  `has_unsaved_pane()` must return True after the keypress).
- Testing the full user-facing editing flow.

In all *unit* tests (test_code_editor, test_main_view, test_app) direct
assignment is acceptable: those tests exercise the CodeEditor reactive layer
in isolation and do not capture screenshots.
"""

from pathlib import Path

import pytest

from textual_code.app import TextualCode


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sample_py_file(workspace: Path) -> Path:
    f = workspace / "hello.py"
    f.write_text("print('hello')\n")
    return f


@pytest.fixture
def sample_json_file(workspace: Path) -> Path:
    f = workspace / "data.json"
    f.write_text('{"key": "value"}\n')
    return f


@pytest.fixture
def multiline_file(workspace: Path) -> Path:
    f = workspace / "multiline.txt"
    f.write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n")
    return f


# Snapshot tests use a fixed, per-test workspace path so the footer path
# display is stable across runs and doesn't cause false snapshot failures.
# Each test gets its own subdirectory named after the test function.
_SNAPSHOT_WS_ROOT = Path("/tmp/tc_snapshot_ws")


@pytest.fixture
def snapshot_workspace(request) -> Path:
    ws = _SNAPSHOT_WS_ROOT / request.node.name
    # Clean up before creating to ensure a fresh directory each run.
    import shutil

    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    return ws


@pytest.fixture
def snapshot_py_file(snapshot_workspace: Path) -> Path:
    f = snapshot_workspace / "hello.py"
    f.write_text("print('hello')\n")
    return f


@pytest.fixture
def snapshot_json_file(snapshot_workspace: Path) -> Path:
    f = snapshot_workspace / "data.json"
    f.write_text('{"key": "value"}\n')
    return f


def make_app(workspace: Path, open_file: Path | None = None) -> TextualCode:
    return TextualCode(workspace_path=workspace, with_open_file=open_file)
