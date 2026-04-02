"""
CodeEditor widget tests.

- Language detection
- Title reactive (untitled, filename, unsaved marker)
- Basic text editing
- Save (save / save as)
- Close
- Delete
- Footer display
"""

import asyncio
from pathlib import Path

import pytest
from textual.widgets import Input

from tests.conftest import make_app
from textual_code.modals import (
    DeleteFileModalScreen,
    GotoLineModalScreen,
    LargeFileConfirmModalScreen,
    SaveAsModalScreen,
    UnsavedChangeModalScreen,
)
from textual_code.widgets.code_editor import CodeEditorFooter

# ── Language detection ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "filename,expected_lang",
    [
        ("file.py", "python"),
        ("file.json", "json"),
        ("file.md", "markdown"),
        ("file.markdown", "markdown"),
        ("file.yaml", "yaml"),
        ("file.yml", "yaml"),
        ("file.toml", "toml"),
        ("file.rs", "rust"),
        ("file.html", "html"),
        ("file.htm", "html"),
        ("file.css", "css"),
        ("file.xml", "xml"),
        ("file.regex", "regex"),
        ("file.sql", "sql"),
        ("file.js", "javascript"),
        ("file.java", "java"),
        ("file.sh", "bash"),
        ("file.go", "go"),
        ("file.unknown", None),
        ("file", None),
        # custom languages via tree-sitter-language-pack
        ("Dockerfile", "dockerfile"),
        ("file.dockerfile", "dockerfile"),
        ("file.ts", "typescript"),
        ("file.tsx", "tsx"),
        ("file.c", "c"),
        ("file.h", "c"),
        ("file.cpp", "cpp"),
        ("file.cc", "cpp"),
        ("file.cxx", "cpp"),
        ("file.hpp", "cpp"),
        ("file.rb", "ruby"),
        ("file.kt", "kotlin"),
        ("file.kts", "kotlin"),
        ("file.lua", "lua"),
        ("file.php", "php"),
        ("Makefile", "make"),
        ("makefile", "make"),
        ("GNUmakefile", "make"),
        ("file.mk", "make"),
    ],
)
async def test_language_detection(
    filename: str, expected_lang: str | None, workspace: Path
):
    f = workspace / filename
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language == expected_lang


