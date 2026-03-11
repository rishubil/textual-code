"""
Tests for the horizontal split view feature.

Red-Green TDD: written before implementation so all tests initially fail,
then pass once the feature is implemented.
"""

from pathlib import Path

import pytest

from tests.conftest import make_app

# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def py_file(workspace: Path) -> Path:
    f = workspace / "main.py"
    f.write_text("print('hello')\n")
    return f


@pytest.fixture
def py_file2(workspace: Path) -> Path:
    f = workspace / "other.py"
    f.write_text("x = 1\n")
    return f


# ── Group A — Initial State ─────────────────────────────────────────────────────


async def test_right_split_initially_hidden(workspace: Path, py_file: Path):
    """Right TabbedContent starts hidden."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view.right_tabbed_content.display is False


async def test_split_visible_initially_false(workspace: Path, py_file: Path):
    """_split_visible is False on startup."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._split_visible is False


async def test_active_split_initially_left(workspace: Path, py_file: Path):
    """_active_split is 'left' on startup."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._active_split == "left"


async def test_initial_file_tracked_in_left_split(workspace: Path, py_file: Path):
    """File opened on startup is in the left split's tracking."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert py_file in app.main_view._opened_files["left"]


async def test_right_pane_ids_initially_empty(workspace: Path, py_file: Path):
    """Right split has no open panes on startup."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._pane_ids["right"] == set()


# ── Group B — Split Right ────────────────────────────────────────────────────────


async def test_split_right_shows_right_panel(workspace: Path, py_file: Path):
    """action_split_right makes the right panel visible."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view.right_tabbed_content.display is True


async def test_split_right_sets_split_visible(workspace: Path, py_file: Path):
    """action_split_right sets _split_visible to True."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._split_visible is True


async def test_split_right_opens_same_file(workspace: Path, py_file: Path):
    """action_split_right opens the current file in the right panel."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert py_file in app.main_view._opened_files["right"]


async def test_split_right_sets_active_split_to_right(workspace: Path, py_file: Path):
    """action_split_right switches focus to the right split."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._active_split == "right"


async def test_split_right_with_no_file(workspace: Path):
    """action_split_right with no open file opens an empty editor in right."""
    app = make_app(workspace, open_file=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._split_visible is True
        assert len(app.main_view._pane_ids["right"]) == 1


async def test_split_right_twice_reuses_right_panel(workspace: Path, py_file: Path):
    """A second action_split_right reuses the existing right panel.

    If the same file is already open in the right split, it is focused rather
    than opened again (deduplication within a split).
    """
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        first_count = len(app.main_view._pane_ids["right"])
        # Switch back to left and split right again with the same file
        app.main_view._active_split = "left"
        await app.main_view.action_split_right()
        await pilot.pause()
        # Right panel still visible (reused), count unchanged (dedup)
        assert app.main_view._split_visible is True
        assert len(app.main_view._pane_ids["right"]) == first_count


# ── Group C — Focus Navigation ───────────────────────────────────────────────────


async def test_focus_left_split_updates_active_split(workspace: Path, py_file: Path):
    """action_focus_left_split sets _active_split to 'left'."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._active_split == "right"
        app.main_view.action_focus_left_split()
        await pilot.pause()
        assert app.main_view._active_split == "left"


async def test_focus_right_split_when_open(workspace: Path, py_file: Path):
    """action_focus_right_split switches to right when split is visible."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        app.main_view.action_focus_left_split()
        await pilot.pause()
        assert app.main_view._active_split == "left"
        app.main_view.action_focus_right_split()
        await pilot.pause()
        assert app.main_view._active_split == "right"


async def test_focus_right_split_noop_when_closed(workspace: Path, py_file: Path):
    """action_focus_right_split is a no-op when no split is open."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._active_split == "left"
        app.main_view.action_focus_right_split()
        await pilot.pause()
        assert app.main_view._active_split == "left"


# ── Group D — Close Split ────────────────────────────────────────────────────────


async def test_close_split_hides_right_panel(workspace: Path, py_file: Path):
    """action_close_split hides the right panel."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_close_split()
        await pilot.pause()
        assert app.main_view.right_tabbed_content.display is False


async def test_close_split_sets_split_visible_false(workspace: Path, py_file: Path):
    """action_close_split sets _split_visible to False."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_close_split()
        await pilot.pause()
        assert app.main_view._split_visible is False


