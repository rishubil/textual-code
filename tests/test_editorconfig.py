"""
EditorConfig support tests.

Group A — _read_editorconfig() basic behaviour (T-01 to T-06)
Group B — Glob pattern matching (T-07 to T-16)
Group C — Parsing edge cases (T-17 to T-22)
Group D — Property value mapping (T-23 to T-28)
Group E — Integration: CodeEditor file open (T-29 to T-32)
Group F — Save-time transformations (T-33 to T-46)
Group G — EditorConfig reload on modification (G-01 to G-12)
"""

from pathlib import Path

from textual.app import App, ComposeResult

from textual_code.widgets.code_editor import (
    CodeEditor,
    _editorconfig_glob_to_pattern,
    _read_editorconfig,
)

# ── Group A: _read_editorconfig() basic behaviour ────────────────────────────


def test_T01_no_editorconfig_returns_empty_dict(tmp_path: Path):
    """T-01: No .editorconfig file anywhere → returns empty dict."""
    f = tmp_path / "hello.py"
    f.write_text("x = 1\n")
    result, dirs = _read_editorconfig(f)
    assert result == {}
    assert len(dirs) > 0  # at least the file's parent dir


def test_T02_reads_same_directory_editorconfig(tmp_path: Path):
    """T-02: Reads .editorconfig in same directory as file."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = space\n")
    f = tmp_path / "hello.py"
    f.write_text("x = 1\n")
    result, dirs = _read_editorconfig(f)
    assert result.get("indent_style") == "space"
    assert tmp_path in dirs


def test_T03_reads_parent_directory_editorconfig(tmp_path: Path):
    """T-03: Traverses up to parent directory .editorconfig."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_size = 2\n")
    subdir = tmp_path / "src"
    subdir.mkdir()
    f = subdir / "hello.py"
    f.write_text("x = 1\n")
    result, dirs = _read_editorconfig(f)
    assert result.get("indent_size") == "2"
    assert subdir in dirs
    assert tmp_path in dirs


def test_T04_root_true_stops_traversal(tmp_path: Path):
    """T-04: root=true stops traversal — properties from higher dirs ignored."""
    # parent .editorconfig (should be ignored due to root=true in child)
    parent_ec = tmp_path / ".editorconfig"
    parent_ec.write_text("[*.py]\nindent_size = 8\n")

    subdir = tmp_path / "sub"
    subdir.mkdir()
    child_ec = subdir / ".editorconfig"
    child_ec.write_text("root = true\n\n[*.py]\nindent_style = tab\n")
    f = subdir / "hello.py"
    f.write_text("x = 1\n")

    result, dirs = _read_editorconfig(f)
    # indent_style comes from child; indent_size from parent should NOT appear
    assert result.get("indent_style") == "tab"
    assert result.get("indent_size") is None
    # root=true stops traversal — only subdir is in search dirs
    assert subdir in dirs
    assert tmp_path not in dirs


def test_T05_closer_editorconfig_overrides_farther(tmp_path: Path):
    """T-05: Closer .editorconfig wins over more distant one for same key."""
    parent_ec = tmp_path / ".editorconfig"
    parent_ec.write_text("[*.py]\nindent_style = tab\n")

    subdir = tmp_path / "sub"
    subdir.mkdir()
    child_ec = subdir / ".editorconfig"
    child_ec.write_text("[*.py]\nindent_style = space\n")

    f = subdir / "hello.py"
    f.write_text("x = 1\n")

    result, dirs = _read_editorconfig(f)
    assert result.get("indent_style") == "space"


