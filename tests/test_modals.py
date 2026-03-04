"""
모달 다이얼로그 테스트.
각 모달을 래핑 TestApp으로 독립 테스트한다.
"""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Label

from textual_code.modals import (
    DeleteFileModalResult,
    DeleteFileModalScreen,
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
