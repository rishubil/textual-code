"""
Modal dialog tests.
Each modal is tested independently using a wrapping TestApp.
"""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Input, Label

from textual_code.modals import (
    ChangeEncodingModalScreen,
    ChangeIndentModalResult,
    ChangeLanguageModalResult,
    ChangeLineEndingModalResult,
    ChangeSyntaxThemeModalScreen,
    ChangeUIThemeModalScreen,
    ChangeWordWrapModalScreen,
    DeleteFileModalResult,
    DeleteFileModalScreen,
    DiscardAndReloadModalScreen,
    GotoLineModalResult,
    GotoLineModalScreen,
    OverwriteConfirmModalScreen,
    RenameModalResult,
    RenameModalScreen,
    ReplaceAllConfirmModalResult,
    ReplaceAllConfirmModalScreen,
    ReplacePreview,
    SaveAsModalResult,
    SaveAsModalScreen,
    SidebarResizeModalScreen,
    SplitResizeModalScreen,
    UnsavedChangeModalResult,
    UnsavedChangeModalScreen,
    UnsavedChangeQuitModalResult,
    UnsavedChangeQuitModalScreen,
)

# ── SaveAsModalScreen ────────────────────────────────────────────────────────


class _SaveAsApp(App):
    def __init__(self):
        super().__init__()
        self.result: SaveAsModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(SaveAsModalScreen(), self._on_result)

    def _on_result(self, result: SaveAsModalResult | None) -> None:
        self.result = result


async def test_save_as_modal_save_button():
    app = _SaveAsApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#path")
        await pilot.click(input_widget)
        await pilot.press("t", "e", "s", "t", ".", "t", "x", "t")
        await pilot.click("#save")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.file_path == "test.txt"


async def test_save_as_modal_cancel_button():
    app = _SaveAsApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.file_path is None


async def test_save_as_modal_enter_submits():
    app = _SaveAsApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#path")
        await pilot.click(input_widget)
        await pilot.press("m", "y", ".", "p", "y")
        await pilot.press("enter")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.file_path == "my.py"


async def test_save_as_modal_escape_dismisses():
    app = _SaveAsApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.file_path is None


async def test_save_as_modal_escape_dismisses_with_input_focused():
    app = _SaveAsApp()
    async with app.run_test() as pilot:
        await pilot.click(app.screen.query_one("#path"))
        await pilot.press("t", "e", "s", "t")
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True


# ── UnsavedChangeModalScreen ─────────────────────────────────────────────────


class _UnsavedChangeApp(App):
    def __init__(self):
        super().__init__()
        self.result: UnsavedChangeModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(UnsavedChangeModalScreen(), self._on_result)

    def _on_result(self, result: UnsavedChangeModalResult | None) -> None:
        self.result = result


async def test_unsaved_change_modal_save_button():
    app = _UnsavedChangeApp()
    async with app.run_test() as pilot:
        await pilot.click("#save")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.should_save is True


async def test_unsaved_change_modal_dont_save_button():
    app = _UnsavedChangeApp()
    async with app.run_test() as pilot:
        await pilot.click("#dont_save")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.should_save is False


async def test_unsaved_change_modal_cancel_button():
    app = _UnsavedChangeApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.should_save is None


async def test_unsaved_change_modal_escape_does_not_dismiss():
    """Escape must NOT dismiss a destructive confirmation modal."""
    app = _UnsavedChangeApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


# ── UnsavedChangeQuitModalScreen ─────────────────────────────────────────────


class _UnsavedQuitApp(App):
    def __init__(self):
        super().__init__()
        self.result: UnsavedChangeQuitModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(UnsavedChangeQuitModalScreen(), self._on_result)

    def _on_result(self, result: UnsavedChangeQuitModalResult | None) -> None:
        self.result = result


async def test_unsaved_quit_modal_quit_button():
    app = _UnsavedQuitApp()
    async with app.run_test() as pilot:
        await pilot.click("#quit")
        await pilot.pause()

    assert app.result is not None
    assert app.result.should_quit is True


async def test_unsaved_quit_modal_cancel_button():
    app = _UnsavedQuitApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.should_quit is False


async def test_unsaved_quit_modal_escape_does_not_dismiss():
    """Escape must NOT dismiss a destructive quit confirmation modal."""
    app = _UnsavedQuitApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


