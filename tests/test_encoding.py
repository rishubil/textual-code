"""
Encoding feature tests.

Unit tests: _detect_encoding helper function
Integration tests: encoding detection on load, modal interaction, save, footer display
"""

from pathlib import Path

from textual.app import App, ComposeResult

from textual_code.widgets.code_editor import (
    CodeEditor,
    CodeEditorFooter,
    _detect_encoding,
)

# ── _detect_encoding unit tests ───────────────────────────────────────────────


def test_detect_encoding_utf8_bom():
    """BOM-prefixed UTF-8 bytes → 'utf-8-sig'."""
    raw = b"\xef\xbb\xbfhello"
    assert _detect_encoding(raw) == "utf-8-sig"


def test_detect_encoding_utf16_le_bom():
    """UTF-16 LE BOM → 'utf-16'."""
    raw = b"\xff\xfeh\x00e\x00l\x00l\x00o\x00"
    assert _detect_encoding(raw) == "utf-16"


def test_detect_encoding_utf16_be_bom():
    """UTF-16 BE BOM → 'utf-16'."""
    raw = b"\xfe\xff\x00h\x00e\x00l\x00l\x00o"
    assert _detect_encoding(raw) == "utf-16"


def test_detect_encoding_pure_ascii():
    """Pure ASCII bytes → 'utf-8'."""
    assert _detect_encoding(b"hello") == "utf-8"


def test_detect_encoding_valid_utf8():
    """Valid UTF-8 bytes → 'utf-8'."""
    assert _detect_encoding("Ünïcödë".encode()) == "utf-8"


def test_detect_encoding_latin1_fallback():
    """Bytes that are not valid UTF-8 → some 8-bit encoding (not UTF-8)."""
    result = _detect_encoding(b"\xe9\xe0\xfc")
    assert result != "utf-8"


def test_detect_encoding_empty():
    """Empty bytes → 'utf-8' (default)."""
    assert _detect_encoding(b"") == "utf-8"


# ── Integration test app ──────────────────────────────────────────────────────


class _EncodingTestApp(App):
    """Test app containing a CodeEditor for integration tests."""

    def __init__(self, path: Path | None = None):
        super().__init__()
        self._path = path

    def compose(self) -> ComposeResult:
        pane_id = CodeEditor.generate_pane_id()
        yield CodeEditor(pane_id=pane_id, path=self._path)
        yield CodeEditorFooter()

    async def on_mount(self) -> None:
        editor = self.query_one(CodeEditor)
        footer = self.query_one(CodeEditorFooter)
        footer.encoding = editor.encoding

    def on_code_editor_footer_state_changed(
        self, event: CodeEditor.FooterStateChanged
    ) -> None:
        footer = self.query_one(CodeEditorFooter)
        footer.encoding = event.code_editor.encoding

    def on_button_pressed(self, event) -> None:
        if event.button.id == "encoding_btn":
            event.stop()
            self.query_one(CodeEditor).action_change_encoding()

    @property
    def code_editor(self) -> CodeEditor:
        return self.query_one(CodeEditor)


# ── Integration tests: file loading ──────────────────────────────────────────


async def test_file_load_detects_utf8(tmp_path: Path):
    """Loading a plain UTF-8 file → editor.encoding == 'utf-8'."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        encoding = app.code_editor.encoding

    assert encoding == "utf-8"


async def test_file_load_detects_utf8_bom(tmp_path: Path):
    """Loading a UTF-8 BOM file → editor.encoding == 'utf-8-sig'."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"\xef\xbb\xbfhello\nworld")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        encoding = app.code_editor.encoding

    assert encoding == "utf-8-sig"


async def test_file_load_detects_utf16(tmp_path: Path):
    """Loading a UTF-16 file → editor.encoding == 'utf-16'."""
    f = tmp_path / "test.txt"
    f.write_bytes("hello\nworld".encode("utf-16"))

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        encoding = app.code_editor.encoding

    assert encoding == "utf-16"


async def test_file_load_detects_latin1(tmp_path: Path):
    """Loading a Latin-1 file → editor.encoding == 'latin-1'."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"\xe9\xe0\xfc\n")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        encoding = app.code_editor.encoding

    assert encoding == "latin-1"


async def test_file_load_bom_not_in_text(tmp_path: Path):
    """Loading a UTF-8 BOM file → editor text does NOT start with BOM char."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"\xef\xbb\xbfhello")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        text = app.code_editor.text

    assert not text.startswith("\ufeff")


async def test_file_load_latin1_readable(tmp_path: Path):
    """Loading a Latin-1 file → editor text contains the decoded string."""
    f = tmp_path / "test.txt"
    f.write_bytes("élève\n".encode("latin-1"))

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        text = app.code_editor.text

    assert "élève" in text


