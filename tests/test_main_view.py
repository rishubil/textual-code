"""
MainView tab management tests.

- Open file → tab created
- Duplicate file prevention
- Multiple files → multiple tabs
- Close tab
- has_unsaved_pane
- focus_pane
- save_all
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.modals import (
    SaveAsModalResult,
    SaveAsModalScreen,
    UnsavedChangeModalResult,
    UnsavedChangeModalScreen,
)
from textual_code.widgets.code_editor import CodeEditor

# ── Open file → tab created ───────────────────────────────────────────────────


async def test_open_file_creates_tab(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


async def test_duplicate_file_not_reopened(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        await app.main_view.action_open_code_editor(path=sample_py_file)
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


async def test_multiple_different_files_open_multiple_tabs(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
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
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1
        await pilot.press("ctrl+w")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_nonexistent_pane_returns_false(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        result = await app.main_view.close_pane("nonexistent-pane-id")
        assert result is False


# ── has_unsaved_pane ──────────────────────────────────────────────────────────


async def test_has_unsaved_pane_false_when_clean(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is False


async def test_has_unsaved_pane_true_when_modified(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is True


async def test_has_unsaved_pane_false_after_save(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
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
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        result = app.main_view.focus_pane("nonexistent-id")
        assert result is False


async def test_focus_pane_switches_active_tab(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
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


# ── save_all ──────────────────────────────────────────────────────────────────


async def test_save_all_noop_when_no_files_open(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Should not raise any error
        app.main_view.action_save_all()
        await pilot.pause()


async def test_save_all_noop_when_all_clean(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is False
        app.main_view.action_save_all()
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is False


async def test_save_all_saves_single_modified_file(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is True

        app.main_view.action_save_all()
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is False
        assert sample_py_file.read_text() == "modified\n"


async def test_save_all_saves_all_of_two_modified(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        for pane_id in list(app.main_view.opened_pane_ids):
            pane = app.main_view.tabbed_content.get_pane(pane_id)
            pane.query_one(CodeEditor).text = "modified\n"
        await pilot.pause()

        assert app.main_view.has_unsaved_pane() is True
        app.main_view.action_save_all()
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is False
        assert sample_py_file.read_text() == "modified\n"
        assert sample_json_file.read_text() == "modified\n"


async def test_save_all_saves_only_modified_among_three(workspace: Path):
    file_a = workspace / "a.py"
    file_b = workspace / "b.py"
    file_c = workspace / "c.py"
    file_a.write_text("original_a\n")
    file_b.write_text("original_b\n")
    file_c.write_text("original_c\n")

    app = make_app(workspace, light=True, open_file=file_a)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=file_b)
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=file_c)
        await pilot.pause()

        pane_id_a = app.main_view.pane_id_from_path(file_a)
        pane_id_b = app.main_view.pane_id_from_path(file_b)
        assert pane_id_a is not None
        assert pane_id_b is not None
        app.main_view.tabbed_content.get_pane(pane_id_a).query_one(
            CodeEditor
        ).text = "modified_a\n"
        app.main_view.tabbed_content.get_pane(pane_id_b).query_one(
            CodeEditor
        ).text = "modified_b\n"
        await pilot.pause()

        app.main_view.action_save_all()
        await pilot.pause()
        assert file_a.read_text() == "modified_a\n"
        assert file_b.read_text() == "modified_b\n"
        assert file_c.read_text() == "original_c\n"


async def test_save_all_saves_all_of_three_modified(workspace: Path):
    file_a = workspace / "a.py"
    file_b = workspace / "b.py"
    file_c = workspace / "c.py"
    file_a.write_text("original_a\n")
    file_b.write_text("original_b\n")
    file_c.write_text("original_c\n")

    app = make_app(workspace, light=True, open_file=file_a)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=file_b)
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=file_c)
        await pilot.pause()

        for pane_id in list(app.main_view.opened_pane_ids):
            pane = app.main_view.tabbed_content.get_pane(pane_id)
            pane.query_one(CodeEditor).text = "modified\n"
        await pilot.pause()

        assert app.main_view.has_unsaved_pane() is True
        app.main_view.action_save_all()
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is False
        assert file_a.read_text() == "modified\n"
        assert file_b.read_text() == "modified\n"
        assert file_c.read_text() == "modified\n"


async def test_save_all_shows_save_as_for_single_untitled(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        pane_id = await app.main_view.open_code_editor_pane(path=None)
        await pilot.pause()

        pane = app.main_view.tabbed_content.get_pane(pane_id)
        pane.query_one(CodeEditor).text = "modified\n"
        await pilot.pause()

        main_view = app.main_view
        main_view.action_save_all()
        await pilot.pause()

        assert isinstance(app.screen, SaveAsModalScreen)
        assert main_view.tabbed_content.active == pane_id

        # Dismiss modal so app can shut down cleanly
        app.screen.dismiss(SaveAsModalResult(is_cancelled=True, file_path=None))
        await pilot.pause()


async def test_save_all_mixed_saves_file_then_shows_save_as(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"

        untitled_pane_id = await app.main_view.open_code_editor_pane(path=None)
        await pilot.pause()
        app.main_view.tabbed_content.get_pane(untitled_pane_id).query_one(
            CodeEditor
        ).text = "untitled modified\n"
        await pilot.pause()

        main_view = app.main_view
        main_view.action_save_all()
        await pilot.pause()

        # File with path should be saved before showing modal for untitled
        assert sample_py_file.read_text() == "modified\n"
        assert isinstance(app.screen, SaveAsModalScreen)

        # Dismiss modal so app can shut down cleanly
        app.screen.dismiss(SaveAsModalResult(is_cancelled=True, file_path=None))
        await pilot.pause()


async def test_save_all_three_mixed_saves_two_files_shows_save_as(workspace: Path):
    file_a = workspace / "a.py"
    file_b = workspace / "b.py"
    file_a.write_text("original_a\n")
    file_b.write_text("original_b\n")

    app = make_app(workspace, light=True, open_file=file_a)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=file_b)
        await pilot.pause()
        untitled_pane_id = await app.main_view.open_code_editor_pane(path=None)
        await pilot.pause()

        pane_id_a = app.main_view.pane_id_from_path(file_a)
        pane_id_b = app.main_view.pane_id_from_path(file_b)
        assert pane_id_a is not None
        assert pane_id_b is not None
        app.main_view.tabbed_content.get_pane(pane_id_a).query_one(
            CodeEditor
        ).text = "modified_a\n"
        app.main_view.tabbed_content.get_pane(pane_id_b).query_one(
            CodeEditor
        ).text = "modified_b\n"
        app.main_view.tabbed_content.get_pane(untitled_pane_id).query_one(
            CodeEditor
        ).text = "untitled modified\n"
        await pilot.pause()

        main_view = app.main_view
        main_view.action_save_all()
        await pilot.pause()

        assert file_a.read_text() == "modified_a\n"
        assert file_b.read_text() == "modified_b\n"
        assert isinstance(app.screen, SaveAsModalScreen)

        # Dismiss modal so app can shut down cleanly
        app.screen.dismiss(SaveAsModalResult(is_cancelled=True, file_path=None))
        await pilot.pause()


async def test_save_all_sequential_multiple_untitled(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        pane_ids = []
        for _ in range(3):
            pane_id = await app.main_view.open_code_editor_pane(path=None)
            pane_ids.append(pane_id)
        await pilot.pause()

        for pane_id in pane_ids:
            app.main_view.tabbed_content.get_pane(pane_id).query_one(
                CodeEditor
            ).text = "modified\n"
        await pilot.pause()

        main_view = app.main_view
        main_view.action_save_all()
        await pilot.pause()

        # First modal should be shown
        assert isinstance(app.screen, SaveAsModalScreen)
        first_active = main_view.tabbed_content.active

        # Simulate completing the first modal (cancel → on_complete still fires)
        app.screen.dismiss(SaveAsModalResult(is_cancelled=True, file_path=None))
        await pilot.pause()

        # Second modal should appear (sequential, not concurrent)
        assert isinstance(app.screen, SaveAsModalScreen)
        second_active = main_view.tabbed_content.active

        assert first_active != second_active

        # Dismiss second modal → third modal opens
        app.screen.dismiss(SaveAsModalResult(is_cancelled=True, file_path=None))
        await pilot.pause()

        # Dismiss third modal so app can shut down cleanly
        assert isinstance(app.screen, SaveAsModalScreen)
        app.screen.dismiss(SaveAsModalResult(is_cancelled=True, file_path=None))
        await pilot.pause()


async def test_save_all_files_via_app_action(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is True

        app.action_save_all_files()
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is False
        assert sample_py_file.read_text() == "modified\n"


async def test_ctrl_shift_s_triggers_save_all(workspace: Path, sample_py_file: Path):
    """Ctrl+Shift+S saves all modified files."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "via_shortcut\n"
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is True

        await pilot.press("ctrl+shift+s")
        await pilot.pause()
        assert app.main_view.has_unsaved_pane() is False

    assert sample_py_file.read_text() == "via_shortcut\n"


