"""
Line ending conversion feature tests.

Unit tests: _detect_line_ending, _convert_line_ending helper functions
Integration tests: action_change_line_ending via ChangeLineEndingModalScreen
"""

from pathlib import Path

from textual.app import App, ComposeResult

from textual_code.widgets.code_editor import (
    CodeEditor,
    _convert_line_ending,
    _detect_line_ending,
)

# ── _detect_line_ending unit tests ───────────────────────────────────────────


def test_detect_lf_only():
    """Text with only \\n → 'lf'."""
    assert _detect_line_ending("\nhello") == "lf"


def test_detect_crlf():
    """Text containing \\r\\n → 'crlf'."""
    assert _detect_line_ending("hello\r\nworld") == "crlf"


def test_detect_cr_only():
    """Text with only \\r → 'cr'."""
    assert _detect_line_ending("hello\rworld") == "cr"


def test_detect_empty_string():
    """Empty string → 'lf' (default)."""
    assert _detect_line_ending("") == "lf"


def test_detect_crlf_priority():
    """Mixed \\r\\n and \\r → 'crlf' takes priority."""
    assert _detect_line_ending("a\r\nb\rc") == "crlf"


# ── _convert_line_ending unit tests ──────────────────────────────────────────


def test_convert_lf_noop():
    """Specifying 'lf' leaves text unchanged."""
    assert _convert_line_ending("hello\nworld", "lf") == "hello\nworld"


def test_convert_to_crlf():
    """'hello\nworld' → 'hello\r\nworld'."""
    assert _convert_line_ending("hello\nworld", "crlf") == "hello\r\nworld"


def test_convert_to_cr():
    """'hello\nworld' → 'hello\rworld'."""
    assert _convert_line_ending("hello\nworld", "cr") == "hello\rworld"


def test_convert_multiline_crlf():
    """All \\n replaced with \\r\\n."""
    text = "a\nb\nc"
    assert _convert_line_ending(text, "crlf") == "a\r\nb\r\nc"


def test_convert_empty_string():
    """Empty string → empty string."""
    assert _convert_line_ending("", "crlf") == ""


# ── Integration test app ──────────────────────────────────────────────────────


class _LineEndingTestApp(App):
    """Test app containing a CodeEditor for integration tests."""

    def __init__(self, path: Path | None = None):
        super().__init__()
        self._path = path

    def compose(self) -> ComposeResult:
        pane_id = CodeEditor.generate_pane_id()
        yield CodeEditor(pane_id=pane_id, path=self._path)

    @property
    def code_editor(self) -> CodeEditor:
        return self.query_one(CodeEditor)


# ── Integration tests ─────────────────────────────────────────────────────────


async def test_file_load_detects_crlf(tmp_path: Path):
    """Loading a CRLF file → editor.line_ending == 'crlf'."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _LineEndingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        line_ending = app.code_editor.line_ending

    assert line_ending == "crlf"


async def test_file_load_detects_lf(tmp_path: Path):
    """Loading an LF file → editor.line_ending == 'lf'."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _LineEndingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        line_ending = app.code_editor.line_ending

    assert line_ending == "lf"


async def test_change_line_ending_updates_reactive(tmp_path: Path):
    """Apply CRLF → editor.line_ending == 'crlf'."""
    from textual.widgets import Select

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _LineEndingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_line_ending()
        await pilot.pause()

        app.screen.query_one(Select).value = "crlf"
        await pilot.click("#apply")
        await pilot.pause()

        line_ending = app.screen_stack[0].query_one(CodeEditor).line_ending

    assert line_ending == "crlf"