# ── DeleteFileModalScreen ─────────────────────────────────────────────────────


class _DeleteFileApp(App):
    def __init__(self, path: Path):
        super().__init__()
        self._path = path
        self.result: DeleteFileModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(DeleteFileModalScreen(self._path), self._on_result)

    def _on_result(self, result: DeleteFileModalResult | None) -> None:
        self.result = result


async def test_delete_modal_delete_button(tmp_path):
    f = tmp_path / "to_delete.txt"
    f.write_text("content")
    app = _DeleteFileApp(f)
    async with app.run_test() as pilot:
        await pilot.click("#delete")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.should_delete is True


async def test_delete_modal_cancel_button(tmp_path):
    f = tmp_path / "to_delete.txt"
    f.write_text("content")
    app = _DeleteFileApp(f)
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.should_delete is False


async def test_delete_modal_shows_file_path(tmp_path):
    f = tmp_path / "myfile.py"
    f.write_text("content")
    app = _DeleteFileApp(f)
    async with app.run_test() as pilot:
        await pilot.pause()
        message_label = app.screen.query_one("#message", Label)
        assert str(f) in str(message_label.content)


async def test_delete_modal_file_title_contains_file(tmp_path):
    """File path → modal title contains 'file', not 'directory'."""
    f = tmp_path / "myfile.py"
    f.write_text("content")
    app = _DeleteFileApp(f)
    async with app.run_test() as pilot:
        await pilot.pause()
        title_label = app.screen.query_one("#title", Label)
        title_text = str(title_label.content)
        assert "file" in title_text.lower()
        assert "directory" not in title_text.lower()


async def test_delete_modal_file_warning_cannot_be_undone(tmp_path):
    """File path → #warning contains 'cannot be undone'."""
    f = tmp_path / "myfile.py"
    f.write_text("content")
    app = _DeleteFileApp(f)
    async with app.run_test() as pilot:
        await pilot.pause()
        warning_label = app.screen.query_one("#warning", Label)
        assert "cannot be undone" in str(warning_label.content).lower()


async def test_delete_modal_directory_title_contains_directory_and_contents(tmp_path):
    """Directory path → modal title contains 'directory' and 'contents'."""
    d = tmp_path / "mydir"
    d.mkdir()
    app = _DeleteFileApp(d)
    async with app.run_test() as pilot:
        await pilot.pause()
        title_label = app.screen.query_one("#title", Label)
        title_text = str(title_label.content).lower()
        assert "directory" in title_text
        assert "contents" in title_text


async def test_delete_modal_directory_warning_cannot_be_undone(tmp_path):
    """Directory path → #warning contains 'cannot be undone'."""
    d = tmp_path / "mydir"
    d.mkdir()
    app = _DeleteFileApp(d)
    async with app.run_test() as pilot:
        await pilot.pause()
        warning_label = app.screen.query_one("#warning", Label)
        assert "cannot be undone" in str(warning_label.content).lower()


async def test_delete_modal_escape_does_not_dismiss(tmp_path):
    """Escape must NOT dismiss a destructive delete confirmation modal."""
    f = tmp_path / "to_delete.txt"
    f.write_text("content")
    app = _DeleteFileApp(f)
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


# ── GotoLineModalScreen ───────────────────────────────────────────────────────


class _GotoLineApp(App):
    def __init__(self):
        super().__init__()
        self.result: GotoLineModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(GotoLineModalScreen(), self._on_result)

    def _on_result(self, result: GotoLineModalResult | None) -> None:
        self.result = result


async def test_goto_line_modal_goto_button():
    app = _GotoLineApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("5")
        await pilot.click("#goto")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.value == "5"


async def test_goto_line_modal_cancel_button():
    app = _GotoLineApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.value is None


async def test_goto_line_modal_enter_submits():
    app = _GotoLineApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("3", ":", "7")
        await pilot.press("enter")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.value == "3:7"


async def test_goto_line_modal_escape_dismisses():
    app = _GotoLineApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.value is None


async def test_goto_line_modal_escape_dismisses_with_input_focused():
    app = _GotoLineApp()
    async with app.run_test() as pilot:
        await pilot.click(app.screen.query_one("#location"))
        await pilot.press("5")
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True