# ── Integration tests: modal interaction ─────────────────────────────────────


async def test_change_encoding_updates_reactive(tmp_path: Path):
    """Apply 'latin-1' → editor.encoding == 'latin-1'."""
    from textual.widgets import Select

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_encoding()
        await pilot.pause()

        app.screen.query_one(Select).value = "latin-1"
        await pilot.click("#apply")
        await pilot.pause()

        encoding = app.screen_stack[0].query_one(CodeEditor).encoding

    assert encoding == "latin-1"


async def test_change_encoding_cancel_no_change(tmp_path: Path):
    """Cancel → encoding unchanged."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_encoding()
        await pilot.pause()

        await pilot.click("#cancel")
        await pilot.pause()

        encoding = app.screen_stack[0].query_one(CodeEditor).encoding

    assert encoding == "utf-8"


async def test_encoding_button_opens_modal(tmp_path: Path):
    """Clicking #encoding_btn opens ChangeEncodingModalScreen."""
    from textual_code.modals import ChangeEncodingModalScreen

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#encoding_btn")
        await pilot.pause()
        assert isinstance(app.screen, ChangeEncodingModalScreen)


# ── Integration tests: save ───────────────────────────────────────────────────


async def test_save_writes_utf8_bom_bytes(tmp_path: Path):
    """Saving with encoding 'utf-8-sig' → file starts with UTF-8 BOM."""
    from textual.widgets import Select

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_encoding()
        await pilot.pause()
        app.screen.query_one(Select).value = "utf-8-sig"
        await pilot.click("#apply")
        await pilot.pause()

        editor = app.screen_stack[0].query_one(CodeEditor)
        editor.action_save()
        await pilot.pause()

    saved = f.read_bytes()
    assert saved.startswith(b"\xef\xbb\xbf")


async def test_save_writes_latin1_bytes(tmp_path: Path):
    """Saving 'élève' with encoding 'latin-1' → correct bytes on disk."""
    f = tmp_path / "test.txt"
    # Write the content as UTF-8 initially, then change encoding via modal
    f.write_bytes("élève\n".encode())

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        # Change encoding to latin-1
        from textual.widgets import Select

        editor.action_change_encoding()
        await pilot.pause()
        app.screen.query_one(Select).value = "latin-1"
        await pilot.click("#apply")
        await pilot.pause()

        editor = app.screen_stack[0].query_one(CodeEditor)
        editor.action_save()
        await pilot.pause()

    saved = f.read_bytes()
    assert saved == "élève\n".encode("latin-1")


async def test_save_utf16_roundtrip(tmp_path: Path):
    """Loading UTF-16 → saving → file contains BOM."""
    f = tmp_path / "test.txt"
    f.write_bytes("hello\n".encode("utf-16"))

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        editor.action_save()
        await pilot.pause()

    saved = f.read_bytes()
    # UTF-16 encoded files always start with a BOM
    assert saved.startswith(b"\xff\xfe") or saved.startswith(b"\xfe\xff")


async def test_save_as_preserves_encoding(tmp_path: Path):
    """save_as with utf-8-sig encoding → new file starts with BOM."""
    from textual.widgets import Input

    f = tmp_path / "test.txt"
    f.write_bytes(b"\xef\xbb\xbfhello")
    new_path = tmp_path / "new_test.txt"

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.encoding == "utf-8-sig"

        editor.action_save_as()
        await pilot.pause()

        app.screen.query_one(Input).value = str(new_path)
        await pilot.click("#save")
        await pilot.pause()

    saved = new_path.read_bytes()
    assert saved.startswith(b"\xef\xbb\xbf")


# ── Integration tests: footer display ────────────────────────────────────────


async def test_footer_shows_utf8_label(tmp_path: Path):
    """Footer #encoding_btn label == 'UTF-8' for a UTF-8 file."""
    from textual.widgets import Button

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\nworld")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        btn = app.query_one("#encoding_btn", Button)
        label = str(btn.label)

    assert label == "UTF-8"


async def test_footer_shows_utf8_bom_label(tmp_path: Path):
    """Footer #encoding_btn label == 'UTF-8 BOM' for a BOM file."""
    from textual.widgets import Button

    f = tmp_path / "test.txt"
    f.write_bytes(b"\xef\xbb\xbfhello")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        btn = app.query_one("#encoding_btn", Button)
        label = str(btn.label)

    assert label == "UTF-8 BOM"


async def test_footer_shows_latin1_label(tmp_path: Path):
    """Footer #encoding_btn label shows Latin-1 for a Latin-1 file."""
    from textual.widgets import Button

    f = tmp_path / "test.txt"
    f.write_bytes(b"\xe9\xe0\xfc\n")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        btn = app.query_one("#encoding_btn", Button)
        label = str(btn.label)

    assert "Latin-1" in label