async def test_save_all_clean_untitled_no_modal(workspace: Path):
    """A clean (unmodified) untitled file is skipped by save_all — no modal."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.open_code_editor_pane(path=None)
        await pilot.pause()
        # Untitled file is clean (text == initial_text == "")

        app.main_view.action_save_all()
        await pilot.pause()

        # No modal should appear for a clean untitled file
        from textual_code.modals import SaveAsModalScreen

        assert not isinstance(app.screen, SaveAsModalScreen)


async def test_save_all_idempotent_on_already_saved(
    workspace: Path, sample_py_file: Path
):
    """Calling save_all twice on already-saved files has no side effects."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "first_write\n"
        await pilot.pause()

        app.main_view.action_save_all()
        await pilot.pause()
        assert sample_py_file.read_text() == "first_write\n"

        # Second call — nothing modified, nothing to save
        app.main_view.action_save_all()
        await pilot.pause()
        assert sample_py_file.read_text() == "first_write\n"
        assert app.main_view.has_unsaved_pane() is False


# ── close_all ──────────────────────────────────────────────────────────────────


async def test_close_all_noop_when_no_files_open(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.main_view.action_close_all()
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_all_closes_single_clean_file(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        app.main_view.action_close_all()
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_all_closes_all_clean_files(workspace: Path):
    file_a = workspace / "a.py"
    file_b = workspace / "b.py"
    file_c = workspace / "c.py"
    file_a.write_text("a\n")
    file_b.write_text("b\n")
    file_c.write_text("c\n")

    app = make_app(workspace, light=True, open_file=file_a)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=file_b)
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=file_c)
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 3

        app.main_view.action_close_all()
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_all_single_unsaved_shows_modal(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.pause()

        app.main_view.action_close_all()
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeModalScreen)

        # Dismiss modal to allow app to shut down cleanly
        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=True, should_save=None)
        )
        await pilot.pause()


