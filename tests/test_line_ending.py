"""
줄 끝 변환 기능 테스트.

단위 테스트: _detect_line_ending, _convert_line_ending 헬퍼 함수
통합 테스트: action_change_line_ending via ChangeLineEndingModalScreen
"""

from pathlib import Path

from textual.app import App, ComposeResult

from textual_code.widgets.code_editor import (
    CodeEditor,
    _convert_line_ending,
    _detect_line_ending,
)

# ── _detect_line_ending 단위 테스트 ──────────────────────────────────────────


def test_detect_lf_only():
    """\n만 포함된 텍스트 → 'lf'."""
    assert _detect_line_ending("\nhello") == "lf"


def test_detect_crlf():
    """\r\n 포함 텍스트 → 'crlf'."""
    assert _detect_line_ending("hello\r\nworld") == "crlf"


def test_detect_cr_only():
    """\r만 포함된 텍스트 → 'cr'."""
    assert _detect_line_ending("hello\rworld") == "cr"


def test_detect_empty_string():
    """빈 문자열 → 'lf' (기본값)."""
    assert _detect_line_ending("") == "lf"


def test_detect_crlf_priority():
    """\r\n과 \r 혼재 시 'crlf' 우선."""
    assert _detect_line_ending("a\r\nb\rc") == "crlf"


# ── _convert_line_ending 단위 테스트 ─────────────────────────────────────────


def test_convert_lf_noop():
    """ "lf" 지정 시 텍스트 그대로."""
    assert _convert_line_ending("hello\nworld", "lf") == "hello\nworld"


def test_convert_to_crlf():
    """'hello\nworld' → 'hello\r\nworld'."""
    assert _convert_line_ending("hello\nworld", "crlf") == "hello\r\nworld"


def test_convert_to_cr():
    """'hello\nworld' → 'hello\rworld'."""
    assert _convert_line_ending("hello\nworld", "cr") == "hello\rworld"


def test_convert_multiline_crlf():
    """여러 \n 모두 \r\n으로 교체."""
    text = "a\nb\nc"
    assert _convert_line_ending(text, "crlf") == "a\r\nb\r\nc"


def test_convert_empty_string():
    """빈 문자열 → 빈 문자열."""
    assert _convert_line_ending("", "crlf") == ""


# ── 통합 테스트용 앱 ─────────────────────────────────────────────────────────


class _LineEndingTestApp(App):
    """CodeEditor를 포함한 통합 테스트용 앱."""

    def __init__(self, path: Path | None = None):
        super().__init__()
        self._path = path

    def compose(self) -> ComposeResult:
        pane_id = CodeEditor.generate_pane_id()
        yield CodeEditor(pane_id=pane_id, path=self._path)

    @property
    def code_editor(self) -> CodeEditor:
        return self.query_one(CodeEditor)


# ── 통합 테스트 ───────────────────────────────────────────────────────────────


async def test_file_load_detects_crlf(tmp_path: Path):
    """CRLF 파일 로드 → editor.line_ending == 'crlf'."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _LineEndingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        line_ending = app.code_editor.line_ending

    assert line_ending == "crlf"


async def test_file_load_detects_lf(tmp_path: Path):
    """LF 파일 로드 → editor.line_ending == 'lf'."""
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
    """Cancel → line_ending 불변."""
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
    """line_ending='crlf' 후 저장 → 파일에 \r\n."""
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
    """footer #line_ending_btn 라벨 == 'LF'."""
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
    """열린 파일 없으면 error notify."""
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
    """Apply CRLF → warning notify 표시."""
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
    """Apply LF → warning notify 없음."""
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
    """on_mount warning 캡처를 위해 app.notify를 오버라이드한 테스트 앱."""

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
    """CRLF 파일 로드 시 on_mount에서 warning notify."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\r\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()

    assert any("warning" in n for n in app.notified)


async def test_open_lf_file_no_warning_toast(tmp_path: Path):
    """LF 파일 로드 시 warning notify 없음."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _NotifyCapturingApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()

    assert not any("warning" in n for n in app.notified)
