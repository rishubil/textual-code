"""
Word deletion tests for Ctrl+Backspace and Ctrl+Delete.

Tests cover single-cursor and multi-cursor scenarios, ported from
VSCode's wordOperations.test.ts (lines 540-870) and adapted for our
editor's word boundary logic (_WORD_PATTERN).

Word boundary pattern::

    _WORD_PATTERN = re.compile(r"(?<=\\W)(?=\\w)|(?<=\\w)(?=\\W)")

Matches every transition between \\w and \\W characters.
"""

from pathlib import Path
from typing import Any

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app
from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _setup_editor(
    workspace: Path, text: str
) -> tuple[Any, Any, MultiCursorTextArea, Any]:
    """Create a light app with text loaded. Returns (app, pilot, editor, ctx)."""
    f = workspace / "test_wd.txt"
    f.write_text(text)
    app = make_app(workspace, light=True, open_file=f)
    ctx = app.run_test()
    pilot = await ctx.__aenter__()
    await pilot.wait_for_scheduled_animations()
    ce = app.main_view.get_active_code_editor()
    assert ce is not None
    ta = ce.editor
    return app, pilot, ta, ctx


# ── Single-cursor: delete word left (Ctrl+Backspace) ────────────────────────


@pytest.mark.parametrize(
    "text, cursor, expected_text, expected_cursor",
    [
        # Mid-word: deletes from cursor to previous word boundary
        ("hello world", (0, 11), "hello ", (0, 6)),
        # At word boundary: deletes the space + previous word
        ("hello world", (0, 6), "world", (0, 0)),
        # Inside first word: deletes to start of line
        ("hello world", (0, 3), "lo world", (0, 0)),
        # At start of document: no-op
        ("hello world", (0, 0), "hello world", (0, 0)),
        # With leading spaces (from Textual test pattern)
        ("  012 345 6789", (0, 2), "012 345 6789", (0, 0)),
        ("  012 345 6789", (0, 5), "   345 6789", (0, 2)),
        ("  012 345 6789", (0, 14), "  012 345 ", (0, 10)),
    ],
    ids=[
        "mid_word",
        "at_word_boundary",
        "inside_first_word",
        "at_doc_start",
        "leading_spaces",
        "after_first_word",
        "at_end",
    ],
)
async def test_delete_word_left_single_cursor(
    workspace: Path,
    text: str,
    cursor: tuple,
    expected_text: str,
    expected_cursor: tuple,
):
    app, pilot, ta, ctx = await _setup_editor(workspace, text)
    try:
        ta.selection = Selection.cursor(cursor)
        ta.action_delete_word_left()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == expected_text
        assert ta.cursor_location == expected_cursor
    finally:
        await ctx.__aexit__(None, None, None)


async def test_delete_word_left_at_line_start_merges(workspace: Path):
    """Ctrl+Backspace at line start merges with previous line."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "hello\nworld")
    try:
        ta.selection = Selection.cursor((1, 0))
        ta.action_delete_word_left()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == "helloworld"
        assert ta.cursor_location == (0, 5)
    finally:
        await ctx.__aexit__(None, None, None)


async def test_delete_word_left_with_selection_deletes_selection(workspace: Path):
    """When selection is active, delete word left just deletes the selection."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "hello world")
    try:
        ta.selection = Selection((0, 2), (0, 8))
        ta.action_delete_word_left()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == "herld"
        assert ta.cursor_location == (0, 2)
    finally:
        await ctx.__aexit__(None, None, None)


# ── Single-cursor: delete word right (Ctrl+Delete) ──────────────────────────


@pytest.mark.parametrize(
    "text, cursor, expected_text, expected_cursor",
    [
        # At start: deletes first word
        ("hello world", (0, 0), " world", (0, 0)),
        # Mid-word: deletes to next word boundary
        ("hello world", (0, 3), "hel world", (0, 3)),
        # At word boundary (space): deletes the space
        ("hello world", (0, 5), "helloworld", (0, 5)),
        # At end of document: no-op
        ("hello world", (0, 11), "hello world", (0, 11)),
        # With leading spaces (from Textual test pattern)
        ("  012 345 6789", (0, 0), "012 345 6789", (0, 0)),
        ("  012 345 6789", (0, 5), "  012345 6789", (0, 5)),
        ("  012 345 6789", (0, 14), "  012 345 6789", (0, 14)),
    ],
    ids=[
        "at_start",
        "mid_word",
        "at_space",
        "at_doc_end",
        "leading_spaces",
        "after_first_word",
        "at_end",
    ],
)
async def test_delete_word_right_single_cursor(
    workspace: Path,
    text: str,
    cursor: tuple,
    expected_text: str,
    expected_cursor: tuple,
):
    app, pilot, ta, ctx = await _setup_editor(workspace, text)
    try:
        ta.selection = Selection.cursor(cursor)
        ta.action_delete_word_right()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == expected_text
        assert ta.cursor_location == expected_cursor
    finally:
        await ctx.__aexit__(None, None, None)