async def test_close_all_single_unsaved_save_closes(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.pause()

        app.main_view.action_close_all()
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeModalScreen)

        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=False, should_save=True)
        )
        await pilot.pause()

        assert sample_py_file.read_text() == "modified\n"
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_all_single_unsaved_dont_save_closes(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.pause()

        app.main_view.action_close_all()
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeModalScreen)

        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=False, should_save=False)
        )
        await pilot.pause()

        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_all_single_unsaved_cancel_stops(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.pause()

        app.main_view.action_close_all()
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeModalScreen)

        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=True, should_save=None)
        )
        await pilot.pause()

        assert len(app.main_view.opened_pane_ids) == 1


async def test_close_all_mixed_clean_and_dirty(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        # Dirty the json file only
        json_pane_id = app.main_view.pane_id_from_path(sample_json_file)
        assert json_pane_id is not None
        app.main_view.tabbed_content.get_pane(json_pane_id).query_one(
            CodeEditor
        ).text = "modified\n"
        await pilot.pause()

        assert len(app.main_view.opened_pane_ids) == 2

        app.main_view.action_close_all()
        await pilot.pause()

        # Modal should appear for the dirty file
        assert isinstance(app.screen, UnsavedChangeModalScreen)
        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=False, should_save=False)
        )
        await pilot.pause()

        # Both files should be closed
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_all_cancel_stops_remaining(workspace: Path):
    file_a = workspace / "a.py"
    file_b = workspace / "b.py"
    file_c = workspace / "c.py"
    file_a.write_text("a\n")
    file_b.write_text("b\n")
    file_c.write_text("c\n")

    app = make_app(workspace, light=True, open_file=file_a)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=file_b)
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=file_c)
        await pilot.pause()

        # Dirty all 3 files
        for pane_id in list(app.main_view.opened_pane_ids):
            pane = app.main_view.tabbed_content.get_pane(pane_id)
            pane.query_one(CodeEditor).text = "modified\n"
        await pilot.pause()

        assert len(app.main_view.opened_pane_ids) == 3

        app.main_view.action_close_all()
        await pilot.pause()

        # 1st modal: Don't save → closes 1st file
        assert isinstance(app.screen, UnsavedChangeModalScreen)
        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=False, should_save=False)
        )
        await pilot.pause()

        # 2nd modal: Cancel → stops
        assert isinstance(app.screen, UnsavedChangeModalScreen)
        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=True, should_save=None)
        )
        await pilot.pause()

        # 2 files remain (3 - 1 = 2)
        assert len(app.main_view.opened_pane_ids) == 2


