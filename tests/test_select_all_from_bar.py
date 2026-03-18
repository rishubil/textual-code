"""
Tests for the 'Select All' button in FindReplaceBar.

Verifies that clicking Select All in the find bar creates multi-cursors
for all matches, respecting regex and case-sensitivity settings.
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.widgets.find_replace_bar import FindReplaceBar

# ── helpers ───────────────────────────────────────────────────────────────────


async def _open_file(workspace: Path, content: str, name: str = "test.txt") -> Path:
    f = workspace / name
    f.write_text(content)
    return f


# ── button existence ─────────────────────────────────────────────────────────


async def test_select_all_btn_exists_in_find_bar(workspace: Path):
    """Find bar contains a Select All button."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)
        btn = bar.query_one("#select_all_btn")
        assert btn is not None


# ── basic select all ─────────────────────────────────────────────────────────


async def test_select_all_creates_multi_cursors(workspace: Path):
    """Select All with 2 matches creates primary selection + 1 extra cursor."""
    f = await _open_file(workspace, "foo bar\nfoo baz\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")
        await pilot.click("#select_all_btn")
        await pilot.pause()

        # Primary selection at first match
        assert editor.editor.selection.start == (0, 0)
        assert editor.editor.selection.end == (0, 3)
        # Extra cursor at second match
        assert (1, 3) in editor.editor.extra_cursors
        assert editor.editor.extra_anchors == [(1, 0)]


async def test_select_all_bar_stays_open(workspace: Path):
    """After Select All, the find bar stays open."""
    f = await _open_file(workspace, "foo bar\nfoo baz\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")
        await pilot.click("#select_all_btn")
        await pilot.pause()

        bar = editor.query_one(FindReplaceBar)
        assert bar.display


async def test_select_all_focuses_editor(workspace: Path):
    """After Select All, focus moves to the editor for multi-cursor typing."""
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

    f = await _open_file(workspace, "foo bar\nfoo baz\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")
        await pilot.click("#select_all_btn")
        await pilot.pause()

        assert app.focused == editor.query_one(MultiCursorTextArea)


# ── single match ─────────────────────────────────────────────────────────────


async def test_select_all_single_match(workspace: Path):
    """Single match: primary selection set, no extra cursors."""
    f = await _open_file(workspace, "foo bar baz\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")
        await pilot.click("#select_all_btn")
        await pilot.pause()

        assert editor.editor.selection.start == (0, 0)
        assert editor.editor.selection.end == (0, 3)
        assert editor.editor.extra_cursors == []


# ── regex mode ───────────────────────────────────────────────────────────────


async def test_select_all_regex_mode(workspace: Path):
    """With regex enabled, pattern matching is used."""
    from textual.widgets import Checkbox

    f = await _open_file(workspace, "hello\nhallo\nhullo\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)

        # Enable regex
        bar.query_one("#use_regex", Checkbox).value = True
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("h", ".", "l", "l", "o")
        await pilot.click("#select_all_btn")
        await pilot.pause()

        # All 3 matches: primary + 2 extra cursors
        assert len(editor.editor.extra_cursors) == 2


# ── case insensitive ─────────────────────────────────────────────────────────


async def test_select_all_case_insensitive(workspace: Path):
    """With Aa unchecked, case-insensitive matching is used."""
    from textual.widgets import Checkbox

    f = await _open_file(workspace, "foo Foo FOO\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)

        # Uncheck case_sensitive
        bar.query_one("#case_sensitive", Checkbox).value = False
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")
        await pilot.click("#select_all_btn")
        await pilot.pause()

        # All 3 matches: primary + 2 extra cursors
        assert len(editor.editor.extra_cursors) == 2


# ── no matches ───────────────────────────────────────────────────────────────


async def test_select_all_no_matches(workspace: Path):
    """No matches: no cursor changes, no crash."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("z", "z", "z")
        await pilot.click("#select_all_btn")
        await pilot.pause()

        assert editor.editor.extra_cursors == []


# ── empty query ──────────────────────────────────────────────────────────────


async def test_select_all_empty_query_is_noop(workspace: Path):
    """Empty query: no-op, no crash."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()

        original_sel = editor.editor.selection

        await pilot.click("#select_all_btn")
        await pilot.pause()

        assert editor.editor.selection == original_sel
        assert editor.editor.extra_cursors == []


# ── invalid regex ────────────────────────────────────────────────────────────


async def test_select_all_invalid_regex(workspace: Path):
    """Invalid regex: error notification, no crash."""
    from textual.widgets import Checkbox

    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)

        # Enable regex
        bar.query_one("#use_regex", Checkbox).value = True
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("[", "i", "n", "v", "a", "l", "i", "d")
        await pilot.click("#select_all_btn")
        await pilot.pause()

        # No crash, no cursors changed
        assert editor.editor.extra_cursors == []


# ── interaction with Find Next ───────────────────────────────────────────────


async def test_select_all_resets_find_offset(workspace: Path):
    """Select All after Find Next resets _find_offset."""
    f = await _open_file(workspace, "foo bar\nfoo baz\nfoo qux\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")

        # Find Next to advance _find_offset
        await pilot.click("#next_match")
        await pilot.pause()
        assert editor._find_offset is not None

        # Select All should reset _find_offset
        await pilot.click("#select_all_btn")
        await pilot.pause()
        assert editor._find_offset is None

        # All 3 matches should be selected
        assert len(editor.editor.extra_cursors) == 2