async def test_delete_word_right_at_line_end_merges(workspace: Path):
    """Ctrl+Delete at line end merges with next line."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "hello\nworld")
    try:
        ta.selection = Selection.cursor((0, 5))
        ta.action_delete_word_right()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == "helloworld"
        assert ta.cursor_location == (0, 5)
    finally:
        await ctx.__aexit__(None, None, None)


async def test_delete_word_right_with_selection_deletes_selection(workspace: Path):
    """When selection is active, delete word right just deletes the selection."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "hello world")
    try:
        ta.selection = Selection((0, 2), (0, 8))
        ta.action_delete_word_right()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == "herld"
        assert ta.cursor_location == (0, 2)
    finally:
        await ctx.__aexit__(None, None, None)


# ── Multi-cursor: delete word left ──────────────────────────────────────────


async def test_delete_word_left_multi_cursor_same_line(workspace: Path):
    """Delete word left with two cursors on the same line."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "aaa bbb ccc")
    try:
        # Place cursors after "aaa" (col 3) and after "bbb" (col 7)
        ta.selection = Selection.cursor((0, 7))
        ta._extra_cursors = [(0, 3)]
        ta._extra_anchors = [(0, 3)]
        ta.action_delete_word_left()
        await pilot.wait_for_scheduled_animations()
        # "aaa" deleted (0→3), "bbb" deleted (4→7), two spaces remain
        assert ta.text == "  ccc"
    finally:
        await ctx.__aexit__(None, None, None)


async def test_delete_word_left_multi_cursor_different_lines(workspace: Path):
    """Delete word left with cursors on different lines."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "hello world\nfoo bar")
    try:
        # Primary at end of "world" (0, 11), extra at end of "bar" (1, 7)
        ta.selection = Selection.cursor((0, 11))
        ta._extra_cursors = [(1, 7)]
        ta._extra_anchors = [(1, 7)]
        ta.action_delete_word_left()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == "hello \nfoo "
    finally:
        await ctx.__aexit__(None, None, None)


# ── Multi-cursor: delete word right ─────────────────────────────────────────


async def test_delete_word_right_multi_cursor_same_line(workspace: Path):
    """Delete word right with two cursors on the same line."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "aaa bbb ccc")
    try:
        # Place cursors at start of "aaa" (col 0) and start of "bbb" (col 4)
        ta.selection = Selection.cursor((0, 0))
        ta._extra_cursors = [(0, 4)]
        ta._extra_anchors = [(0, 4)]
        ta.action_delete_word_right()
        await pilot.wait_for_scheduled_animations()
        # "aaa" deleted (0→3), "bbb" deleted (4→7) → " ccc"
        assert ta.text == "  ccc"
    finally:
        await ctx.__aexit__(None, None, None)


async def test_delete_word_right_multi_cursor_different_lines(workspace: Path):
    """Delete word right with cursors on different lines."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "hello world\nfoo bar")
    try:
        # Primary at start (0, 0), extra at start of "foo" (1, 0)
        ta.selection = Selection.cursor((0, 0))
        ta._extra_cursors = [(1, 0)]
        ta._extra_anchors = [(1, 0)]
        ta.action_delete_word_right()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == " world\n bar"
    finally:
        await ctx.__aexit__(None, None, None)


# ── Edge cases ───────────────────────────────────────────────────────────────


async def test_delete_word_left_empty_document(workspace: Path):
    """Delete word left in empty document is a no-op."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "")
    try:
        ta.selection = Selection.cursor((0, 0))
        ta.action_delete_word_left()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == ""
    finally:
        await ctx.__aexit__(None, None, None)


async def test_delete_word_right_empty_document(workspace: Path):
    """Delete word right in empty document is a no-op."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "")
    try:
        ta.selection = Selection.cursor((0, 0))
        ta.action_delete_word_right()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == ""
    finally:
        await ctx.__aexit__(None, None, None)


async def test_delete_word_left_whitespace_only(workspace: Path):
    """Delete word left on whitespace-only line deletes to line start."""
    app, pilot, ta, ctx = await _setup_editor(workspace, "   ")
    try:
        ta.selection = Selection.cursor((0, 3))
        ta.action_delete_word_left()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == ""
        assert ta.cursor_location == (0, 0)
    finally:
        await ctx.__aexit__(None, None, None)