async def test_close_split_focuses_left(workspace: Path, py_file: Path):
    """action_close_split sets _active_split back to 'left'."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_close_split()
        await pilot.pause()
        assert app.main_view._active_split == "left"


async def test_close_split_clears_right_pane_ids(workspace: Path, py_file: Path):
    """action_close_split removes all right pane tracking."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert len(app.main_view._pane_ids["right"]) > 0
        await app.main_view.action_close_split()
        await pilot.pause()
        assert app.main_view._pane_ids["right"] == set()


async def test_close_split_noop_when_not_open(workspace: Path, py_file: Path):
    """action_close_split does nothing when no split is visible."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.main_view._split_visible
        await app.main_view.action_close_split()  # should not raise
        await pilot.pause()
        assert app.main_view._active_split == "left"


async def test_auto_close_split_when_last_right_tab_closed(
    workspace: Path, py_file: Path
):
    """Closing the last tab in the right split auto-hides the right panel."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._split_visible is True
        # Switch to left so we can close the right editor via its action
        right_editor = app.main_view._get_active_code_editor_in_split("right")
        assert right_editor is not None
        right_editor.action_close()
        await pilot.pause()
        # Right split should now be hidden (auto-closed)
        assert app.main_view._split_visible is False
        assert app.main_view._active_split == "left"


# ── Group E — Split Independence ─────────────────────────────────────────────────


async def test_open_file_goes_to_active_split(workspace: Path, py_file: Path):
    """Opening a file targets the active split."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # File is in left split
        assert py_file in app.main_view._opened_files["left"]
        assert py_file not in app.main_view._opened_files.get("right", {})


async def test_same_file_can_be_open_in_both_splits(workspace: Path, py_file: Path):
    """The same file can be independently open in both splits."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        # File is now in both splits
        assert py_file in app.main_view._opened_files["left"]
        assert py_file in app.main_view._opened_files["right"]
        # But they are different pane instances
        left_pane_id = app.main_view._opened_files["left"][py_file]
        right_pane_id = app.main_view._opened_files["right"][py_file]
        assert left_pane_id != right_pane_id


async def test_split_of_pane_returns_correct_split(workspace: Path, py_file: Path):
    """_split_of_pane returns 'left' for left pane, 'right' for right pane."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        left_pane_id = app.main_view._opened_files["left"][py_file]
        assert app.main_view._split_of_pane(left_pane_id) == "left"

        await app.main_view.action_split_right()
        await pilot.pause()
        right_pane_id = app.main_view._opened_files["right"][py_file]
        assert app.main_view._split_of_pane(right_pane_id) == "right"


async def test_split_of_pane_unknown_returns_none(workspace: Path):
    """_split_of_pane returns None for an unknown pane_id."""
    app = make_app(workspace, open_file=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._split_of_pane("nonexistent-pane-id") is None


async def test_opened_pane_ids_combines_both_splits(workspace: Path, py_file: Path):
    """opened_pane_ids returns pane IDs from both splits combined."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        count_before = len(app.main_view.opened_pane_ids)
        await app.main_view.action_split_right()
        await pilot.pause()
        count_after = len(app.main_view.opened_pane_ids)
        assert count_after == count_before + 1


async def test_close_right_tab_removes_from_right_tracking(
    workspace: Path, py_file: Path
):
    """Closing a tab in the right split removes it from _pane_ids['right']."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        right_pane_id = app.main_view._opened_files["right"][py_file]
        assert right_pane_id in app.main_view._pane_ids["right"]
        right_editor = app.main_view._get_active_code_editor_in_split("right")
        right_editor.action_close()
        await pilot.pause()
        assert right_pane_id not in app.main_view._pane_ids["right"]


# ── Group F — Bindings & Commands ───────────────────────────────────────────────


def test_ctrl_backslash_binding_registered():
    """ctrl+backslash binding is in MainView.BINDINGS."""
    from textual_code.app import MainView

    keys = [b.key for b in MainView.BINDINGS]
    assert "ctrl+backslash" in keys


def test_ctrl_shift_backslash_binding_registered():
    """ctrl+shift+backslash binding is in MainView.BINDINGS."""
    from textual_code.app import MainView

    keys = [b.key for b in MainView.BINDINGS]
    assert "ctrl+shift+backslash" in keys


async def test_ctrl_backslash_key_opens_split(workspace: Path, py_file: Path):
    """Pressing ctrl+backslash triggers action_split_right."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+backslash")
        await pilot.pause()
        assert app.main_view._split_visible is True


async def test_split_right_cmd_no_file(workspace: Path):
    """action_split_right_cmd with no open editor still opens empty right split."""
    app = make_app(workspace, open_file=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Should not raise
        app.action_split_right_cmd()
        await pilot.pause()