# ── ChangeLanguageModalScreen ─────────────────────────────────────────────────


class _ChangeLanguageApp(App):
    def __init__(self, languages: list[str], current_language: str | None):
        super().__init__()
        self._languages = languages
        self._current_language = current_language
        self.result: ChangeLanguageModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        from textual_code.modals import ChangeLanguageModalScreen

        self.push_screen(
            ChangeLanguageModalScreen(
                languages=self._languages,
                current_language=self._current_language,
            ),
            self._on_result,
        )

    def _on_result(self, result) -> None:
        self.result = result


async def test_change_language_modal_apply_returns_language():
    from textual.widgets import Select

    app = _ChangeLanguageApp(languages=["python", "javascript"], current_language=None)
    async with app.run_test() as pilot:
        app.screen.query_one(Select).value = "python"
        await pilot.click("#apply")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.language == "python"


async def test_change_language_modal_cancel_returns_cancelled():
    app = _ChangeLanguageApp(languages=["python"], current_language="python")
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.language is None


async def test_change_language_modal_plain_returns_none_language():
    from textual.widgets import Select

    app = _ChangeLanguageApp(languages=["python"], current_language="python")
    async with app.run_test() as pilot:
        app.screen.query_one(Select).value = "plain"
        await pilot.click("#apply")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.language is None


