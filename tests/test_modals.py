"""
모달 다이얼로그 테스트.
각 모달을 래핑 TestApp으로 독립 테스트한다.
"""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Label

from textual_code.modals import (
    ChangeIndentModalResult,
    ChangeLanguageModalResult,
    DeleteFileModalResult,
    DeleteFileModalScreen,
    GotoLineModalResult,
    GotoLineModalScreen,
    SaveAsModalResult,
    SaveAsModalScreen,
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
        message_label = app.screen.query_one("#message")
        assert str(f) in str(message_label.content)


async def test_delete_modal_file_title_contains_file(tmp_path):
    """파일 경로 → 모달 title에 'file' 포함, 'directory' 미포함."""
    f = tmp_path / "myfile.py"
    f.write_text("content")
    app = _DeleteFileApp(f)
    async with app.run_test() as pilot:
        await pilot.pause()
        title_label = app.screen.query_one("#title")
        title_text = str(title_label.content)
        assert "file" in title_text.lower()
        assert "directory" not in title_text.lower()


async def test_delete_modal_file_warning_cannot_be_undone(tmp_path):
    """파일 경로 → #warning에 'cannot be undone' 포함."""
    f = tmp_path / "myfile.py"
    f.write_text("content")
    app = _DeleteFileApp(f)
    async with app.run_test() as pilot:
        await pilot.pause()
        warning_label = app.screen.query_one("#warning")
        assert "cannot be undone" in str(warning_label.content).lower()


async def test_delete_modal_directory_title_contains_directory_and_contents(tmp_path):
    """디렉토리 경로 → 모달 title에 'directory'와 'contents' 포함."""
    d = tmp_path / "mydir"
    d.mkdir()
    app = _DeleteFileApp(d)
    async with app.run_test() as pilot:
        await pilot.pause()
        title_label = app.screen.query_one("#title")
        title_text = str(title_label.content).lower()
        assert "directory" in title_text
        assert "contents" in title_text


async def test_delete_modal_directory_warning_cannot_be_undone(tmp_path):
    """디렉토리 경로 → #warning에 'cannot be undone' 포함."""
    d = tmp_path / "mydir"
    d.mkdir()
    app = _DeleteFileApp(d)
    async with app.run_test() as pilot:
        await pilot.pause()
        warning_label = app.screen.query_one("#warning")
        assert "cannot be undone" in str(warning_label.content).lower()


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


# ── FindModalScreen use_regex ──────────────────────────────────────────────────


async def test_find_modal_has_use_regex_checkbox():
    """FindModalScreen에 #use_regex Checkbox가 존재한다."""
    from textual.widgets import Checkbox

    app = _FindApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        checkbox = app.screen.query_one("#use_regex", Checkbox)
        assert checkbox is not None


async def test_find_modal_use_regex_false_by_default():
    """체크하지 않으면 result.use_regex == False."""
    app = _FindApp()
    async with app.run_test() as pilot:
        await pilot.click("#find")
        await pilot.pause()

    assert app.result is not None
    assert app.result.use_regex is False


async def test_find_modal_use_regex_true_when_checked():
    """Checkbox 체크 후 Find하면 result.use_regex == True."""
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
    """ReplaceModalScreen에 #use_regex Checkbox가 존재한다."""
    from textual.widgets import Checkbox

    app = _ReplaceApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        checkbox = app.screen.query_one("#use_regex", Checkbox)
        assert checkbox is not None


async def test_replace_modal_use_regex_false_by_default():
    """체크하지 않으면 result.use_regex == False."""
    app = _ReplaceApp()
    async with app.run_test() as pilot:
        await pilot.click("#replace")
        await pilot.pause()

    assert app.result is not None
    assert app.result.use_regex is False


async def test_replace_modal_use_regex_true_when_checked():
    """Checkbox 체크 후 Replace하면 result.use_regex == True."""
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
    """ChangeIndentModalScreen에 #indent_type Select가 존재한다."""
    from textual.widgets import Select

    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        select = app.screen.query_one("#indent_type", Select)
        assert select is not None


async def test_change_indent_modal_has_size_select():
    """ChangeIndentModalScreen에 #indent_size Select가 존재한다."""
    from textual.widgets import Select

    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        select = app.screen.query_one("#indent_size", Select)
        assert select is not None


async def test_change_indent_modal_apply_returns_spaces_4():
    """Apply 클릭 → indent_type='spaces', indent_size=4, is_cancelled=False."""
    from textual.widgets import Select

    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Select).value = 4
        await pilot.click("#apply")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.indent_type == "spaces"
    assert app.result.indent_size == 4


async def test_change_indent_modal_apply_returns_tabs():
    """Apply 클릭 (tabs) → indent_type='tabs', is_cancelled=False."""
    from textual.widgets import Select

    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        app.screen.query_one("#indent_type", Select).value = "tabs"
        app.screen.query_one("#indent_size", Select).value = 2
        await pilot.click("#apply")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.indent_type == "tabs"
    assert app.result.indent_size == 2


async def test_change_indent_modal_cancel_returns_cancelled():
    """Cancel 클릭 → is_cancelled=True, indent_type/size=None."""
    app = _ChangeIndentApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.indent_type is None
    assert app.result.indent_size is None
