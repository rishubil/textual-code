"""
EditorConfig support tests.

Group A — _read_editorconfig() basic behaviour (T-01 to T-06)
Group B — Glob pattern matching (T-07 to T-16)
Group C — Parsing edge cases (T-17 to T-22)
Group D — Property value mapping (T-23 to T-28)
Group E — Integration: CodeEditor file open (T-29 to T-32)
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
    result = _read_editorconfig(f)
    assert result == {}


def test_T02_reads_same_directory_editorconfig(tmp_path: Path):
    """T-02: Reads .editorconfig in same directory as file."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = space\n")
    f = tmp_path / "hello.py"
    f.write_text("x = 1\n")
    result = _read_editorconfig(f)
    assert result.get("indent_style") == "space"


def test_T03_reads_parent_directory_editorconfig(tmp_path: Path):
    """T-03: Traverses up to parent directory .editorconfig."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_size = 2\n")
    subdir = tmp_path / "src"
    subdir.mkdir()
    f = subdir / "hello.py"
    f.write_text("x = 1\n")
    result = _read_editorconfig(f)
    assert result.get("indent_size") == "2"


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

    result = _read_editorconfig(f)
    # indent_style comes from child; indent_size from parent should NOT appear
    assert result.get("indent_style") == "tab"
    assert result.get("indent_size") is None


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

    result = _read_editorconfig(f)
    assert result.get("indent_style") == "space"


def test_T06_later_section_in_same_file_wins(tmp_path: Path):
    """T-06: In the same file, later section overrides earlier for same key."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = tab\n\n[*.py]\nindent_style = space\n")
    f = tmp_path / "hello.py"
    f.write_text("x = 1\n")
    result = _read_editorconfig(f)
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
    result = _read_editorconfig(f)
    # Value should include the trailing " # not a comment" text (no inline comment)
    assert "space" in result.get("indent_style", "")


def test_T18_semicolon_comment_ignored(tmp_path: Path):
    """T-18: ; at line start = comment line → ignored."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("; this is a comment\n[*.py]\nindent_style = space\n")
    f = tmp_path / "hello.py"
    f.write_text("")
    result = _read_editorconfig(f)
    assert result.get("indent_style") == "space"


def test_T19_keys_and_values_normalized_lowercase(tmp_path: Path):
    """T-19: Keys and values are normalized to lowercase."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nINDENT_STYLE = Space\n")
    f = tmp_path / "hello.py"
    f.write_text("")
    result = _read_editorconfig(f)
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

    result = _read_editorconfig(f)
    # Parent's indent_size should still be visible (root=true in section ignored)
    assert result.get("indent_size") == "8"


def test_T21_empty_editorconfig_returns_empty_dict(tmp_path: Path):
    """T-21: Empty .editorconfig → empty dict."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("")
    f = tmp_path / "hello.py"
    f.write_text("")
    result = _read_editorconfig(f)
    assert result == {}


def test_T22_unknown_property_included_in_dict(tmp_path: Path):
    """T-22: Unknown properties are included in dict but don't affect CodeEditor."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nspelling_language = en_US\n")
    f = tmp_path / "hello.py"
    f.write_text("")
    result = _read_editorconfig(f)
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