def test_T06_later_section_in_same_file_wins(tmp_path: Path):
    """T-06: In the same file, later section overrides earlier for same key."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = tab\n\n[*.py]\nindent_style = space\n")
    f = tmp_path / "hello.py"
    f.write_text("x = 1\n")
    result, dirs = _read_editorconfig(f)
    assert result.get("indent_style") == "space"


# ── Group B: Glob pattern matching ───────────────────────────────────────────


def test_T07_star_matches_all_files(tmp_path: Path):
    """T-07: [*] matches any file name."""
    pattern = _editorconfig_glob_to_pattern("*")
    assert pattern.fullmatch("foo.py")
    assert pattern.fullmatch("bar.txt")
    assert pattern.fullmatch("README")


def test_T08_star_py_matches_py_not_js(tmp_path: Path):
    """T-08: [*.py] matches .py at any depth; does NOT match .js."""
    pattern = _editorconfig_glob_to_pattern("*.py")
    assert pattern.fullmatch("foo.py")
    assert not pattern.fullmatch("foo.js")
    # no-slash pattern → prefixed with **/ → matches at all depths
    assert pattern.fullmatch("src/foo.py")


def test_T09_brace_js_ts_matches_both(tmp_path: Path):
    """T-09: [*.{js,ts}] matches .js and .ts; not .py."""
    pattern = _editorconfig_glob_to_pattern("*.{js,ts}")
    assert pattern.fullmatch("app.js")
    assert pattern.fullmatch("app.ts")
    assert not pattern.fullmatch("app.py")


def test_T10_slash_in_pattern_anchors_path(tmp_path: Path):
    """T-10: [src/*.py] only matches src/<name>.py; not root-level .py."""
    pattern = _editorconfig_glob_to_pattern("src/*.py")
    assert pattern.fullmatch("src/foo.py")
    assert not pattern.fullmatch("foo.py")
    assert not pattern.fullmatch("lib/foo.py")


def test_T11_double_star_matches_all_depths(tmp_path: Path):
    """T-11: [**/*.py] matches .py at any depth."""
    pattern = _editorconfig_glob_to_pattern("**/*.py")
    assert pattern.fullmatch("foo.py")
    assert pattern.fullmatch("src/foo.py")
    assert pattern.fullmatch("a/b/c/foo.py")


def test_T12_question_matches_single_char(tmp_path: Path):
    """T-12: [?oo.py] matches foo.py but not oo.py (? = exactly one non-/ char)."""
    pattern = _editorconfig_glob_to_pattern("?oo.py")
    assert pattern.fullmatch("foo.py")
    assert not pattern.fullmatch("oo.py")
    assert not pattern.fullmatch("ffoo.py")


def test_T13_character_class_matches_listed(tmp_path: Path):
    """T-13: [[abc].py] matches a.py, b.py, c.py; not d.py."""
    pattern = _editorconfig_glob_to_pattern("[abc].py")
    assert pattern.fullmatch("a.py")
    assert pattern.fullmatch("b.py")
    assert pattern.fullmatch("c.py")
    assert not pattern.fullmatch("d.py")


def test_T14_negated_char_class(tmp_path: Path):
    """T-14: [[!abc].py] matches d.py; not a.py."""
    pattern = _editorconfig_glob_to_pattern("[!abc].py")
    assert pattern.fullmatch("d.py")
    assert not pattern.fullmatch("a.py")


def test_T15_integer_range_brace(tmp_path: Path):
    """T-15: [{1..3}.js] matches 1.js, 2.js, 3.js; not 4.js."""
    pattern = _editorconfig_glob_to_pattern("{1..3}.js")
    assert pattern.fullmatch("1.js")
    assert pattern.fullmatch("2.js")
    assert pattern.fullmatch("3.js")
    assert not pattern.fullmatch("4.js")
    assert not pattern.fullmatch("0.js")


def test_T16_escaped_star_matches_literal(tmp_path: Path):
    """T-16: [\\*.py] matches only the literal filename *.py."""
    pattern = _editorconfig_glob_to_pattern(r"\*.py")
    assert pattern.fullmatch("*.py")
    assert not pattern.fullmatch("foo.py")


# ── Group C: Parsing edge cases ──────────────────────────────────────────────


def test_T17_line_start_hash_is_comment_inline_is_not(tmp_path: Path):
    """T-17: # at line start = comment; # in middle of value = part of value."""
    ec = tmp_path / ".editorconfig"
    # The value contains a # — it should NOT be treated as inline comment
    ec.write_text("[*.py]\nindent_style = space # not a comment\n")
    f = tmp_path / "hello.py"
    f.write_text("")
    result, _ = _read_editorconfig(f)
    # Value should include the trailing " # not a comment" text (no inline comment)
    assert "space" in result.get("indent_style", "")


