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

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pytest_textual_snapshot import SVGImageExtension

from textual_code.app import TextualCode

requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not installed"
)

# Fixed git env for deterministic commits in tests
_GIT_TEST_ENV = {
    "GIT_AUTHOR_DATE": "2025-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2025-01-01T00:00:00+00:00",
}


def init_git_repo(workspace: Path) -> None:
    """Create a git repo with an initial commit containing committed.py.

    Uses fixed author/committer dates for deterministic test output.
    """
    git_env = {**os.environ, **_GIT_TEST_ENV, "HOME": str(workspace)}

    def run(args, **kw):
        return subprocess.run(
            args, cwd=workspace, check=True, capture_output=True, **kw
        )

    run(["git", "init"], env=git_env)
    run(["git", "config", "user.email", "test@test.com"], env=git_env)
    run(["git", "config", "user.name", "Test"], env=git_env)
    (workspace / "committed.py").write_text("# committed\n")
    run(["git", "add", "."], env=git_env)
    run(["git", "commit", "-m", "init"], env=git_env)


# pytest-textual-snapshot 1.0.0 sets _file_extension (underscore prefix) but
# syrupy 5.x looks at file_extension (no prefix), so snapshots fall back to
# ".raw".  Patch the correct attribute so snap_compare produces ".svg" files.
SVGImageExtension.file_extension = "svg"


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


def make_app(
    workspace: Path,
    open_file: Path | None = None,
    user_config_path: Path | None = None,
    light: bool = False,
) -> TextualCode:
    app = TextualCode(
        workspace_path=workspace,
        with_open_file=open_file,
        user_config_path=user_config_path,
        skip_sidebar=light,
    )
    app.animation_level = "none"
    return app


def set_editor_text(main_view, pane_id: str, text: str) -> None:
    """Set editor text for a pane, handling both mounted and unmounted editors.

    With lazy mounting, inactive tabs have their editors stored in
    _editor_states rather than mounted in the DOM.
    """
    from textual_code.widgets.code_editor import CodeEditor

    if pane_id in main_view._editor_states:
        main_view._editor_states[pane_id].text = text
    else:
        tc = main_view._tc_for_pane(pane_id)
        if tc:
            editors = list(tc.get_pane(pane_id).query(CodeEditor))
            if editors:
                editors[0].text = text


def assert_focus_on_leaf(app, main, dest_leaf, new_pane_id, context=""):
    """Assert that focus is correctly on dest_leaf and the moved tab."""
    from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
    from textual_code.widgets.split_tree import all_leaves

    tree_info = f" (leaves={[lf.leaf_id for lf in all_leaves(main._split_root)]})"
    msg = f"{context}{tree_info}"
    assert main._active_leaf_id == dest_leaf.leaf_id, (
        f"active_leaf_id mismatch: {main._active_leaf_id} != {dest_leaf.leaf_id}{msg}"
    )
    tc = main.query_one(f"#{dest_leaf.leaf_id}", DraggableTabbedContent)
    assert tc.active == new_pane_id, (
        f"tc.active mismatch: {tc.active} != {new_pane_id}{msg}"
    )
    focused = app.focused
    assert focused is not None, f"No focused widget{msg}"
    is_descendant = any(ancestor is tc for ancestor in focused.ancestors_with_self)
    assert is_descendant, (
        f"focused widget {focused!r} is not a descendant of dest TC {tc.id}{msg}"
    )


@pytest.fixture()
def restore_bindings():
    """Restore class-level BINDINGS after tests that patch them."""
    from textual_code.app import MainView, TextualCode
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

    backup = {
        cls: list(cls.BINDINGS) for cls in (MainView, TextualCode, MultiCursorTextArea)
    }
    yield
    for cls, bindings in backup.items():
        cls.BINDINGS[:] = bindings
