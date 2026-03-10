"""
모달 다이얼로그 테스트.
각 모달을 래핑 TestApp으로 독립 테스트한다.
"""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Label

from textual_code.modals import (
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