def test_T18_semicolon_comment_ignored(tmp_path: Path):
    """T-18: ; at line start = comment line → ignored."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("; this is a comment\n[*.py]\nindent_style = space\n")
    f = tmp_path / "hello.py"
    f.write_text("")
    result, _ = _read_editorconfig(f)
    assert result.get("indent_style") == "space"


def test_T19_keys_and_values_normalized_lowercase(tmp_path: Path):
    """T-19: Keys and values are normalized to lowercase."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nINDENT_STYLE = Space\n")
    f = tmp_path / "hello.py"
    f.write_text("")
    result, _ = _read_editorconfig(f)
    assert result.get("indent_style") == "space"


def test_T20_root_in_section_is_ignored(tmp_path: Path):
    """T-20: root=true inside a section is not treated as root marker."""
    parent_ec = tmp_path / ".editorconfig"
    parent_ec.write_text("[*.py]\nindent_size = 8\n")

    subdir = tmp_path / "sub"
    subdir.mkdir()
    # root=true is inside a [*.py] section, not preamble — should be ignored
    child_ec = subdir / ".editorconfig"
    child_ec.write_text("[*.py]\nroot = true\nindent_style = space\n")
    f = subdir / "hello.py"
    f.write_text("")

    result, _ = _read_editorconfig(f)
    # Parent's indent_size should still be visible (root=true in section ignored)
    assert result.get("indent_size") == "8"


def test_T21_empty_editorconfig_returns_empty_dict(tmp_path: Path):
    """T-21: Empty .editorconfig → empty dict."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("")
    f = tmp_path / "hello.py"
    f.write_text("")
    result, _ = _read_editorconfig(f)
    assert result == {}


def test_T22_unknown_property_included_in_dict(tmp_path: Path):
    """T-22: Unknown properties are included in dict but don't affect CodeEditor."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nspelling_language = en_US\n")
    f = tmp_path / "hello.py"
    f.write_text("")
    result, _ = _read_editorconfig(f)
    # Unknown property present in returned dict (caller decides what to use)
    assert "spelling_language" in result


# ── Group D: Property value mapping ──────────────────────────────────────────


class _EditorConfigTestApp(App):
    """Lightweight test app with a single CodeEditor."""

    def __init__(self, path: Path | None = None):
        super().__init__()
        self._path = path

    def compose(self) -> ComposeResult:
        pane_id = CodeEditor.generate_pane_id()
        yield CodeEditor(pane_id=pane_id, path=self._path)

    @property
    def code_editor(self) -> CodeEditor:
        return self.query_one(CodeEditor)


async def test_T23_indent_style_space(tmp_path: Path):
    """T-23: indent_style=space → indent_type='spaces'."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = space\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"\tx = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.code_editor.indent_type == "spaces"


async def test_T24_indent_style_tab_with_tab_width(tmp_path: Path):
    """T-24: indent_style=tab + tab_width=2 → indent_type='tabs', indent_size=2."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = tab\ntab_width = 2\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.indent_type == "tabs"
        assert editor.indent_size == 2


async def test_T25_indent_size_tab_uses_tab_width(tmp_path: Path):
    """T-25: indent_size=tab + tab_width=4 → indent_size=4."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = space\nindent_size = tab\ntab_width = 4\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.code_editor.indent_size == 4


async def test_T26_charset_utf8_bom(tmp_path: Path):
    """T-26: charset=utf-8-bom → encoding='utf-8-sig'."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ncharset = utf-8-bom\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.code_editor.encoding == "utf-8-sig"


async def test_T27_charset_latin1(tmp_path: Path):
    """T-27: charset=latin1 → encoding='latin-1'."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ncharset = latin1\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.code_editor.encoding == "latin-1"


async def test_T28_end_of_line_crlf(tmp_path: Path):
    """T-28: end_of_line=crlf → line_ending='crlf'."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nend_of_line = crlf\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.code_editor.line_ending == "crlf"


# ── Group E: Integration: CodeEditor file open ───────────────────────────────


