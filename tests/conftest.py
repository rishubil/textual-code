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

import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_textual_snapshot import SVGImageExtension

from textual_code.app import TextualCode

requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not installed"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip snapshot tests on Windows — SVG rendering differs across platforms."""
    if sys.platform != "win32":
        return
    skip_win = pytest.mark.skip(
        reason="Snapshot SVG rendering differs on Windows — run on Linux CI",
    )
    for item in items:
        if isinstance(item, pytest.Function) and "snap_compare" in item.fixturenames:
            item.add_marker(skip_win)


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


def git_add_commit(workspace: Path, message: str = "update") -> None:
    """Stage all changes and commit with a deterministic timestamp."""
    git_env = {**os.environ, **_GIT_TEST_ENV, "HOME": str(workspace)}

    def run(args):
        return subprocess.run(
            args, cwd=workspace, check=True, capture_output=True, env=git_env
        )

    run(["git", "add", "."])
    run(["git", "commit", "-m", message])


# pytest-textual-snapshot 1.0.0 sets _file_extension (underscore prefix) but
# syrupy 5.x looks at file_extension (no prefix), so snapshots fall back to
# ".raw".  Patch the correct attribute so snap_compare produces ".svg" files.
SVGImageExtension.file_extension = "svg"


def _disable_cursor_blink(app) -> None:
    """Turn off cursor blinking on all TextArea and Input widgets."""
    from textual.widgets import Input, TextArea

    for widget in app.query(TextArea):
        widget.cursor_blink = False
    for widget in app.query(Input):
        widget.cursor_blink = False


def find_tree_node_by_path(tree, path: Path):
    """Recursively find a tree node matching the given path.

    Walks the tree starting from root, returning the first node whose
    ``data.path`` matches *path*, or ``None`` if no match is found.

    Shared by explorer tree state and file-ops tree state tests.
    """

    def walk(node):
        if node.data is not None and node.data.path == path:
            return node
        for child in node.children:
            result = walk(child)
            if result is not None:
                return result
        return None

    return walk(tree.root)


def get_tree_child_labels(tree) -> list[str]:
    """Return labels of the root's direct children in display order.

    Shared by explorer tree state tests.
    """
    return [str(child.label) for child in tree.root.children]


@pytest.fixture
def snap_compare(snap_compare):
    """Wrap snap_compare to disable cursor blinking for deterministic snapshots.

    TextArea and Input widgets blink the cursor via a 0.5s timer by default.
    This timer is independent of ``animation_level`` and can cause snapshot
    differences depending on whether the cursor is visible at capture time.

    Cursor blink is disabled both *before* and *after* ``run_before`` so that
    any stability-polling helpers (e.g. ``_wait_for_stable_screen``) inside
    ``run_before`` see deterministic output, and widgets mounted during
    ``run_before`` are also covered.

    Depends on pytest-textual-snapshot's snap_compare signature:
        compare(app, *, press, terminal_size, run_before)
    """

    def wrapper(app, *, run_before=None, **kwargs):
        from tests.snapshots.test_snapshots import _wait_for_stable_screen

        async def run_before_no_blink(pilot):
            _disable_cursor_blink(pilot.app)
            if run_before is not None:
                await run_before(pilot)
            _disable_cursor_blink(pilot.app)
            await _wait_for_stable_screen(pilot)

        return snap_compare(app, run_before=run_before_no_blink, **kwargs)

    return wrapper


MINI_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "2mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)
"""Minimal valid 1x1 red PNG encoded as base64 (67 bytes decoded)."""


def make_png(path: Path) -> Path:
    """Write a minimal valid PNG to *path* and return it."""
    path.write_bytes(base64.b64decode(MINI_PNG_B64))
    return path


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


async def await_workers(pilot) -> None:
    """Wait until all running Textual workers finish.

    On Windows, ``run_cancellable`` uses ``multiprocessing.spawn`` (~80-400 ms
    startup).  Fire-and-forget ``@work`` methods may still be running when
    ``wait_for_scheduled_animations()`` returns.  Call this helper after
    animations to ensure subprocess-based workers have completed.

    On Linux with ``fork``, workers complete near-instantly so this returns
    immediately with negligible overhead.
    """
    import asyncio

    for _ in range(200):  # up to ~2 s
        if not any(w.is_running for w in pilot.app.workers):
            return
        await asyncio.sleep(0.01)


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


@pytest.fixture(autouse=True)
def _isolate_user_config(tmp_path, monkeypatch):
    """Prevent real user settings from affecting tests (#16).

    Patches both modules because app.py uses ``from textual_code.config import
    get_user_config_path``, creating a local name binding that a single patch
    on ``textual_code.config`` would not cover.
    """
    fake = tmp_path / "_test_user_settings.toml"
    monkeypatch.setattr("textual_code.config.get_user_config_path", lambda: fake)
    monkeypatch.setattr("textual_code.app.get_user_config_path", lambda: fake)


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
        cls.BINDINGS = bindings


# ── Condition-based wait helper ──────────────────────────────────────────────


async def wait_for_condition(
    pilot,
    condition,
    *,
    max_retries: int = 20,
    delay: float = 0.1,
    msg: str = "Condition not met after retries",
):
    """Wait until *condition()* returns truthy, with real-time delay between retries.

    Each retry iteration first calls ``wait_for_scheduled_animations()`` to
    drain pending messages and complete any running/scheduled animations, then
    ``pilot.pause(delay=...)`` to insert a real wall-clock ``asyncio.sleep()``
    that gives workers and async mounts time to finish (especially on Windows
    CI where the event loop can be CPU-idle while work is still in progress).

    Args:
        pilot: The Textual Pilot instance.
        condition: A callable (sync or async) returning a truthy value on success.
        max_retries: Maximum number of pause-retry cycles.
        delay: Seconds of real-time delay per retry (default 0.1 s).
        msg: Assertion message if the condition is never met.

    Returns:
        The truthy value returned by *condition*.

    Raises:
        AssertionError: If the condition is not met within *max_retries*.
    """
    import inspect

    last_exc: Exception | None = None
    for _ in range(max_retries):
        try:
            result = condition()
            if inspect.isawaitable(result):
                result = await result
            if result:
                return result
        except Exception as exc:
            last_exc = exc
        await pilot.wait_for_scheduled_animations()
        await pilot.pause(delay=delay)
    if last_exc is not None:
        raise AssertionError(msg) from last_exc
    raise AssertionError(msg)


# ── Strip style inspection helpers ────────────────────────────────────────────


def get_style_color_at(
    strip, gutter_width: int, content_col: int, attr: str = "color"
) -> str | None:
    """Return the foreground or background color (as string) at a content column.

    Args:
        strip: Rendered Strip from ``_render_line()``.
        gutter_width: Number of gutter cells to skip.
        content_col: Content-relative column to inspect.
        attr: ``"color"`` for foreground, ``"bgcolor"`` for background.
    """
    from rich.segment import Segment

    cell_pos = 0
    for seg in strip:
        text = seg.text if isinstance(seg, Segment) else str(seg)
        style = seg.style if isinstance(seg, Segment) else None
        for _ch in text:
            if cell_pos >= gutter_width and cell_pos - gutter_width == content_col:
                if style:
                    value = getattr(style, attr, None)
                    return str(value) if value else None
                return None
            cell_pos += 1
    return None
