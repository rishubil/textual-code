"""
FindReplaceBar widget tests.

Tests the inline find/replace bar behaviour:
- Visibility and mode toggling
- Find next via button and Enter key
- Sequential finds (bar stays open)
- Replace current and replace all
- Close button and Escape key
- Focus restoration after close
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.widgets.find_replace_bar import FindReplaceBar

# ── helpers ───────────────────────────────────────────────────────────────────


async def _open_file(workspace: Path, content: str, name: str = "test.txt") -> Path:
    f = workspace / name
    f.write_text(content)
    return f


# ── visibility ────────────────────────────────────────────────────────────────


async def test_ctrl_f_shows_bar_find_mode(workspace: Path):
    """Ctrl+F: bar visible, replace_mode=False."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        await pilot.press("ctrl+f")
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)
        assert bar.display
        assert not bar.replace_mode


async def test_ctrl_h_shows_bar_replace_mode(workspace: Path):
    """Ctrl+H: bar visible, replace_mode=True."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        await pilot.press("ctrl+h")
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)
        assert bar.display
        assert bar.replace_mode


async def test_escape_closes_bar(workspace: Path):
    """Escape while bar is focused closes the bar."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        # focus is on find_input
        await pilot.press("escape")
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)
        assert not bar.display


async def test_close_btn_hides_bar(workspace: Path):
    """Clicking ✕ hides the bar."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#close_btn")
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)
        assert not bar.display


async def test_close_returns_focus_to_textarea(workspace: Path):
    """Closing the bar returns focus to the MultiCursorTextArea."""
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#close_btn")
        await pilot.pause()
        assert app.focused == editor.query_one(MultiCursorTextArea)


# ── mode switching ────────────────────────────────────────────────────────────


async def test_replace_row_hidden_in_find_mode(workspace: Path):
    """In find mode, the replace row is not displayed."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        replace_row = editor.query_one("#replace_row")
        assert not replace_row.display


async def test_replace_row_visible_in_replace_mode(workspace: Path):
    """In replace mode, the replace row is displayed."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_replace()
        await pilot.pause()
        replace_row = editor.query_one("#replace_row")
        assert replace_row.display


async def test_ctrl_h_after_ctrl_f_switches_to_replace_mode(workspace: Path):
    """Opening replace bar after find bar switches mode."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        await pilot.press("ctrl+f")
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)
        assert not bar.replace_mode
        await pilot.press("ctrl+h")
        await pilot.pause()
        assert bar.replace_mode


# ── Find Next via bar ─────────────────────────────────────────────────────────


async def test_find_next_button_selects_match(workspace: Path):
    """Clicking Next selects the first match."""
    f = await _open_file(workspace, "hello world\nhello again\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#next_match")
        await pilot.pause()
        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_find_next_enter_key_selects_match(workspace: Path):
    """Pressing Enter in find_input triggers find next."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.press("enter")
        await pilot.pause()
        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_sequential_find_stays_open(workspace: Path):
    """Bar stays open across multiple Next clicks."""
    f = await _open_file(workspace, "aa bb aa cc aa\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_find()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("a", "a")

        await pilot.click("#next_match")
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)
        assert bar.display
        first_sel = editor.editor.selection.start

        await pilot.click("#next_match")
        await pilot.pause()
        assert bar.display
        second_sel = editor.editor.selection.start

        # successive finds moved the cursor forward
        assert second_sel > first_sel


async def test_find_next_empty_query_does_nothing(workspace: Path):
    """Empty query leaves cursor unchanged."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        original = editor.editor.cursor_location
        editor.action_find()
        await pilot.pause()
        await pilot.click("#next_match")
        await pilot.pause()
        assert editor.editor.cursor_location == original


# ── Replace via bar ───────────────────────────────────────────────────────────


async def test_replace_all_btn_replaces_all(workspace: Path):
    """Replace All button replaces every occurrence."""
    f = await _open_file(workspace, "foo bar foo baz\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_replace()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")
        await pilot.click("#replace_input")
        await pilot.press("X")
        await pilot.click("#replace_all_btn")
        await pilot.pause()
        assert "foo" not in editor.text
        assert editor.text.count("X") == 2


async def test_replace_btn_selection_matches_replaces_and_finds_next(workspace: Path):
    """Replace button: selection matches → replace and find next."""
    f = await _open_file(workspace, "hello hello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        from textual.widgets.text_area import Selection

        editor.editor.selection = Selection(start=(0, 0), end=(0, 5))
        await pilot.pause()

        editor.action_replace()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#replace_input")
        await pilot.press("h", "i")
        await pilot.click("#replace_btn")
        await pilot.pause()

        assert editor.text.startswith("hi")
        assert "hello" in editor.text  # second occurrence remains


async def test_replace_btn_no_selection_match_finds_next(workspace: Path):
    """Replace button: selection doesn't match → find next without replacing."""
    f = await _open_file(workspace, "hello world\nhello again\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_text = editor.text
        editor.editor.cursor_location = (0, 0)
        await pilot.pause()

        editor.action_replace()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#replace_input")
        await pilot.press("h", "i")
        await pilot.click("#replace_btn")
        await pilot.pause()

        # text unchanged but 'hello' selected
        assert editor.text == original_text
        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


# ── Case-sensitive toggle ─────────────────────────────────────────────────────


async def test_case_insensitive_find_via_bar(workspace: Path):
    """Unchecking Aa checkbox causes case-insensitive find."""
    from textual.widgets import Checkbox

    f = await _open_file(workspace, "HELLO world\n")
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
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#next_match")
        await pilot.pause()

        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_regex_on_disables_case_sensitive_checkbox(workspace: Path):
    """Enabling regex disables the case_sensitive checkbox."""
    from textual.widgets import Checkbox

    f = await _open_file(workspace, "hello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)

        await pilot.click("#use_regex")
        await pilot.pause()

        case_cb = bar.query_one("#case_sensitive", Checkbox)
        assert case_cb.disabled


async def test_regex_on_get_case_sensitive_always_true(workspace: Path):
    """When regex is on, _get_case_sensitive() always returns True."""
    from textual.widgets import Checkbox

    f = await _open_file(workspace, "hello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)

        # Uncheck case_sensitive, then turn regex on
        bar.query_one("#case_sensitive", Checkbox).value = False
        await pilot.pause()
        await pilot.click("#use_regex")
        await pilot.pause()

        assert bar._get_case_sensitive() is True