# ── Integration tests: command palette ───────────────────────────────────────


async def test_encoding_cmd_no_editor(tmp_path: Path):
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
        tc_app.action_change_encoding_cmd()
        await pilot.pause()

    assert any("error" in n for n in notified)


async def test_encoding_cmd_with_editor(tmp_path: Path):
    """With open file → ChangeEncodingModalScreen is pushed."""
    from tests.conftest import make_app
    from textual_code.modals import ChangeEncodingModalScreen

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello")

    tc_app = make_app(tmp_path, open_file=f)
    async with tc_app.run_test() as pilot:
        await pilot.pause()
        tc_app.action_change_encoding_cmd()
        await pilot.pause()
        assert isinstance(tc_app.screen, ChangeEncodingModalScreen)


# ── New encoding detection tests ──────────────────────────────────────────────


def test_detect_encoding_utf32_le_bom():
    """UTF-32 LE BOM → 'utf-32'."""
    raw = b"\xff\xfe\x00\x00" + "hi".encode("utf-32-le")
    assert _detect_encoding(raw) == "utf-32"


def test_detect_encoding_utf32_be_bom():
    """UTF-32 BE BOM → 'utf-32'."""
    raw = b"\x00\x00\xfe\xff" + "hi".encode("utf-32-be")
    assert _detect_encoding(raw) == "utf-32"


# ── New encoding modal option tests ──────────────────────────────────────────


async def test_encoding_modal_can_select_gbk(tmp_path: Path):
    """Modal allows selecting gbk encoding."""
    from textual.widgets import Select

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_encoding()
        await pilot.pause()
        app.screen.query_one(Select).value = "gbk"
        await pilot.click("#apply")
        await pilot.pause()
        encoding = app.screen_stack[0].query_one(CodeEditor).encoding

    assert encoding == "gbk"


async def test_encoding_modal_can_select_shift_jis(tmp_path: Path):
    """Modal allows selecting shift_jis encoding."""
    from textual.widgets import Select

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_encoding()
        await pilot.pause()
        app.screen.query_one(Select).value = "shift_jis"
        await pilot.click("#apply")
        await pilot.pause()
        encoding = app.screen_stack[0].query_one(CodeEditor).encoding

    assert encoding == "shift_jis"


async def test_encoding_modal_can_select_euc_kr(tmp_path: Path):
    """Modal allows selecting euc_kr encoding."""
    from textual.widgets import Select

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_encoding()
        await pilot.pause()
        app.screen.query_one(Select).value = "euc_kr"
        await pilot.click("#apply")
        await pilot.pause()
        encoding = app.screen_stack[0].query_one(CodeEditor).encoding

    assert encoding == "euc_kr"


async def test_encoding_modal_can_select_cp1251(tmp_path: Path):
    """Modal allows selecting cp1251 (Cyrillic Windows) encoding."""
    from textual.widgets import Select

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello")

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_encoding()
        await pilot.pause()
        app.screen.query_one(Select).value = "cp1251"
        await pilot.click("#apply")
        await pilot.pause()
        encoding = app.screen_stack[0].query_one(CodeEditor).encoding

    assert encoding == "cp1251"


# ── New encoding file load detection tests (charset-normalizer) ───────────────


async def test_file_load_detects_gbk(tmp_path: Path):
    """Loading a GBK file → editor.encoding is a gbk/gb family encoding."""
    f = tmp_path / "test.txt"
    # Pre-encoded GBK bytes: repeated valid GBK two-byte sequences.
    # Each pair is a valid CJK character (lead 0xB0-0xF7, trail 0xA1-0xFE).
    _GBK_CHAR = b"\xd6\xd0\xce\xc4\xb2\xe2\xca\xd4\xc4\xda\xc8\xdd\xb8\xf1\xca\xbd"
    f.write_bytes(_GBK_CHAR * 30)  # ~480 bytes for reliable detection

    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        encoding = app.code_editor.encoding

    assert encoding in ("gbk", "gb2312", "gb18030")


# ── save_level visibility tests ───────────────────────────────────────────────


async def test_footer_encoding_modal_no_save_level(tmp_path: Path):
    """action_change_encoding (footer path) → modal has no #save_level widget."""
    from textual_code.modals import ChangeEncodingModalScreen

    f = tmp_path / "test.txt"
    f.write_text("hello")
    app = _EncodingTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_encoding()
        await pilot.pause()

        assert isinstance(app.screen, ChangeEncodingModalScreen)
        assert len(app.screen.query("#save_level")) == 0