async def test_custom_language_registered(workspace: Path):
    """Opening a Dockerfile registers 'dockerfile' as an available language."""
    f = workspace / "Dockerfile"
    f.write_text("FROM ubuntu:22.04\nRUN apt-get update\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert "dockerfile" in editor.editor.available_languages


# ── Title reactive ────────────────────────────────────────────────────────────


async def test_title_untitled_when_no_path(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.title == "<Untitled>"


async def test_title_shows_filename(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.title == "hello.py"


async def test_title_has_asterisk_when_modified(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified content\n"
        await pilot.wait_for_scheduled_animations()
        assert editor.title == "hello.py*"


async def test_title_asterisk_removed_after_save(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.wait_for_scheduled_animations()
        assert "*" in editor.title

        await pilot.press("ctrl+s")
        await pilot.wait_for_scheduled_animations()
        assert "*" not in editor.title


# ── Basic text editing ────────────────────────────────────────────────────────


async def test_initial_text_loaded_from_file(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.text == "print('hello')\n"
        assert editor.initial_text == "print('hello')\n"


async def test_text_reactive_reflects_edit(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "new content\n"
        await pilot.wait_for_scheduled_animations()
        assert editor.text == "new content\n"
        assert editor.initial_text == "print('hello')\n"


# ── Save ──────────────────────────────────────────────────────────────────────


async def test_save_writes_to_disk(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "print('modified')\n"
        await pilot.press("ctrl+s")
        await pilot.wait_for_scheduled_animations()

    assert sample_py_file.read_text(encoding="utf-8") == "print('modified')\n"


async def test_save_updates_initial_text(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "updated\n"
        await pilot.press("ctrl+s")
        await pilot.wait_for_scheduled_animations()
        assert editor.initial_text == "updated\n"
        assert editor.text == editor.initial_text


async def test_save_without_path_triggers_save_as_modal(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+s")
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, SaveAsModalScreen)


# ── Save As ───────────────────────────────────────────────────────────────────


async def test_save_as_creates_new_file(workspace: Path, sample_py_file: Path):
    new_path = workspace / "new_file.py"
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_save_as()
        await pilot.wait_for_scheduled_animations()

        input_widget = app.screen.query_one("#path", Input)
        input_widget.value = str(new_path)
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#save")
        await pilot.wait_for_scheduled_animations()

    assert new_path.exists()


# ── Close ─────────────────────────────────────────────────────────────────────


async def test_close_clean_editor_with_ctrl_w(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view.opened_pane_ids) == 1
        await pilot.press("ctrl+w")
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_dirty_editor_shows_unsaved_modal(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "unsaved change\n"
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+w")
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, UnsavedChangeModalScreen)


async def test_close_dirty_editor_dont_save_closes(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "unsaved\n"
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+w")
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#dont_save")
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view.opened_pane_ids) == 0


# ── Delete ────────────────────────────────────────────────────────────────────


async def test_delete_without_path_shows_notification(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_delete()
        await pilot.wait_for_scheduled_animations()
        assert not isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_with_path_shows_modal(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_delete()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_confirm_removes_file_and_closes_tab(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_delete()
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#delete")
        await pilot.wait_for_scheduled_animations()
        assert not sample_py_file.exists()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_delete_cancel_keeps_file_and_tab(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_delete()
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#cancel")
        await pilot.wait_for_scheduled_animations()
        assert sample_py_file.exists()
        assert len(app.main_view.opened_pane_ids) == 1


# ── Footer ────────────────────────────────────────────────────────────────────


async def test_footer_shows_file_path(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test(size=(240, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        path_label = app.query_one(CodeEditorFooter).path_view
        assert str(sample_py_file) in str(path_label.content)


async def test_footer_shows_language(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        lang_button = app.query_one(CodeEditorFooter).language_button
        assert "python" in str(lang_button.label)


async def test_footer_plain_for_untitled(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.wait_for_scheduled_animations()
        lang_button = app.query_one(CodeEditorFooter).language_button
        assert "plain" in str(lang_button.label)


# ── Cursor position ────────────────────────────────────────────────────────────


async def test_footer_shows_cursor_position_initially(workspace: Path):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.wait_for_scheduled_animations()
        cursor_btn = app.query_one(CodeEditorFooter).cursor_button
        assert "Ln 1, Col 1" in str(cursor_btn.label)


async def test_footer_cursor_position_updates_on_move(
    workspace: Path, sample_py_file: Path
):
    # sample_py_file contains "print('hello')\n"
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Move cursor to column 5 (0-based) = "Col 6" (1-based display)
        editor.editor.cursor_location = (0, 5)
        await pilot.wait_for_scheduled_animations()

        cursor_btn = app.query_one(CodeEditorFooter).cursor_button
        assert "Ln 1, Col 6" in str(cursor_btn.label)


async def test_footer_shows_ln1_col1_on_file_open(
    workspace: Path, sample_py_file: Path
):
    """Opening a file positions cursor at Ln 1, Col 1."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert "Ln 1, Col 1" in str(app.query_one(CodeEditorFooter).cursor_button.label)


async def test_footer_cursor_second_line(workspace: Path, multiline_file: Path):
    """Moving to second line shows Ln 2, Col 1."""
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.editor.cursor_location = (1, 0)
        await pilot.wait_for_scheduled_animations()

        assert "Ln 2, Col 1" in str(app.query_one(CodeEditorFooter).cursor_button.label)


async def test_footer_cursor_end_of_line(workspace: Path, sample_py_file: Path):
    """Cursor at end of 'print('hello')' (14 chars) → Col 15."""
    # sample_py_file: "print('hello')\n" — 14 chars before \n
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.editor.cursor_location = (0, 14)
        await pilot.wait_for_scheduled_animations()

        assert "Col 15" in str(app.query_one(CodeEditorFooter).cursor_button.label)


async def test_footer_cursor_updates_after_goto_line(
    workspace: Path, multiline_file: Path
):
    """After goto_line, footer reflects the new cursor position."""
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_goto_line()
        await pilot.wait_for_scheduled_animations()

        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("7")
        await pilot.click("#goto")
        await pilot.wait_for_scheduled_animations()

        footer = app.query_one(CodeEditorFooter)
        assert "Ln 7" in str(footer.cursor_button.label)
        assert "Col 1" in str(footer.cursor_button.label)


async def test_footer_path_updates_on_tab_switch(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """Footer shows the correct path when switching between tabs."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test(size=(240, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for tab open + footer path update

        json_editor = app.main_view.get_active_code_editor()
        assert json_editor is not None
        footer = app.query_one(CodeEditorFooter)
        assert str(sample_json_file) in str(footer.path_view.content)

        # Switch back to py tab
        py_pane_id = app.main_view.pane_id_from_path(sample_py_file)
        assert py_pane_id is not None
        app.main_view.focus_pane(py_pane_id)
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert str(sample_py_file) in str(footer.path_view.content)


# ── Goto Line ─────────────────────────────────────────────────────────────────


async def test_ctrl_g_opens_goto_line_modal(workspace: Path, multiline_file: Path):
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+g")
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, GotoLineModalScreen)


async def test_goto_line_moves_cursor_to_line(workspace: Path, multiline_file: Path):
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_goto_line()
        await pilot.wait_for_scheduled_animations()

        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("5")
        await pilot.click("#goto")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location == (4, 0)


async def test_goto_line_with_column_moves_cursor(
    workspace: Path, multiline_file: Path
):
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_goto_line()
        await pilot.wait_for_scheduled_animations()

        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("3", ":", "4")
        await pilot.click("#goto")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location == (2, 3)


async def test_goto_line_cancel_keeps_cursor(workspace: Path, multiline_file: Path):
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_goto_line()
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#cancel")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location == original_location


async def test_goto_line_invalid_input_no_move(workspace: Path, multiline_file: Path):
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_goto_line()
        await pilot.wait_for_scheduled_animations()

        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("a", "b", "c")
        await pilot.click("#goto")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location == original_location


async def test_goto_line_out_of_range_high_no_move(
    workspace: Path, multiline_file: Path
):
    """Line number beyond file length → notification, cursor unchanged."""
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_goto_line()
        await pilot.wait_for_scheduled_animations()

        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("9", "9", "9")
        await pilot.click("#goto")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location == original_location


async def test_goto_line_zero_is_out_of_range(workspace: Path, multiline_file: Path):
    """Line 0 is invalid (1-indexed); cursor should not move."""
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_goto_line()
        await pilot.wait_for_scheduled_animations()

        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("0")
        await pilot.click("#goto")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location == original_location


async def test_goto_first_line(workspace: Path, multiline_file: Path):
    """Goto line 1 moves cursor to row 0."""
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Move away from first line first
        editor.editor.cursor_location = (5, 0)
        await pilot.wait_for_scheduled_animations()

        editor.action_goto_line()
        await pilot.wait_for_scheduled_animations()

        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("1")
        await pilot.click("#goto")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location[0] == 0


async def test_goto_last_line(workspace: Path, multiline_file: Path):
    """Goto the last line (10th in multiline_file)."""
    # multiline_file has 10 lines ("line1" … "line10")
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_goto_line()
        await pilot.wait_for_scheduled_animations()

        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("1", "0")
        await pilot.click("#goto")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location[0] == 9  # 0-based


async def test_goto_line_col_zero_input_clamps_to_zero(
    workspace: Path, multiline_file: Path
):
    """Col input '0' (1-indexed 0 → 0-based -1) clamps to col 0."""
    app = make_app(workspace, light=True, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_goto_line()
        await pilot.wait_for_scheduled_animations()

        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("3", ":", "0")
        await pilot.click("#goto")
        await pilot.wait_for_scheduled_animations()

        row, col = editor.editor.cursor_location
        assert row == 2
        assert col == 0


# ── Change Language ────────────────────────────────────────────────────────────


async def test_language_button_opens_change_language_modal(
    workspace: Path, sample_py_file: Path
):
    from textual_code.modals import ChangeLanguageModalScreen

    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        await pilot.click("#language")
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, ChangeLanguageModalScreen)


async def test_change_language_action_opens_modal(
    workspace: Path, sample_py_file: Path
):
    from textual_code.modals import ChangeLanguageModalScreen

    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_change_language()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, ChangeLanguageModalScreen)


async def test_change_language_updates_editor_language(
    workspace: Path, sample_py_file: Path
):
    from textual.widgets import Select

    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language == "python"

        editor.action_change_language()
        await pilot.wait_for_scheduled_animations()

        app.screen.query_one(Select).value = "javascript"
        await pilot.click("#apply")
        await pilot.wait_for_scheduled_animations()

        assert editor.language == "javascript"


async def test_change_language_to_plain(workspace: Path, sample_py_file: Path):
    from textual.widgets import Select

    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language == "python"

        editor.action_change_language()
        await pilot.wait_for_scheduled_animations()

        app.screen.query_one(Select).value = "plain"
        await pilot.click("#apply")
        await pilot.wait_for_scheduled_animations()

        assert editor.language is None


async def test_change_language_cancel_keeps_language(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language == "python"

        editor.action_change_language()
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#cancel")
        await pilot.wait_for_scheduled_animations()

        assert editor.language == "python"


async def test_change_language_updates_footer(workspace: Path, sample_py_file: Path):
    from textual.widgets import Select

    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_change_language()
        await pilot.wait_for_scheduled_animations()

        app.screen.query_one(Select).value = "rust"
        await pilot.click("#apply")
        await pilot.wait_for_scheduled_animations()

        assert "rust" in str(app.query_one(CodeEditorFooter).language_button.label)


# ── Large file warning ───────────────────────────────────────────────────────


async def test_large_file_opens_with_warning(workspace: Path):
    """Opening a file exceeding threshold shows the confirmation modal."""
    large_file = workspace / "big.txt"
    large_file.write_text("x" * 200, encoding="utf-8")

    # Use a low threshold so we don't need a multi-MB file
    app = make_app(workspace, light=True)
    app.default_large_file_threshold = 100
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Schedule open as a background task (it blocks on modal dismiss)
        asyncio.create_task(app.main_view.action_open_code_editor(path=large_file))
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert isinstance(app.screen, LargeFileConfirmModalScreen)


async def test_large_file_threshold_zero_disables_warning(workspace: Path):
    """Threshold of 0 disables the large file warning."""
    large_file = workspace / "big.txt"
    large_file.write_text("x" * 200, encoding="utf-8")

    app = make_app(workspace, light=True)
    app.default_large_file_threshold = 0
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor(path=large_file)
        await pilot.wait_for_scheduled_animations()
        assert not isinstance(app.screen, LargeFileConfirmModalScreen)
        # File should have opened normally
        editor = app.main_view.get_active_code_editor()
        assert editor is not None


async def test_large_file_open_optimized_disables_highlighting(workspace: Path):
    """Choosing 'Open (no highlighting)' opens the file without syntax highlighting."""
    large_file = workspace / "big.py"
    large_file.write_text("x = 1\n" * 50, encoding="utf-8")

    app = make_app(workspace, light=True)
    app.default_large_file_threshold = 100
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Schedule open as a background task (it blocks on modal dismiss)
        asyncio.create_task(app.main_view.action_open_code_editor(path=large_file))
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert isinstance(app.screen, LargeFileConfirmModalScreen)

        await pilot.click("#open_optimized")
        await pilot.wait_for_scheduled_animations()

        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language is None


async def test_large_file_already_open_skips_check(workspace: Path):
    """Re-opening an already-open large file skips the size check."""
    large_file = workspace / "big.txt"
    large_file.write_text("x" * 200, encoding="utf-8")

    app = make_app(workspace, light=True)
    app.default_large_file_threshold = 100
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # First open — triggers the modal
        asyncio.create_task(app.main_view.action_open_code_editor(path=large_file))
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert isinstance(app.screen, LargeFileConfirmModalScreen)
        await pilot.click("#open")
        await pilot.wait_for_scheduled_animations()

        # Second open — should just focus the existing pane (no modal)
        await app.main_view.action_open_code_editor(path=large_file)
        await pilot.wait_for_scheduled_animations()
        assert not isinstance(app.screen, LargeFileConfirmModalScreen)


async def test_large_file_cancel_does_not_open(workspace: Path):
    """Cancelling the large file dialog does not open any editor."""
    large_file = workspace / "big.txt"
    large_file.write_text("x" * 200, encoding="utf-8")

    app = make_app(workspace, light=True)
    app.default_large_file_threshold = 100
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Schedule open as a background task (it blocks on modal dismiss)
        asyncio.create_task(app.main_view.action_open_code_editor(path=large_file))
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert isinstance(app.screen, LargeFileConfirmModalScreen)
        await pilot.click("#cancel")
        await pilot.wait_for_scheduled_animations()

        editor = app.main_view.get_active_code_editor()
        assert editor is None
