"""
Replace (Ctrl+H) feature tests.

Behaviour spec:
- Ctrl+H opens FindReplaceBar in replace mode
- Replace All: replaces every occurrence, shows count notification
- Replace All: no match → warning notification, text unchanged
- Replace All: empty find_query → does nothing
- Replace (single): current selection matches find_query → replace and find next
- Replace (single): current selection doesn't match → find next without replacing
- Replace: no file open → bar not shown
- Case-sensitive matching
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.find_replace_bar import FindReplaceBar

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def replace_file(workspace: Path) -> Path:
    """A file with repeated words useful for replace testing."""
    f = workspace / "replace.txt"
    f.write_text("hello world\nhello textual\nfoo bar\n")
    return f


# ── Ctrl+H opens bar ──────────────────────────────────────────────────────────


async def test_ctrl_h_opens_replace_bar(workspace: Path, replace_file: Path):
    app = make_app(workspace, open_file=replace_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        await pilot.press("ctrl+h")
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)
        assert bar.display
        assert bar.replace_mode


async def test_ctrl_h_with_no_open_file_does_nothing(workspace: Path):
    """Ctrl+H when no file is open does nothing."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+h")
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is None


# ── Replace All ───────────────────────────────────────────────────────────────


async def test_replace_all_replaces_all_occurrences(
    workspace: Path, replace_file: Path
):
    """Replace All changes every occurrence of the find_query."""
    app = make_app(workspace, open_file=replace_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#replace_input")
        await pilot.press("h", "i")
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        assert "hi world" in editor.text
        assert "hi textual" in editor.text
        assert "hello" not in editor.text


async def test_replace_all_no_match_shows_warning(workspace: Path, replace_file: Path):
    """Replace All with no match shows a warning and leaves text unchanged."""
    app = make_app(workspace, open_file=replace_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_text = editor.text

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("z", "z", "z", "n", "o", "t", "f", "o", "u", "n", "d")
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        assert editor.text == original_text


async def test_replace_all_empty_find_query_does_nothing(
    workspace: Path, replace_file: Path
):
    """Replace All with empty find_query does nothing."""
    app = make_app(workspace, open_file=replace_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_text = editor.text

        editor.action_replace()
        await pilot.pause()
        # Leave find_input empty, click Replace All
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        assert editor.text == original_text


async def test_replace_all_count_notification(workspace: Path):
    """Replace All notifies the user with the replacement count."""
    f = workspace / "count.txt"
    f.write_text("aaa bbb aaa ccc aaa\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("a", "a", "a")
        await pilot.click("#replace_input")
        await pilot.press("X")
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        assert editor.text.count("aaa") == 0
        assert editor.text.count("X") == 3


# ── Replace (single) ──────────────────────────────────────────────────────────


async def test_replace_single_selection_matches_replaces_and_finds_next(
    workspace: Path, replace_file: Path
):
    """When selection matches find_query, it is replaced and next match is selected."""
    # replace_file: "hello world\nhello textual\nfoo bar\n"
    # two 'hello': (0,0)–(0,5) and (1,0)–(1,5)
    app = make_app(workspace, open_file=replace_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        from textual.widgets.text_area import Selection

        # Select the first 'hello'
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

        # First hello replaced with "hi"
        assert editor.text.startswith("hi world")
        # Next match (the remaining 'hello') should be selected
        sel = editor.editor.selection
        new_text = editor.text
        hello_idx = new_text.find("hello")
        assert hello_idx != -1
        from textual_code.widgets.code_editor import _text_offset_to_location

        expected_start = _text_offset_to_location(new_text, hello_idx)
        assert sel.start == expected_start


async def test_replace_single_selection_no_match_finds_next(
    workspace: Path, replace_file: Path
):
    """Selection doesn't match find_query — next occurrence is found, no replacement."""
    # replace_file: "hello world\nhello textual\nfoo bar\n"
    app = make_app(workspace, open_file=replace_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_text = editor.text
        # Cursor at start, nothing selected → selection won't match "hello"
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

        # Text should be unchanged (no replacement done)
        assert editor.text == original_text
        # But cursor should be on 'hello'
        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


# ── Cancel ────────────────────────────────────────────────────────────────────


async def test_replace_cancel_leaves_text_unchanged(
    workspace: Path, replace_file: Path
):
    """Closing the replace bar leaves text and cursor unchanged."""
    app = make_app(workspace, open_file=replace_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_text = editor.text
        original_location = editor.editor.cursor_location

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#close_btn")
        await pilot.pause()

        assert editor.text == original_text
        assert editor.editor.cursor_location == original_location


# ── action_replace_cmd ────────────────────────────────────────────────────────


async def test_replace_cmd_with_no_open_file_does_not_open_bar(workspace: Path):
    """action_replace_cmd when no file is open does nothing."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_replace_cmd()
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is None


# ── Case sensitivity ──────────────────────────────────────────────────────────


async def test_replace_all_is_case_sensitive(workspace: Path):
    """Replace All is case-sensitive: 'Hello' doesn't match 'hello'."""
    f = workspace / "case.txt"
    f.write_text("Hello hello HELLO\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("h", "e", "l", "l", "o")  # lowercase
        await pilot.click("#replace_input")
        await pilot.press("X")
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        # Only lowercase 'hello' replaced
        assert "Hello" in editor.text
        assert "HELLO" in editor.text
        assert "X" in editor.text


# ── Replace All preserves unsaved-state ───────────────────────────────────────


async def test_replace_all_marks_file_as_unsaved(workspace: Path):
    """After Replace All, the editor is marked as having unsaved changes."""
    f = workspace / "unsaved.txt"
    f.write_text("foo foo foo\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")
        await pilot.click("#replace_input")
        await pilot.press("b", "a", "r")
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        assert editor.text != editor.initial_text


# ── Replace All: empty replacement (deletion) ─────────────────────────────────


async def test_replace_all_empty_replacement_deletes_occurrences(workspace: Path):
    """Replace All with empty replace_text removes all occurrences."""
    f = workspace / "del.txt"
    f.write_text("foo bar foo baz foo\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")
        # leave replace_input empty
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        assert "foo" not in editor.text
        assert "bar" in editor.text
        assert "baz" in editor.text


# ── Replace All: single occurrence ────────────────────────────────────────────


async def test_replace_all_single_occurrence(workspace: Path):
    """Replace All on a file with exactly one match replaces it."""
    f = workspace / "one.txt"
    f.write_text("only one match here\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("m", "a", "t", "c", "h")
        await pilot.click("#replace_input")
        await pilot.press("f", "o", "u", "n", "d")
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        assert "found" in editor.text
        assert "match" not in editor.text


# ── Replace All: replacement contains the search string ───────────────────────


async def test_replace_all_replacement_contains_search_string(workspace: Path):
    """Replace All where replacement contains the search string.

    Python str.replace handles this non-recursively.
    """
    f = workspace / "contain.txt"
    f.write_text("aa aa\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("a", "a")
        await pilot.click("#replace_input")
        await pilot.press("a", "a", "a")
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        # "aa aa" → "aaa aaa"
        assert editor.text == "aaa aaa\n"


# ── Replace All: multiline ────────────────────────────────────────────────────


async def test_replace_all_multiline_file(workspace: Path):
    """Replace All works across multiple lines."""
    f = workspace / "multi.txt"
    f.write_text("line one\nline two\nline three\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("l", "i", "n", "e")
        await pilot.click("#replace_input")
        await pilot.press("r", "o", "w")
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        assert editor.text == "row one\nrow two\nrow three\n"


# ── Replace single: last occurrence (no next match) ───────────────────────────


async def test_replace_single_last_occurrence_no_next_selected(workspace: Path):
    """Replacing the last occurrence does not crash; no new selection is forced."""
    f = workspace / "last.txt"
    f.write_text("foo bar\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        from textual.widgets.text_area import Selection

        # Select the only 'foo'
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")
        await pilot.click("#replace_input")
        await pilot.press("b", "a", "z")
        await pilot.click("#replace_btn")
        await pilot.pause()

        # Replacement happened, no 'foo' left
        assert editor.text == "baz bar\n"
        assert "foo" not in editor.text


# ── Replace single: only one match total ──────────────────────────────────────


async def test_replace_single_only_one_match_no_next(workspace: Path):
    """After replacing the only occurrence there is no next match to jump to."""
    f = workspace / "only.txt"
    f.write_text("unique word here\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        from textual.widgets.text_area import Selection

        editor.editor.selection = Selection(start=(0, 0), end=(0, 6))  # "unique"
        await pilot.pause()

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        for ch in "unique":
            await pilot.press(ch)
        await pilot.click("#replace_input")
        for ch in "common":
            await pilot.press(ch)
        await pilot.click("#replace_btn")
        await pilot.pause()

        assert "common" in editor.text
        assert "unique" not in editor.text


# ── Replace single: sequential calls advance through occurrences ──────────────


async def test_replace_single_sequential_advances(workspace: Path):
    """Two sequential Replace calls progressively replace occurrences."""
    # file: "aa bb aa cc aa"
    f = workspace / "seq.txt"
    f.write_text("aa bb aa cc aa\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        from textual.widgets.text_area import Selection

        # ── call 1: select first "aa" → replaces, advances to second "aa" ──
        editor.editor.selection = Selection(start=(0, 0), end=(0, 2))
        await pilot.pause()

        editor.action_replace()
        await pilot.pause()
        await pilot.click("#find_input")
        await pilot.press("a", "a")
        await pilot.click("#replace_input")
        await pilot.press("X", "X")
        await pilot.click("#replace_btn")
        await pilot.pause()

        # First "aa" replaced with "XX"; second "aa" selected
        assert editor.text.startswith("XX bb")
        sel = editor.editor.selection
        new_text = editor.text
        second_aa_idx = new_text.find("aa")
        assert second_aa_idx != -1
        from textual_code.widgets.code_editor import _text_offset_to_location

        assert sel.start == _text_offset_to_location(new_text, second_aa_idx)

        # ── call 2: second "aa" is selected → replaces, advances to third ──
        # Bar is still open; move cursor to end of find input and retype query
        await pilot.click("#find_input")
        await pilot.press("end")
        await pilot.press("backspace", "backspace")
        await pilot.press("a", "a")
        await pilot.click("#replace_btn")
        await pilot.pause()

        # Two "aa" replaced; one "aa" remaining
        assert editor.text.count("aa") == 1
        assert editor.text.count("XX") == 2


# ── Replace single: wrap-around when cursor is past last occurrence ───────────


async def test_replace_single_wraps_around_find(workspace: Path):
    """Cursor after all occurrences and no selection match — search wraps to start."""
    f = workspace / "wrap.txt"
    f.write_text("foo bar\nbaz qux\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Place cursor at end of file (after all 'foo' occurrences)
        editor.editor.cursor_location = (1, 7)
        await pilot.pause()

        original_text = editor.text

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("f", "o", "o")
        await pilot.click("#replace_input")
        await pilot.press("z", "a", "p")
        await pilot.click("#replace_btn")
        await pilot.pause()

        # No replacement (selection didn't match); but 'foo' at (0,0) selected via wrap
        assert editor.text == original_text
        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 3)


# ── Replace single: untitled (new) file ───────────────────────────────────────


async def test_replace_single_on_untitled_file(workspace: Path):
    """Replace works on a new, unsaved file."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.editor.focus()
        await pilot.pause()
        for ch in "hello hello":
            await pilot.press(ch)
        await pilot.pause()

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
        assert "hello" in editor.text  # second occurrence still exists


# ── action_replace_cmd: positive path ────────────────────────────────────────


async def test_replace_cmd_opens_bar_when_file_open(
    workspace: Path, replace_file: Path
):
    """action_replace_cmd opens FindReplaceBar in replace mode when a file is open."""
    app = make_app(workspace, open_file=replace_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        app.action_replace_cmd()
        await pilot.pause()
        bar = editor.query_one(FindReplaceBar)
        assert bar.display
        assert bar.replace_mode


# ── Replace single: no match anywhere (not found) ────────────────────────────


async def test_replace_single_no_match_anywhere_shows_warning(
    workspace: Path, replace_file: Path
):
    """Replace single when find_query doesn't exist at all shows a warning."""
    app = make_app(workspace, open_file=replace_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_text = editor.text

        editor.action_replace()
        await pilot.pause()

        await pilot.click("#find_input")
        await pilot.press("z", "z", "z", "n", "o", "t", "h", "e", "r", "e")
        await pilot.click("#replace_input")
        await pilot.press("X")
        await pilot.click("#replace_btn")
        await pilot.pause()

        assert editor.text == original_text
