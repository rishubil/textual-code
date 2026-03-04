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

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.modals import (
    DeleteFileModalScreen,
    SaveAsModalScreen,
    UnsavedChangeModalScreen,
)

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
    ],
)
async def test_language_detection(
    filename: str, expected_lang: str | None, workspace: Path
):
    f = workspace / filename
    f.write_text("")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language == expected_lang


# ── Title reactive ────────────────────────────────────────────────────────────


async def test_title_untitled_when_no_path(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.title == "<Untitled>"


async def test_title_shows_filename(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.title == "hello.py"


async def test_title_has_asterisk_when_modified(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified content\n"
        await pilot.pause()
        assert editor.title == "hello.py*"


async def test_title_asterisk_removed_after_save(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.pause()
        assert "*" in editor.title

        await pilot.press("ctrl+s")
        await pilot.pause()
        assert "*" not in editor.title


# ── Basic text editing ────────────────────────────────────────────────────────


async def test_initial_text_loaded_from_file(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.text == "print('hello')\n"
        assert editor.initial_text == "print('hello')\n"


async def test_text_reactive_reflects_edit(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "new content\n"
        await pilot.pause()
        assert editor.text == "new content\n"
        assert editor.initial_text == "print('hello')\n"


# ── Save ──────────────────────────────────────────────────────────────────────


async def test_save_writes_to_disk(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "print('modified')\n"
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert sample_py_file.read_text() == "print('modified')\n"


async def test_save_updates_initial_text(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "updated\n"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert editor.initial_text == "updated\n"
        assert editor.text == editor.initial_text


async def test_save_without_path_triggers_save_as_modal(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, SaveAsModalScreen)


# ── Save As ───────────────────────────────────────────────────────────────────


async def test_save_as_creates_new_file(workspace: Path, sample_py_file: Path):
    new_path = workspace / "new_file.py"
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_save_as()
        await pilot.pause()

        input_widget = app.query_one("#path")
        await pilot.click(input_widget)
        for ch in str(new_path):
            await pilot.press(ch)
        await pilot.click("#save")
        await pilot.pause()

    assert new_path.exists()


# ── Close ─────────────────────────────────────────────────────────────────────


async def test_close_clean_editor_with_ctrl_w(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1
        await pilot.press("ctrl+w")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_close_dirty_editor_shows_unsaved_modal(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "unsaved change\n"
        await pilot.pause()
        await pilot.press("ctrl+w")
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeModalScreen)


async def test_close_dirty_editor_dont_save_closes(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "unsaved\n"
        await pilot.pause()
        await pilot.press("ctrl+w")
        await pilot.pause()
        await pilot.click("#dont_save")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


# ── Delete ────────────────────────────────────────────────────────────────────


async def test_delete_without_path_shows_notification(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_delete()
        await pilot.pause()
        assert not isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_with_path_shows_modal(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_delete()
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_confirm_removes_file_and_closes_tab(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_delete()
        await pilot.pause()
        await pilot.click("#delete")
        await pilot.pause()
        assert not sample_py_file.exists()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_delete_cancel_keeps_file_and_tab(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_delete()
        await pilot.pause()
        await pilot.click("#cancel")
        await pilot.pause()
        assert sample_py_file.exists()
        assert len(app.main_view.opened_pane_ids) == 1


# ── Footer ────────────────────────────────────────────────────────────────────


async def test_footer_shows_file_path(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        path_label = editor.footer.path_view
        assert str(sample_py_file) in str(path_label.content)


async def test_footer_shows_language(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        lang_button = editor.footer.language_button
        assert "python" in str(lang_button.label)


async def test_footer_plain_for_untitled(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        lang_button = editor.footer.language_button
        assert "plain" in str(lang_button.label)
