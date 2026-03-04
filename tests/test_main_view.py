"""
MainView tab management tests.

- Open file → tab created
- Duplicate file prevention
- Multiple files → multiple tabs
- Close tab
- has_unsaved_pane
- focus_pane
"""

from pathlib import Path

from tests.conftest import make_app

# ── Open file → tab created ───────────────────────────────────────────────────


async def test_open_file_creates_tab(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


async def test_duplicate_file_not_reopened(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        await app.main_view.action_open_code_editor(path=sample_py_file)
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


async def test_multiple_different_files_open_multiple_tabs(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 2


# ── Close tab ─────────────────────────────────────────────────────────────────


async def test_close_pane_removes_from_opened_pane_ids(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1
        await pilot.press("ctrl+w")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_nonexistent_pane_returns_false(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        result = await app.main_view.close_pane("nonexistent-pane-id")
        assert result is False


# ── has_unsaved_pane ──────────────────────────────────────────────────────────


async def test_has_unsaved_pane_false_when_clean(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is False


async def test_has_unsaved_pane_true_when_modified(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is True


async def test_has_unsaved_pane_false_after_save(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is True

        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is False


# ── focus_pane ────────────────────────────────────────────────────────────────


async def test_focus_pane_returns_false_for_nonexistent(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        result = app.main_view.focus_pane("nonexistent-id")
        assert result is False


async def test_focus_pane_switches_active_tab(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        py_pane_id = list(app.main_view.opened_pane_ids)[0]

        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 2

        result = app.main_view.focus_pane(py_pane_id)
        await pilot.pause()
        assert result is True
        assert app.main_view.tabbed_content.active == py_pane_id