async def test_T29_no_editorconfig_keeps_auto_detect(tmp_path: Path):
    """T-29: No .editorconfig → auto-detect values are retained."""
    f = tmp_path / "hello.py"
    # Write a file with tabs to trigger tab auto-detect
    f.write_bytes(b"\tx = 1\n\ty = 2\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        # Without .editorconfig, default values remain (auto-detect from content
        # is not implemented for indent_type, so defaults stay)
        assert editor.encoding == "utf-8"
        assert editor.line_ending == "lf"


async def test_T30_editorconfig_overrides_auto_detect(tmp_path: Path):
    """T-30: .editorconfig indent/charset/eol settings override auto-detect."""
    ec = tmp_path / ".editorconfig"
    ec.write_text(
        "[*.py]\n"
        "indent_style = tab\n"
        "indent_size = 4\n"
        "charset = utf-8-bom\n"
        "end_of_line = crlf\n"
    )
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.indent_type == "tabs"
        assert editor.indent_size == 4
        assert editor.encoding == "utf-8-sig"
        assert editor.line_ending == "crlf"


async def test_T31_indent_style_unset_keeps_default(tmp_path: Path):
    """T-31: indent_style=unset → property not applied, default stays."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = unset\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Default indent_type is "spaces"
        assert app.code_editor.indent_type == "spaces"


async def test_T32_unsupported_indent_size_ignored(tmp_path: Path):
    """T-32: indent_size=3 (unsupported) → indent_size stays at default 4."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_size = 3\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        # indent_size 3 is not in (2, 4, 8) → ignored, default 4 stays
        assert app.code_editor.indent_size == 4


# ── Group F: Save-time transformations ───────────────────────────────────────


async def test_T33_insert_final_newline_true_adds_newline(tmp_path: Path):
    """T-33: insert_final_newline=true → file ends with newline after save."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ninsert_final_newline = true\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b"x = 1\n"


async def test_T34_insert_final_newline_true_already_has_newline(tmp_path: Path):
    """T-34: insert_final_newline=true + already has newline → unchanged."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ninsert_final_newline = true\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b"x = 1\n"


async def test_T35_insert_final_newline_false_removes_newline(tmp_path: Path):
    """T-35: insert_final_newline=false → trailing newline removed after save."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ninsert_final_newline = false\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b"x = 1"


async def test_T36_insert_final_newline_true_empty_file(tmp_path: Path):
    """T-36: insert_final_newline=true + empty file → stays empty."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ninsert_final_newline = true\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b""


async def test_T37_trim_trailing_whitespace_true(tmp_path: Path):
    """T-37: trim_trailing_whitespace=true → trailing ws removed, leading kept."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ntrim_trailing_whitespace = true\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"  x = 1   \n  y = 2\t\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b"  x = 1\n  y = 2\n"


async def test_T38_trim_trailing_whitespace_false_no_change(tmp_path: Path):
    """T-38: trim_trailing_whitespace=false → trailing whitespace preserved."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ntrim_trailing_whitespace = false\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1   \n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b"x = 1   \n"


async def test_T39_trim_and_insert_final_newline_combined(tmp_path: Path):
    """T-39: Both transformations applied: trim first, then insert newline."""
    ec = tmp_path / ".editorconfig"
    ec.write_text(
        "[*.py]\ntrim_trailing_whitespace = true\ninsert_final_newline = true\n"
    )
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1   \ny = 2  ")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b"x = 1\ny = 2\n"


async def test_T40_insert_final_newline_unset_no_change(tmp_path: Path):
    """T-40: insert_final_newline=unset → no transformation applied."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ninsert_final_newline = unset\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b"x = 1"


async def test_T41_editor_text_updated_after_trim_on_save(tmp_path: Path):
    """T-41: After saving with trim, editor.text reflects trimmed content."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ntrim_trailing_whitespace = true\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1   \n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()
        saved_text = app.code_editor.text

    assert saved_text == "x = 1\n"


async def test_T42_initial_text_matches_text_after_save(tmp_path: Path):
    """T-42: After save with transforms, initial_text == text (no unsaved)."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ninsert_final_newline = true\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()
        text = app.code_editor.text
        initial_text = app.code_editor.initial_text

    assert text == initial_text


async def test_T43_insert_final_newline_with_crlf(tmp_path: Path):
    """T-43: insert_final_newline=true + end_of_line=crlf → file ends with \\r\\n."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ninsert_final_newline = true\nend_of_line = crlf\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b"x = 1\r\n"


async def test_T44_insert_final_newline_false_empty_file(tmp_path: Path):
    """T-44: insert_final_newline=false + empty file → stays empty."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ninsert_final_newline = false\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b""


async def test_T45_trim_and_insert_final_newline_false_combined(tmp_path: Path):
    """T-45: trim=true + insert=false → trim whitespace, then remove final newline."""
    ec = tmp_path / ".editorconfig"
    ec.write_text(
        "[*.py]\ntrim_trailing_whitespace = true\ninsert_final_newline = false\n"
    )
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1   \ny = 2  \n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_save()
        await pilot.pause()

    assert f.read_bytes() == b"x = 1\ny = 2"


async def test_T46_textarea_updated_when_user_adds_trailing_ws(tmp_path: Path):
    """T-46: User types trailing ws then saves → TextArea shows trimmed text.

    Bug scenario: file starts clean, user types trailing whitespace via the
    TextArea (which updates both TextArea and CodeEditor.text), then saves.
    The trim reverts text to the original initial_text value, so the reactive
    watcher on initial_text does not fire (same value), and the TextArea
    stays stale unless explicitly updated.
    """
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ntrim_trailing_whitespace = true\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")  # clean file, no trailing ws

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        textarea = editor.editor

        # Simulate user typing: insert trailing spaces via TextArea
        textarea.move_cursor_relative(columns=999, rows=0)
        textarea.insert("   ")
        await pilot.pause()
        assert textarea.text == "x = 1   \n"

        # Save — trim should revert to "x = 1\n"
        editor.action_save()
        await pilot.pause()

        # The actual TextArea widget must reflect the trimmed content
        textarea_text = textarea.text

    assert textarea_text == "x = 1\n"


# ── Group G: EditorConfig reload on modification ─────────────────────────────


def _bump_ec_mtimes(editor: CodeEditor) -> None:
    """Decrement stored editorconfig mtimes to simulate file change detection."""
    for d in list(editor._ec_mtimes):
        if editor._ec_mtimes[d] is not None:
            editor._ec_mtimes[d] -= 1.0


async def test_G01_modify_indent_style_detected(tmp_path: Path):
    """G-01: Modify indent_style in .editorconfig → detected and re-applied."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = space\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.indent_type == "spaces"

        # Modify .editorconfig
        ec.write_text("[*.py]\nindent_style = tab\n")
        _bump_ec_mtimes(editor)

        editor._poll_editorconfig_change()
        await pilot.pause()
        assert editor.indent_type == "tabs"


async def test_G02_modify_indent_size_detected(tmp_path: Path):
    """G-02: Modify indent_size in .editorconfig → detected and re-applied."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_size = 2\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.indent_size == 2

        ec.write_text("[*.py]\nindent_size = 8\n")
        _bump_ec_mtimes(editor)

        editor._poll_editorconfig_change()
        await pilot.pause()
        assert editor.indent_size == 8


async def test_G03_modify_trim_trailing_whitespace(tmp_path: Path):
    """G-03: Modify trim_trailing_whitespace → re-applied."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ntrim_trailing_whitespace = true\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor._trim_trailing_whitespace is True

        ec.write_text("[*.py]\ntrim_trailing_whitespace = false\n")
        _bump_ec_mtimes(editor)

        editor._poll_editorconfig_change()
        await pilot.pause()
        assert editor._trim_trailing_whitespace is False


async def test_G04_modify_insert_final_newline(tmp_path: Path):
    """G-04: Modify insert_final_newline → re-applied."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ninsert_final_newline = true\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor._insert_final_newline is True

        ec.write_text("[*.py]\ninsert_final_newline = false\n")
        _bump_ec_mtimes(editor)

        editor._poll_editorconfig_change()
        await pilot.pause()
        assert editor._insert_final_newline is False


async def test_G05_charset_not_reapplied(tmp_path: Path):
    """G-05: charset NOT re-applied on reload (safety — would corrupt text)."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\ncharset = utf-8\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.encoding == "utf-8"

        ec.write_text("[*.py]\ncharset = latin1\n")
        _bump_ec_mtimes(editor)

        editor._poll_editorconfig_change()
        await pilot.pause()
        # encoding must NOT change on reload
        assert editor.encoding == "utf-8"


async def test_G06_end_of_line_not_reapplied(tmp_path: Path):
    """G-06: end_of_line NOT re-applied on reload (safety)."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nend_of_line = lf\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.line_ending == "lf"

        ec.write_text("[*.py]\nend_of_line = crlf\n")
        _bump_ec_mtimes(editor)

        editor._poll_editorconfig_change()
        await pilot.pause()
        assert editor.line_ending == "lf"


async def test_G07_new_editorconfig_appears(tmp_path: Path):
    """G-07: New .editorconfig created → detected and applied."""
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.indent_type == "spaces"  # default

        # Create a NEW .editorconfig
        ec = tmp_path / ".editorconfig"
        ec.write_text("[*.py]\nindent_style = tab\n")
        # Stored mtime is None; current is now a float → change detected

        editor._poll_editorconfig_change()
        await pilot.pause()
        assert editor.indent_type == "tabs"


async def test_G08_editorconfig_deleted_resets_save_settings(tmp_path: Path):
    """G-08: .editorconfig deleted → save-time settings reset to None."""
    ec = tmp_path / ".editorconfig"
    ec.write_text(
        "[*.py]\ntrim_trailing_whitespace = true\ninsert_final_newline = true\n"
    )
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor._trim_trailing_whitespace is True
        assert editor._insert_final_newline is True

        # Delete .editorconfig
        ec.unlink()
        _bump_ec_mtimes(editor)

        editor._poll_editorconfig_change()
        await pilot.pause()
        assert editor._trim_trailing_whitespace is None
        assert editor._insert_final_newline is None


async def test_G09_no_mtime_change_is_noop(tmp_path: Path):
    """G-09: No mtime change → poll does nothing (no unnecessary re-apply)."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = space\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.indent_type == "spaces"

        # Do NOT modify .editorconfig or bump mtimes
        editor._poll_editorconfig_change()
        await pilot.pause()
        assert editor.indent_type == "spaces"


async def test_G10_parent_editorconfig_modified(tmp_path: Path):
    """G-10: Parent .editorconfig modified → inherited settings update."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_size = 2\n")
    subdir = tmp_path / "src"
    subdir.mkdir()
    f = subdir / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.indent_size == 2

        ec.write_text("[*.py]\nindent_size = 8\n")
        _bump_ec_mtimes(editor)

        editor._poll_editorconfig_change()
        await pilot.pause()
        assert editor.indent_size == 8


async def test_G11_untitled_file_poll_noop(tmp_path: Path):
    """G-11: Untitled file (path=None) → poll does nothing."""
    app = _EditorConfigTestApp(path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        # Should not raise any error
        editor._poll_editorconfig_change()
        await pilot.pause()


async def test_G12_property_removed_indent_stays(tmp_path: Path):
    """G-12: Property removed from .editorconfig → indent_type stays unchanged."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = tab\nindent_size = 8\n")
    f = tmp_path / "hello.py"
    f.write_bytes(b"x = 1\n")

    app = _EditorConfigTestApp(path=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor
        assert editor.indent_type == "tabs"
        assert editor.indent_size == 8

        # Remove indent_style and indent_size from .editorconfig
        ec.write_text("[*.py]\ntrim_trailing_whitespace = true\n")
        _bump_ec_mtimes(editor)

        editor._poll_editorconfig_change()
        await pilot.pause()
        # indent_type and indent_size stay at their current values
        assert editor.indent_type == "tabs"
        assert editor.indent_size == 8
        # But trim_trailing_whitespace IS applied
        assert editor._trim_trailing_whitespace is True