async def test_change_line_ending_cancel_no_change(tmp_path: Path):
    """Cancel → line_ending unchanged."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _LineEndingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_line_ending()
        await pilot.pause()

        await pilot.click("#cancel")
        await pilot.pause()

        line_ending = app.screen_stack[0].query_one(CodeEditor).line_ending

    assert line_ending == "lf"


async def test_save_writes_crlf_to_disk(tmp_path: Path):
    """After setting line_ending='crlf' and saving → file contains \\r\\n."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _LineEndingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        # change line ending to CRLF
        from textual.widgets import Select

        editor.action_change_line_ending()
        await pilot.pause()
        app.screen.query_one(Select).value = "crlf"
        await pilot.click("#apply")
        await pilot.pause()

        # save the file
        editor = app.screen_stack[0].query_one(CodeEditor)
        editor.action_save()
        await pilot.pause()

    saved = f.read_bytes()
    assert b"\r\n" in saved


async def test_footer_shows_line_ending(tmp_path: Path):
    """Footer #line_ending_btn label == 'LF'."""
    from textual.widgets import Button

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _LineEndingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        btn = app.query_one("#line_ending_btn", Button)
        label = str(btn.label)

    assert label == "LF"


async def test_change_line_ending_cmd_no_editor(tmp_path: Path):
    """No open file → error notification."""
    from tests.conftest import make_app

    tc_app = make_app(tmp_path)
    notified: list[str] = []

    async with tc_app.run_test() as pilot:
        original_notify = tc_app.notify

        def capture_notify(message, *, severity="information", **kwargs):
            notified.append(f"{severity}:{message}")
            return original_notify(message, severity=severity, **kwargs)

        tc_app.notify = capture_notify  # type: ignore
        tc_app.action_change_line_ending_cmd()
        await pilot.pause()

    assert any("error" in n for n in notified)


async def test_select_crlf_shows_warning_toast(tmp_path: Path):
    """Apply CRLF → warning notification shown."""
    from textual.widgets import Select

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _LineEndingTestApp(path=f)
    notified: list[str] = []

    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        original_notify = editor.notify

        def capture_notify(message, *, severity="information", **kwargs):
            notified.append(f"{severity}:{message}")
            return original_notify(message, severity=severity, **kwargs)

        editor.notify = capture_notify  # type: ignore

        editor.action_change_line_ending()
        await pilot.pause()
        app.screen.query_one(Select).value = "crlf"
        await pilot.click("#apply")
        await pilot.pause()

    assert any("warning" in n for n in notified)


async def test_select_lf_no_warning_toast(tmp_path: Path):
    """Apply LF → no warning notification."""
    from textual.widgets import Select

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _LineEndingTestApp(path=f)
    notified: list[str] = []

    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        original_notify = editor.notify

        def capture_notify(message, *, severity="information", **kwargs):
            notified.append(f"{severity}:{message}")
            return original_notify(message, severity=severity, **kwargs)

        editor.notify = capture_notify  # type: ignore

        editor.action_change_line_ending()
        await pilot.pause()
        app.screen.query_one(Select).value = "lf"
        await pilot.click("#apply")
        await pilot.pause()

    assert not any("warning" in n for n in notified)


class _NotifyCapturingApp(App):
    """Test app that overrides app.notify to capture on_mount warnings."""

    def __init__(self, path: Path):
        super().__init__()
        self._path = path
        self.notified: list[str] = []

    def compose(self) -> ComposeResult:
        pane_id = CodeEditor.generate_pane_id()
        yield CodeEditor(pane_id=pane_id, path=self._path)

    def notify(self, message, *, severity="information", **kwargs):
        self.notified.append(f"{severity}:{message}")
        return super().notify(message, severity=severity, **kwargs)

    @property
    def code_editor(self) -> CodeEditor:
        return self.query_one(CodeEditor)


async def test_open_crlf_file_shows_warning_toast(tmp_path: Path):
    """Opening a CRLF file → warning notification from on_mount."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()

    assert any("warning" in n for n in app.notified)


async def test_open_lf_file_no_warning_toast(tmp_path: Path):
    """Opening an LF file → no warning notification."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()

    assert not any("warning" in n for n in app.notified)