async def test_close_all_sequential_multiple_unsaved(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        # Dirty both files
        for pane_id in list(app.main_view.opened_pane_ids):
            pane = app.main_view.tabbed_content.get_pane(pane_id)
            pane.query_one(CodeEditor).text = "modified\n"
        await pilot.pause()

        app.main_view.action_close_all()
        await pilot.pause()

        # 1st modal appears
        assert isinstance(app.screen, UnsavedChangeModalScreen)
        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=False, should_save=False)
        )
        await pilot.pause()

        # After 1st Don't save: 1st file closed, 2nd modal appears (sequential)
        assert isinstance(app.screen, UnsavedChangeModalScreen)
        assert len(app.main_view.opened_pane_ids) == 1

        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=False, should_save=False)
        )
        await pilot.pause()

        # Both files now closed
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_all_untitled_unsaved_save_shows_error(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        pane_id = await app.main_view.open_code_editor_pane(path=None)
        await pilot.pause()

        pane = app.main_view.tabbed_content.get_pane(pane_id)
        pane.query_one(CodeEditor).text = "modified\n"
        await pilot.pause()

        app.main_view.action_close_all()
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeModalScreen)

        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=False, should_save=True)
        )
        await pilot.pause()

        # Tab should NOT be closed (no path to save to)
        assert len(app.main_view.opened_pane_ids) == 1


async def test_close_all_untitled_dont_save_closes(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        pane_id = await app.main_view.open_code_editor_pane(path=None)
        await pilot.pause()

        pane = app.main_view.tabbed_content.get_pane(pane_id)
        pane.query_one(CodeEditor).text = "modified\n"
        await pilot.pause()

        app.main_view.action_close_all()
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeModalScreen)

        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=False, should_save=False)
        )
        await pilot.pause()

        assert len(app.main_view.opened_pane_ids) == 0


async def test_ctrl_shift_w_triggers_close_all(workspace: Path, sample_py_file: Path):
    """Ctrl+Shift+W closes all clean files without prompting."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        await pilot.press("ctrl+shift+w")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_all_clears_opened_files_dict(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """After close_all, opened_files dict is empty."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()
        assert len(app.main_view.opened_files) == 2

        app.main_view.action_close_all()
        await pilot.pause()
        assert len(app.main_view.opened_files) == 0


async def test_close_all_allows_reopen_same_file(workspace: Path, sample_py_file: Path):
    """After close_all, the same file can be reopened."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        app.main_view.action_close_all()
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0
        assert app.main_view.pane_id_from_path(sample_py_file) is None

        await app.main_view.action_open_code_editor(path=sample_py_file)
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


async def test_close_all_all_dirty_save_all_writes_to_disk(workspace: Path):
    """close_all with Save on each dirty file persists content to disk."""
    file_a = workspace / "a.py"
    file_b = workspace / "b.py"
    file_a.write_text("original_a\n")
    file_b.write_text("original_b\n")

    app = make_app(workspace, light=True, open_file=file_a)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=file_b)
        await pilot.pause()

        pane_id_a = app.main_view.pane_id_from_path(file_a)
        pane_id_b = app.main_view.pane_id_from_path(file_b)
        assert pane_id_a and pane_id_b
        app.main_view.tabbed_content.get_pane(pane_id_a).query_one(
            CodeEditor
        ).text = "saved_a\n"
        app.main_view.tabbed_content.get_pane(pane_id_b).query_one(
            CodeEditor
        ).text = "saved_b\n"
        await pilot.pause()

        app.main_view.action_close_all()
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeModalScreen)
        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=False, should_save=True)
        )
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeModalScreen)
        app.screen.dismiss(
            UnsavedChangeModalResult(is_cancelled=False, should_save=True)
        )
        await pilot.pause()

        assert len(app.main_view.opened_pane_ids) == 0

    assert file_a.read_text() == "saved_a\n"
    assert file_b.read_text() == "saved_b\n"