async def test_change_language_modal_initial_plain_when_no_language():
    from textual.widgets import Select

    app = _ChangeLanguageApp(languages=["python", "rust"], current_language=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        select = app.screen.query_one(Select)
        assert select.value == "plain"


async def test_change_language_modal_initial_value_is_current_language():
    from textual.widgets import Select

    app = _ChangeLanguageApp(languages=["python", "rust"], current_language="rust")
    async with app.run_test() as pilot:
        await pilot.pause()
        select = app.screen.query_one(Select)
        assert select.value == "rust"


async def test_change_language_modal_escape_dismisses():
    app = _ChangeLanguageApp(languages=["python"], current_language="python")
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.language is None


# ── FindModalScreen ───────────────────────────────────────────────────────────


class _FindApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        from textual_code.modals import FindModalScreen

        self.push_screen(FindModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_find_modal_find_button_returns_query():
    app = _FindApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#query")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#find")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.query == "hello"


async def test_find_modal_cancel_button_returns_cancelled():
    app = _FindApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.query is None


async def test_find_modal_enter_submits():
    app = _FindApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#query")
        await pilot.click(input_widget)
        await pilot.press("f", "o", "o")
        await pilot.press("enter")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.query == "foo"


async def test_find_modal_empty_query_allowed():
    """FindModalScreen allows empty query (the caller decides what to do)."""
    app = _FindApp()
    async with app.run_test() as pilot:
        await pilot.click("#find")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.query == ""


async def test_find_modal_escape_dismisses():
    app = _FindApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.query is None


async def test_find_modal_escape_dismisses_with_input_focused():
    app = _FindApp()
    async with app.run_test() as pilot:
        await pilot.click(app.screen.query_one("#query"))
        await pilot.press("h", "i")
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True


# ── ReplaceModalScreen ────────────────────────────────────────────────────────


class _ReplaceApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        from textual_code.modals import ReplaceModalScreen

        self.push_screen(ReplaceModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_replace_modal_replace_button_returns_action_replace():
    app = _ReplaceApp()
    async with app.run_test() as pilot:
        await pilot.click("#find_query")
        await pilot.press("f", "o", "o")
        await pilot.click("#replace_text")
        await pilot.press("b", "a", "r")
        await pilot.click("#replace")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.action == "replace"
    assert app.result.find_query == "foo"
    assert app.result.replace_text == "bar"


async def test_replace_modal_replace_all_button_returns_action_replace_all():
    app = _ReplaceApp()
    async with app.run_test() as pilot:
        await pilot.click("#find_query")
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#replace_text")
        await pilot.press("h", "i")
        await pilot.click("#replace_all")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.action == "replace_all"
    assert app.result.find_query == "hello"
    assert app.result.replace_text == "hi"


async def test_replace_modal_cancel_returns_cancelled():
    app = _ReplaceApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.action is None
    assert app.result.find_query is None
    assert app.result.replace_text is None


async def test_replace_modal_empty_replace_text_returns_empty_string():
    """replace_text is "" (not None) when the replacement field is left blank."""
    app = _ReplaceApp()
    async with app.run_test() as pilot:
        await pilot.click("#find_query")
        await pilot.press("f", "o", "o")
        # leave replace_text empty
        await pilot.click("#replace")
        await pilot.pause()

    assert app.result is not None
    assert app.result.replace_text == ""


async def test_replace_modal_escape_dismisses():
    app = _ReplaceApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.action is None


async def test_replace_modal_escape_dismisses_with_input_focused():
    app = _ReplaceApp()
    async with app.run_test() as pilot:
        await pilot.click(app.screen.query_one("#find_query"))
        await pilot.press("f", "o", "o")
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True


# ── FindModalScreen use_regex ──────────────────────────────────────────────────


async def test_find_modal_has_use_regex_checkbox():
    """FindModalScreen has a #use_regex Checkbox."""
    from textual.widgets import Checkbox

    app = _FindApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        checkbox = app.screen.query_one("#use_regex", Checkbox)
        assert checkbox is not None


async def test_find_modal_use_regex_false_by_default():
    """Without checking, result.use_regex == False."""
    app = _FindApp()
    async with app.run_test() as pilot:
        await pilot.click("#find")
        await pilot.pause()

    assert app.result is not None
    assert app.result.use_regex is False


async def test_find_modal_use_regex_true_when_checked():
    """After checking the Checkbox and clicking Find, result.use_regex == True."""
    from textual.widgets import Checkbox

    app = _FindApp()
    async with app.run_test() as pilot:
        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)
        await pilot.click("#find")
        await pilot.pause()

    assert app.result is not None
    assert app.result.use_regex is True


# ── ReplaceModalScreen use_regex ───────────────────────────────────────────────


async def test_replace_modal_has_use_regex_checkbox():
    """ReplaceModalScreen has a #use_regex Checkbox."""
    from textual.widgets import Checkbox

    app = _ReplaceApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        checkbox = app.screen.query_one("#use_regex", Checkbox)
        assert checkbox is not None


async def test_replace_modal_use_regex_false_by_default():
    """Without checking, result.use_regex == False."""
    app = _ReplaceApp()
    async with app.run_test() as pilot:
        await pilot.click("#replace")
        await pilot.pause()

    assert app.result is not None
    assert app.result.use_regex is False


async def test_replace_modal_use_regex_true_when_checked():
    """After checking the Checkbox and clicking Replace, result.use_regex == True."""
    from textual.widgets import Checkbox

    app = _ReplaceApp()
    async with app.run_test() as pilot:
        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)
        await pilot.click("#replace")
        await pilot.pause()

    assert app.result is not None
    assert app.result.use_regex is True


# ── ChangeIndentModalScreen ───────────────────────────────────────────────────


class _ChangeIndentApp(App):
    def __init__(self):
        super().__init__()
        self.result: ChangeIndentModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        from textual_code.modals import ChangeIndentModalScreen

        self.push_screen(ChangeIndentModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_change_indent_modal_has_type_select():
    """ChangeIndentModalScreen has an #indent_type Select."""
    from textual.widgets import Select

    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        select = app.screen.query_one("#indent_type", Select)
        assert select is not None


async def test_change_indent_modal_has_size_input():
    """ChangeIndentModalScreen has an #indent_size Input (free-form integer)."""
    from textual.widgets import Input

    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        inp = app.screen.query_one("#indent_size", Input)
        assert inp is not None


async def test_change_indent_modal_apply_returns_spaces_4():
    """Clicking Apply → indent_type='spaces', indent_size=4, is_cancelled=False."""
    from textual.widgets import Input, Select

    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "4"
        await pilot.click("#apply")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.indent_type == "spaces"
    assert app.result.indent_size == 4


async def test_change_indent_modal_apply_returns_tabs():
    """Clicking Apply (tabs) → indent_type='tabs', is_cancelled=False."""
    from textual.widgets import Input, Select

    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        app.screen.query_one("#indent_type", Select).value = "tabs"
        app.screen.query_one("#indent_size", Input).value = "2"
        await pilot.click("#apply")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.indent_type == "tabs"
    assert app.result.indent_size == 2


async def test_change_indent_modal_cancel_returns_cancelled():
    """Clicking Cancel → is_cancelled=True, indent_type/size=None."""
    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.indent_type is None
    assert app.result.indent_size is None


async def test_change_indent_modal_escape_dismisses():
    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.indent_type is None
    assert app.result.indent_size is None


# ── ChangeLineEndingModalScreen ───────────────────────────────────────────────


class _ChangeLineEndingApp(App):
    def __init__(self, current_line_ending: str = "lf"):
        super().__init__()
        self._current_line_ending = current_line_ending
        self.result: ChangeLineEndingModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        from textual_code.modals import ChangeLineEndingModalScreen

        self.push_screen(
            ChangeLineEndingModalScreen(current_line_ending=self._current_line_ending),
            self._on_result,
        )

    def _on_result(self, result) -> None:
        self.result = result


async def test_change_line_ending_modal_has_select():
    """ChangeLineEndingModalScreen has a #line_ending Select."""
    from textual.widgets import Select

    app = _ChangeLineEndingApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        select = app.screen.query_one("#line_ending", Select)
        assert select is not None


async def test_change_line_ending_modal_apply_returns_lf():
    """Clicking Apply (lf) → line_ending='lf', is_cancelled=False."""
    from textual.widgets import Select

    app = _ChangeLineEndingApp(current_line_ending="lf")
    async with app.run_test() as pilot:
        app.screen.query_one("#line_ending", Select).value = "lf"
        await pilot.click("#apply")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.line_ending == "lf"


async def test_change_line_ending_modal_apply_returns_crlf():
    """Clicking Apply (crlf) → line_ending='crlf', is_cancelled=False."""
    from textual.widgets import Select

    app = _ChangeLineEndingApp(current_line_ending="lf")
    async with app.run_test() as pilot:
        app.screen.query_one("#line_ending", Select).value = "crlf"
        await pilot.click("#apply")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.line_ending == "crlf"


async def test_change_line_ending_modal_cancel_returns_cancelled():
    """Clicking Cancel → is_cancelled=True, line_ending=None."""
    app = _ChangeLineEndingApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.line_ending is None


async def test_change_line_ending_modal_initial_value_is_current():
    """current_line_ending='crlf' → Select initial value is 'crlf'."""
    from textual.widgets import Select

    app = _ChangeLineEndingApp(current_line_ending="crlf")
    async with app.run_test() as pilot:
        await pilot.pause()
        select = app.screen.query_one("#line_ending", Select)
        assert select.value == "crlf"


async def test_change_line_ending_modal_escape_dismisses():
    app = _ChangeLineEndingApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.line_ending is None


# ── RebindKeyScreen and ShowShortcutsScreen align CSS ─────────────────────────


def test_rebind_screen_has_center_align():
    """RebindKeyScreen DEFAULT_CSS must contain 'align: center middle'."""
    from textual_code.modals import RebindKeyScreen

    assert "align: center middle" in RebindKeyScreen.DEFAULT_CSS


def test_show_shortcuts_screen_has_center_align():
    """ShowShortcutsScreen DEFAULT_CSS must contain 'align: center middle'."""
    from textual_code.modals import ShowShortcutsScreen

    assert "align: center middle" in ShowShortcutsScreen.DEFAULT_CSS


# ── RenameModalScreen ────────────────────────────────────────────────────────


class _RenameApp(App):
    def __init__(self, current_name: str):
        super().__init__()
        self._current_name = current_name
        self.result: RenameModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(RenameModalScreen(self._current_name), self._on_result)

    def _on_result(self, result: RenameModalResult | None) -> None:
        self.result = result


async def test_rename_modal_rename_button():
    app = _RenameApp("hello.py")
    async with app.run_test() as pilot:
        inp = app.screen.query_one("#new_name")
        await pilot.click(inp)
        from textual.widgets import Input

        app.screen.query_one(Input).value = "world.py"
        await pilot.click("#rename")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.new_name == "world.py"


async def test_rename_modal_cancel_button():
    app = _RenameApp("hello.py")
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.new_name is None


async def test_rename_modal_enter_submits():
    app = _RenameApp("hello.py")
    async with app.run_test() as pilot:
        from textual.widgets import Input

        app.screen.query_one(Input).value = "renamed.py"
        await pilot.press("enter")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.new_name == "renamed.py"


async def test_rename_modal_input_prefilled():
    app = _RenameApp("hello.py")
    async with app.run_test():
        from textual.widgets import Input

        inp = app.screen.query_one(Input)
        assert inp.value == "hello.py"


async def test_rename_modal_escape_dismisses():
    app = _RenameApp("hello.py")
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.new_name is None


async def test_rename_modal_escape_dismisses_with_input_focused():
    app = _RenameApp("hello.py")
    async with app.run_test() as pilot:
        from textual.widgets import Input

        await pilot.click(app.screen.query_one(Input))
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True


# ── ReplaceAllConfirmModalScreen ─────────────────────────────────────────────


def _make_preview() -> ReplacePreview:
    return ReplacePreview(
        file="src/app.py",
        line_num=10,
        before="hello world",
        after="hi world",
    )


class _ReplaceAllConfirmApp(App):
    def __init__(self, **kwargs):
        super().__init__()
        self.result: ReplaceAllConfirmModalResult | None = None
        self.modal_kwargs = kwargs

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(
            ReplaceAllConfirmModalScreen(**self.modal_kwargs),
            self._on_result,
        )

    def _on_result(self, result: ReplaceAllConfirmModalResult | None) -> None:
        self.result = result


async def test_replace_all_confirm_modal_replace_button():
    app = _ReplaceAllConfirmApp(
        files_count=3,
        occurrences_count=5,
        is_truncated=False,
        preview=_make_preview(),
    )
    async with app.run_test() as pilot:
        await pilot.click("#replace-all")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.should_replace is True


async def test_replace_all_confirm_modal_cancel_button():
    app = _ReplaceAllConfirmApp(
        files_count=3,
        occurrences_count=5,
        is_truncated=False,
        preview=_make_preview(),
    )
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.should_replace is False


async def test_replace_all_confirm_modal_shows_summary():
    app = _ReplaceAllConfirmApp(
        files_count=3,
        occurrences_count=5,
        is_truncated=False,
        preview=_make_preview(),
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        message = app.screen.query_one("#message", Label)
        text = str(message.content)
        assert "5" in text
        assert "3" in text
        assert "occurrence" in text
        assert "file" in text


async def test_replace_all_confirm_modal_shows_preview():
    app = _ReplaceAllConfirmApp(
        files_count=1,
        occurrences_count=1,
        is_truncated=False,
        preview=_make_preview(),
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        preview = app.screen.query_one("#preview", Label)
        text = str(preview.content)
        assert "- hello world" in text
        assert "+ hi world" in text
        assert "src/app.py:10" in text


async def test_replace_all_confirm_modal_truncated():
    app = _ReplaceAllConfirmApp(
        files_count=42,
        occurrences_count=500,
        is_truncated=True,
        preview=_make_preview(),
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        message = app.screen.query_one("#message", Label)
        text = str(message.content)
        assert "500+" in text
        assert "42+" in text


async def test_replace_all_confirm_modal_escape_does_not_dismiss():
    """Escape must NOT dismiss a destructive replace-all confirmation modal."""
    app = _ReplaceAllConfirmApp(
        files_count=3,
        occurrences_count=5,
        is_truncated=False,
        preview=_make_preview(),
    )
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


# ── ChangeEncodingModalScreen (Escape) ──────────────────────────────────────


class _ChangeEncodingApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(ChangeEncodingModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_change_encoding_modal_escape_dismisses():
    app = _ChangeEncodingApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.encoding is None


# ── ChangeSyntaxThemeModalScreen (Escape) ───────────────────────────────────


class _ChangeSyntaxThemeApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(ChangeSyntaxThemeModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_change_syntax_theme_modal_escape_dismisses():
    app = _ChangeSyntaxThemeApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.theme is None


# ── ChangeWordWrapModalScreen (Escape) ──────────────────────────────────────


class _ChangeWordWrapApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(ChangeWordWrapModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_change_word_wrap_modal_escape_dismisses():
    app = _ChangeWordWrapApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.word_wrap is None


# ── ChangeUIThemeModalScreen (Escape) ───────────────────────────────────────


class _ChangeUIThemeApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(ChangeUIThemeModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_change_ui_theme_modal_escape_dismisses():
    app = _ChangeUIThemeApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.theme is None


# ── SidebarResizeModalScreen (Escape) ───────────────────────────────────────


class _SidebarResizeApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(SidebarResizeModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_sidebar_resize_modal_escape_dismisses():
    app = _SidebarResizeApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.value is None


# ── SplitResizeModalScreen (Escape) ─────────────────────────────────────────


class _SplitResizeApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(SplitResizeModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_split_resize_modal_escape_dismisses():
    app = _SplitResizeApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.value is None


# ── OverwriteConfirmModalScreen (Escape defense) ───────────────────────────


class _OverwriteConfirmApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(OverwriteConfirmModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_overwrite_confirm_modal_escape_does_not_dismiss():
    """Escape must NOT dismiss a destructive overwrite confirmation modal."""
    app = _OverwriteConfirmApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


# ── DiscardAndReloadModalScreen (Escape defense) ───────────────────────────


class _DiscardAndReloadApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(DiscardAndReloadModalScreen(), self._on_result)

    def _on_result(self, result) -> None:
        self.result = result


async def test_discard_and_reload_modal_escape_does_not_dismiss():
    """Escape must NOT dismiss a destructive discard-and-reload modal."""
    app = _DiscardAndReloadApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


# ── ShortcutSettingsScreen (Escape) ─────────────────────────────────────────


class _ShortcutSettingsApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        from textual_code.modals import ShortcutSettingsScreen

        self.push_screen(
            ShortcutSettingsScreen(
                action_name="test_action",
                description="Test Action",
                current_key="ctrl+t",
            ),
            self._on_result,
        )

    def _on_result(self, result) -> None:
        self.result = result


async def test_shortcut_settings_escape_dismisses():
    app = _ShortcutSettingsApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True


# ── FooterConfigScreen (Escape) ─────────────────────────────────────────────


class _FooterConfigApp(App):
    def __init__(self):
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        from textual_code.config import FooterOrders
        from textual_code.modals import FooterConfigScreen

        self.push_screen(
            FooterConfigScreen(
                all_area_actions={
                    "editor": [("test_action", "Test", "ctrl+t", True)],
                },
                footer_orders=FooterOrders(areas={"editor": ["test_action"]}),
            ),
            self._on_result,
        )

    def _on_result(self, result) -> None:
        self.result = result


async def test_footer_config_escape_dismisses():
    app = _FooterConfigApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True


# ── ShowShortcutsScreen (Escape) ────────────────────────────────────────────

_UNSET = object()


class _ShowShortcutsApp(App):
    def __init__(self):
        super().__init__()
        self.result = _UNSET

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        from textual_code.modals import ShowShortcutsScreen

        self.push_screen(
            ShowShortcutsScreen(
                rows=[("ctrl+s", "Save", "Editor", "save")],
            ),
            self._on_result,
        )

    def _on_result(self, result) -> None:
        self.result = result


async def test_show_shortcuts_escape_dismisses():
    app = _ShowShortcutsApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


# ── Save Screenshot (SaveAsModalScreen with title override) ──────────────────


class _SaveScreenshotApp(App):
    def __init__(self, default_path: str = "screenshot_test.svg"):
        super().__init__()
        self.result: SaveAsModalResult | None = None
        self._default_path = default_path

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(
            SaveAsModalScreen(title="Save Screenshot", default_path=self._default_path),
            self._on_result,
        )

    def _on_result(self, result: SaveAsModalResult | None) -> None:
        self.result = result


async def test_save_screenshot_modal_save_button():
    app = _SaveScreenshotApp()
    async with app.run_test() as pilot:
        await pilot.click("#save")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.file_path == "screenshot_test.svg"


async def test_save_screenshot_modal_cancel_button():
    app = _SaveScreenshotApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.file_path is None


async def test_save_screenshot_modal_enter_submits():
    app = _SaveScreenshotApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#path")
        await pilot.click(input_widget)
        await pilot.press("enter")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.file_path == "screenshot_test.svg"


async def test_save_screenshot_modal_escape_dismisses():
    app = _SaveScreenshotApp()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.file_path is None


async def test_save_screenshot_modal_default_value():
    app = _SaveScreenshotApp(default_path="my_screenshot.svg")
    async with app.run_test():
        input_widget = app.screen.query_one("#path", Input)
        assert input_widget.value == "my_screenshot.svg"
