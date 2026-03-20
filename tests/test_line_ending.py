"""
Line ending conversion feature tests.

Unit tests: _detect_line_ending, _convert_line_ending helper functions
Integration tests: action_change_line_ending via ChangeLineEndingModalScreen
"""

from pathlib import Path

from textual.app import App, ComposeResult

from textual_code.widgets.code_editor import (
    CodeEditor,
    CodeEditorFooter,
    _convert_line_ending,
    _detect_line_ending,
    _insert_final_newline,
    _remove_final_newline,
    _trim_trailing_whitespace,
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


# ── _trim_trailing_whitespace unit tests ──────────────────────────────────────


def test_trim_trailing_whitespace_spaces():
    """Trailing spaces removed from each line."""
    assert _trim_trailing_whitespace("hello   \nworld  \n") == "hello\nworld\n"


def test_trim_trailing_whitespace_tabs():
    """Trailing tabs removed from each line."""
    assert _trim_trailing_whitespace("hello\t\nworld\t\n") == "hello\nworld\n"


def test_trim_trailing_whitespace_mixed():
    """Mixed trailing whitespace (spaces + tabs) removed."""
    assert _trim_trailing_whitespace("hello \t \nworld\n") == "hello\nworld\n"


def test_trim_trailing_whitespace_no_trailing():
    """No trailing whitespace → unchanged."""
    assert _trim_trailing_whitespace("hello\nworld\n") == "hello\nworld\n"


def test_trim_trailing_whitespace_empty():
    """Empty string → empty string."""
    assert _trim_trailing_whitespace("") == ""


def test_trim_trailing_whitespace_preserves_leading():
    """Leading whitespace is preserved."""
    assert _trim_trailing_whitespace("  hello  \n  world  \n") == "  hello\n  world\n"


def test_trim_trailing_whitespace_blank_lines():
    """Blank lines with only spaces become empty lines."""
    assert _trim_trailing_whitespace("hello\n   \nworld\n") == "hello\n\nworld\n"


# ── _insert_final_newline unit tests ─────────────────────────────────────────


def test_insert_final_newline_missing():
    """Text not ending with newline gets one appended."""
    assert _insert_final_newline("hello") == "hello\n"


def test_insert_final_newline_already_present():
    """Text ending with newline → unchanged."""
    assert _insert_final_newline("hello\n") == "hello\n"


def test_insert_final_newline_empty():
    """Empty string → empty string (no newline added)."""
    assert _insert_final_newline("") == ""


def test_insert_final_newline_only_newline():
    """Single newline → unchanged."""
    assert _insert_final_newline("\n") == "\n"


# ── _remove_final_newline unit tests ─────────────────────────────────────────


def test_remove_final_newline_present():
    """Trailing newline removed."""
    assert _remove_final_newline("hello\n") == "hello"


def test_remove_final_newline_multiple():
    """Multiple trailing newlines all removed."""
    assert _remove_final_newline("hello\n\n\n") == "hello"


def test_remove_final_newline_absent():
    """No trailing newline → unchanged."""
    assert _remove_final_newline("hello") == "hello"


def test_remove_final_newline_empty():
    """Empty string → empty string."""
    assert _remove_final_newline("") == ""


# ── Integration test app ──────────────────────────────────────────────────────


class _LineEndingTestApp(App):
    """Test app containing a CodeEditor for integration tests."""

    def __init__(self, path: Path | None = None, *, warn_line_ending: bool = True):
        super().__init__()
        self._path = path
        self._warn_line_ending = warn_line_ending

    def compose(self) -> ComposeResult:
        pane_id = CodeEditor.generate_pane_id()
        yield CodeEditor(
            pane_id=pane_id,
            path=self._path,
            default_warn_line_ending=self._warn_line_ending,
        )
        yield CodeEditorFooter()

    async def on_mount(self) -> None:
        footer = self.query_one(CodeEditorFooter)
        footer.line_ending = self.query_one(CodeEditor).line_ending

    def on_code_editor_footer_state_changed(
        self, event: CodeEditor.FooterStateChanged
    ) -> None:
        footer = self.query_one(CodeEditorFooter)
        footer.line_ending = event.code_editor.line_ending

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

    tc_app = make_app(tmp_path, light=True)
    notified: list[str] = []

    async with tc_app.run_test() as pilot:
        original_notify = tc_app.notify

        def capture_notify(message, *, severity="information", **kwargs):
            notified.append(f"{severity}:{message}")
            return original_notify(message, severity=severity, **kwargs)

        tc_app.notify = capture_notify  # type: ignore[method-assign]  # monkey-patch to capture notifications in test
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

        editor.notify = capture_notify  # type: ignore[method-assign]  # monkey-patch to capture notifications in test

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

        editor.notify = capture_notify  # type: ignore[method-assign]  # monkey-patch to capture notifications in test

        editor.action_change_line_ending()
        await pilot.pause()
        app.screen.query_one(Select).value = "lf"
        await pilot.click("#apply")
        await pilot.pause()

    assert not any("warning" in n for n in notified)


class _NotifyCapturingApp(App):
    """Test app that overrides app.notify to capture on_mount warnings."""

    def __init__(self, path: Path, *, warn_line_ending: bool = True):
        super().__init__()
        self._path = path
        self._warn_line_ending = warn_line_ending
        self.notified: list[str] = []

    def compose(self) -> ComposeResult:
        pane_id = CodeEditor.generate_pane_id()
        yield CodeEditor(
            pane_id=pane_id,
            path=self._path,
            default_warn_line_ending=self._warn_line_ending,
        )

    def notify(self, message, *, severity="information", **kwargs):
        self.notified.append(f"{severity}:{message}")
        return super().notify(message, severity=severity, **kwargs)

    @property
    def code_editor(self) -> CodeEditor:
        return self.query_one(CodeEditor)


async def test_open_crlf_file_no_warning_on_open(tmp_path: Path):
    """Opening a CRLF file → no warning notification (moved to copy/cut/paste)."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()

    assert not any("warning" in n for n in app.notified)


async def test_open_lf_file_no_warning_toast(tmp_path: Path):
    """Opening an LF file → no warning notification."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()

    assert not any("warning" in n for n in app.notified)


# ── save_level visibility tests ───────────────────────────────────────────────


async def test_footer_line_ending_modal_no_save_level(tmp_path: Path):
    """action_change_line_ending (footer path) → modal has no #save_level widget."""
    from textual_code.modals import ChangeLineEndingModalScreen

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")
    app = _LineEndingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_line_ending()
        await pilot.pause()

        assert isinstance(app.screen, ChangeLineEndingModalScreen)
        assert len(app.screen.query("#save_level")) == 0


# ── clipboard warning tests ──────────────────────────────────────────────────


async def test_copy_crlf_file_shows_warning_toast(tmp_path: Path):
    """Copy in a CRLF file (multiline) → warning notification shown."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.notified.clear()  # discard any mount-time notifications
        # select all text then copy (multiline → triggers warning)
        app.code_editor.editor.select_all()
        await pilot.pause()
        app.code_editor.editor.action_copy()
        await pilot.pause()

    assert any("warning" in n for n in app.notified)


async def test_cut_crlf_file_shows_warning_toast(tmp_path: Path):
    """Cut in a CRLF file (no selection → whole line with newline) → warning shown."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.notified.clear()
        # no selection → cut whole line (includes newline)
        app.code_editor.editor.action_cut()
        await pilot.pause()

    assert any("warning" in n for n in app.notified)


async def test_paste_crlf_file_shows_warning_toast(tmp_path: Path):
    """Paste multiline text in a CRLF file → warning notification shown."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.notified.clear()
        # put multiline text on clipboard, then paste
        app.copy_to_clipboard("line1\nline2")
        app.code_editor.editor.action_paste()
        await pilot.pause()

    assert any("warning" in n for n in app.notified)


async def test_copy_lf_file_no_warning(tmp_path: Path):
    """Copy in an LF file → no warning notification."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.notified.clear()
        app.code_editor.editor.select_all()
        await pilot.pause()
        app.code_editor.editor.action_copy()
        await pilot.pause()

    assert not any("warning" in n for n in app.notified)


async def test_copy_crlf_warning_only_once(tmp_path: Path):
    """Copy twice in CRLF file → warning appears only once."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.notified.clear()
        # first copy
        app.code_editor.editor.select_all()
        await pilot.pause()
        app.code_editor.editor.action_copy()
        await pilot.pause()
        # second copy
        app.code_editor.editor.action_copy()
        await pilot.pause()

    warning_count = sum(1 for n in app.notified if "warning" in n)
    assert warning_count == 1


async def test_copy_single_line_crlf_no_warning(tmp_path: Path):
    """Single-line copy in CRLF file → no warning (no newline in copied text)."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.notified.clear()
        # select only "hello" on the first line (no newline)
        from textual.widgets._text_area import Selection

        app.code_editor.editor.selection = Selection((0, 0), (0, 5))
        await pilot.pause()
        app.code_editor.editor.action_copy()
        await pilot.pause()

    assert not any("warning" in n for n in app.notified)


async def test_copy_crlf_no_warning_when_disabled(tmp_path: Path):
    """Copy in CRLF file with warn_line_ending=False → no warning."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _NotifyCapturingApp(path=f, warn_line_ending=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.notified.clear()
        app.code_editor.editor.select_all()
        await pilot.pause()
        app.code_editor.editor.action_copy()
        await pilot.pause()

    assert not any("warning" in n for n in app.notified)


async def test_open_crlf_file_no_warning_when_disabled(tmp_path: Path):
    """Opening a CRLF file with warn_line_ending=False → no warning."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _NotifyCapturingApp(path=f, warn_line_ending=False)
    async with app.run_test() as pilot:
        await pilot.pause()

    assert not any("warning" in n for n in app.notified)


async def test_select_crlf_no_warning_when_disabled(tmp_path: Path):
    """Apply CRLF with warn_line_ending=False → no warning."""
    from textual.widgets import Select

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _LineEndingTestApp(path=f, warn_line_ending=False)
    notified: list[str] = []

    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        original_notify = editor.notify

        def capture_notify(message, *, severity="information", **kwargs):
            notified.append(f"{severity}:{message}")
            return original_notify(message, severity=severity, **kwargs)

        editor.notify = capture_notify  # type: ignore[method-assign]  # monkey-patch to capture notifications in test

        editor.action_change_line_ending()
        await pilot.pause()
        app.screen.query_one(Select).value = "crlf"
        await pilot.click("#apply")
        await pilot.pause()

    assert not any("warning" in n for n in notified)
