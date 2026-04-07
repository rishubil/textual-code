"""Tests for CheckboxTree widget and TriStateCheckbox."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.content import Content

from textual_code.search import WorkspaceSearchResult
from textual_code.widgets.checkbox_tree import (
    CheckboxTree,
    TriStateCheckbox,
    _InlineCheckbox,
    _InlineTriState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_results(
    workspace: Path,
    files: dict[str, list[tuple[int, str, int, int]]],
) -> list[WorkspaceSearchResult]:
    """Build WorkspaceSearchResult list from a compact spec.

    *files* maps relative path to list of (line_number, line_text, start, end).
    """
    results: list[WorkspaceSearchResult] = []
    for rel, matches in files.items():
        fp = workspace / rel
        for ln, text, start, end in matches:
            results.append(
                WorkspaceSearchResult(
                    file_path=fp,
                    line_number=ln,
                    line_text=text,
                    match_start=start,
                    match_end=end,
                )
            )
    return results


class _TreeApp(App):
    """Minimal app hosting a CheckboxTree for testing."""

    def __init__(self, results: list[WorkspaceSearchResult], workspace: Path) -> None:
        super().__init__()
        self._results = results
        self._workspace = workspace

    def compose(self) -> ComposeResult:
        yield CheckboxTree(id="tree")

    def on_mount(self) -> None:
        tree = self.query_one("#tree", CheckboxTree)
        tree.populate(self._results, self._workspace)


# ---------------------------------------------------------------------------
# TriStateCheckbox unit tests
# ---------------------------------------------------------------------------


class _TriStateApp(App):
    def compose(self) -> ComposeResult:
        yield TriStateCheckbox(id="tri")


@pytest.mark.asyncio
async def test_tristate_initial_false() -> None:
    async with _TriStateApp().run_test() as pilot:
        tri = pilot.app.query_one("#tri", TriStateCheckbox)
        assert tri.value is False


@pytest.mark.asyncio
async def test_tristate_toggle_cycle() -> None:
    async with _TriStateApp().run_test() as pilot:
        tri = pilot.app.query_one("#tri", TriStateCheckbox)
        # False → True
        tri.toggle()
        assert tri.value is True
        # True → False
        tri.toggle()
        assert tri.value is False


@pytest.mark.asyncio
async def test_tristate_partial_to_true() -> None:
    async with _TriStateApp().run_test() as pilot:
        tri = pilot.app.query_one("#tri", TriStateCheckbox)
        with tri.prevent(TriStateCheckbox.Changed):
            tri.value = None
        assert tri.value is None
        tri.toggle()
        assert tri.value is True


@pytest.mark.asyncio
async def test_tristate_changed_message() -> None:
    messages: list[bool | None] = []

    class _App(App):
        def compose(self) -> ComposeResult:
            yield TriStateCheckbox(id="tri")

        def on_tri_state_checkbox_changed(
            self, event: TriStateCheckbox.Changed
        ) -> None:
            messages.append(event.value)

    async with _App().run_test() as pilot:
        tri = pilot.app.query_one("#tri", TriStateCheckbox)
        tri.toggle()  # False → True
        await pilot.pause()
        assert True in messages


# ---------------------------------------------------------------------------
# CheckboxTree population tests
# ---------------------------------------------------------------------------

_WS = Path("/tmp/ws")
_SAMPLE_RESULTS = _make_results(
    _WS,
    {
        "src/a.py": [
            (10, "hello world", 0, 5),
            (20, "hello again", 0, 5),
        ],
        "src/b.py": [
            (5, "hello there", 0, 5),
        ],
    },
)


@pytest.mark.asyncio
async def test_populate_creates_file_and_match_rows() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        file_rows = tree.file_rows()
        assert len(file_rows) == 2
        assert len(tree.match_rows_for(file_rows[0])) == 2
        assert len(tree.match_rows_for(file_rows[1])) == 1


@pytest.mark.asyncio
async def test_populate_file_label_shows_path_and_count() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        file_rows = tree.file_rows()
        assert "src/a.py" in file_rows[0].label_text
        assert "2 matches" in file_rows[0].label_text
        assert "src/b.py" in file_rows[1].label_text
        assert "1 match" in file_rows[1].label_text


@pytest.mark.asyncio
async def test_populate_match_label_shows_line() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        match_rows = tree.match_rows_for(tree.file_rows()[0])
        assert "10:" in match_rows[0].label_text
        assert "hello world" in match_rows[0].label_text


@pytest.mark.asyncio
async def test_clear_removes_all_rows() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        tree.clear()
        await pilot.pause()
        assert tree.file_rows() == []
        assert tree.selected_results == []


@pytest.mark.asyncio
async def test_populate_after_clear_rebuilds() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        tree.clear()
        await pilot.pause()
        tree.populate(_SAMPLE_RESULTS, _WS)
        await pilot.pause()
        assert len(tree.file_rows()) == 2


# ---------------------------------------------------------------------------
# Selection logic tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_all_selected() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        assert tree.all_selected is True
        assert len(tree.selected_results) == 3


@pytest.mark.asyncio
async def test_toggle_match_makes_file_partial() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        # Uncheck the first match in the first file
        first_file = tree.file_rows()[0]
        first_match = tree.match_rows_for(first_file)[0]
        cb = first_match.query_one(_InlineCheckbox)
        cb.toggle()
        await pilot.pause()

        # File should now be partial
        tri = first_file.query_one(_InlineTriState)
        assert tri.value is None
        assert tree.all_selected is False
        assert len(tree.selected_results) == 2


@pytest.mark.asyncio
async def test_toggle_file_selects_all_children() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        # First make it partial by unchecking one match
        first_file = tree.file_rows()[0]
        first_match = tree.match_rows_for(first_file)[0]
        cb = first_match.query_one(_InlineCheckbox)
        cb.toggle()
        await pilot.pause()

        # Now toggle file checkbox (partial → True)
        tri = first_file.query_one(_InlineTriState)
        tri.toggle()
        await pilot.pause()

        # All children should be selected
        for mr in tree.match_rows_for(first_file):
            assert mr.query_one(_InlineCheckbox).value is True
        assert tree.all_selected is True


@pytest.mark.asyncio
async def test_toggle_file_deselects_all_children() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        first_file = tree.file_rows()[0]
        tri = first_file.query_one(_InlineTriState)
        # True → False
        tri.toggle()
        await pilot.pause()

        for mr in tree.match_rows_for(first_file):
            assert mr.query_one(_InlineCheckbox).value is False
        assert tree.all_selected is False


@pytest.mark.asyncio
async def test_selected_results_excludes_unchecked() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        # Uncheck all matches in first file
        first_file = tree.file_rows()[0]
        tri = first_file.query_one(_InlineTriState)
        tri.toggle()  # True → False
        await pilot.pause()

        selected = tree.selected_results
        assert len(selected) == 1  # only the match from b.py
        assert selected[0].file_path == _WS / "src/b.py"


@pytest.mark.asyncio
async def test_all_selected_true_when_all_checked() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        assert tree.all_selected is True


@pytest.mark.asyncio
async def test_all_selected_false_when_partial() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        first_match = tree.match_rows_for(tree.file_rows()[0])[0]
        first_match.query_one(_InlineCheckbox).toggle()
        await pilot.pause()
        assert tree.all_selected is False


# ---------------------------------------------------------------------------
# Empty state tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_tree_selected_results() -> None:
    async with _TreeApp([], _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        assert tree.selected_results == []


@pytest.mark.asyncio
async def test_empty_tree_all_selected() -> None:
    async with _TreeApp([], _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        assert tree.all_selected is True  # vacuously true


@pytest.mark.asyncio
async def test_empty_tree_home_end_no_error() -> None:
    async with _TreeApp([], _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.press("home")
        await pilot.press("end")
        # No error should occur


@pytest.mark.asyncio
async def test_home_end_with_data() -> None:
    """Home/End navigate to first/last visible row in a populated tree."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        # Move cursor to the last row via End
        await pilot.press("end")
        await pilot.pause()
        last_row = tree.cursor_node
        assert last_row is not None

        # Move cursor to the first row via Home
        await pilot.press("home")
        await pilot.pause()
        first_row = tree.cursor_node
        assert first_row is not None

        # First and last should differ (tree has multiple rows)
        assert first_row is not last_row
        # First row should be the first file row
        assert first_row is tree.file_rows()[0]


# ---------------------------------------------------------------------------
# Node data tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_row_data() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        first_file = tree.file_rows()[0]
        file_path, line_number = first_file.data
        assert file_path == _WS / "src/a.py"
        assert line_number == 10


@pytest.mark.asyncio
async def test_match_row_data() -> None:
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()
        match_row = tree.match_rows_for(tree.file_rows()[0])[1]
        file_path, line_number = match_row.data
        assert file_path == _WS / "src/a.py"
        assert line_number == 20


# ---------------------------------------------------------------------------
# Focus memory tests
# ---------------------------------------------------------------------------


class _FocusCycleApp(App):
    """App with an input before and after the CheckboxTree for focus cycling."""

    CSS = """
    CheckboxTree { height: 1fr; }
    """

    def __init__(self, results: list[WorkspaceSearchResult], workspace: Path) -> None:
        super().__init__()
        self._results = results
        self._workspace = workspace

    def compose(self) -> ComposeResult:
        from textual.widgets import Input

        yield Input(id="before")
        yield CheckboxTree(id="tree")
        yield Input(id="after")

    def on_mount(self) -> None:
        tree = self.query_one("#tree", CheckboxTree)
        tree.populate(self._results, self._workspace)


@pytest.mark.asyncio
async def test_focus_restored_on_tree_refocus() -> None:
    """When the tree regains focus, the last-focused row should be restored."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        # Set virtual cursor to the second match row
        tree.focus()
        await pilot.pause()
        second_match = tree.match_rows_for(tree.file_rows()[0])[1]
        tree._set_cursor(second_match)
        await pilot.pause()
        assert tree._last_focused_row is second_match

        # Move focus away from the tree entirely
        tree.screen.set_focus(None)
        await pilot.pause()

        # Re-focus the tree container — cursor should be restored
        tree.focus()
        await pilot.pause()
        assert second_match.has_class("-cursor")


@pytest.mark.asyncio
async def test_focus_cycle_restores_cursor_position() -> None:
    """Tab cycling away and back restores the previously focused row, not the last.

    This tests the real-world scenario: CheckboxTree rows should not appear
    as individual focusable targets in the external focus chain (Tab/Shift+Tab).
    Instead, focusing the CheckboxTree should always redirect to the last-focused row.
    """
    from textual.widgets import Input

    async with _FocusCycleApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        # Move virtual cursor to the first match row
        first_file = tree.file_rows()[0]
        first_match = tree.match_rows_for(first_file)[0]
        tree._set_cursor(first_match)
        await pilot.pause()
        assert first_match.has_class("-cursor")

        # Tab to the next widget after the tree
        await pilot.press("tab")
        await pilot.pause()

        # Should land on #after, NOT stay in the tree
        focused = pilot.app.screen.focused
        assert isinstance(focused, Input), (
            f"Tab should leave tree to #after input, but focused: {focused}"
        )

        # Focus previous — should go back to CheckboxTree
        pilot.app.screen.focus_previous()
        await pilot.pause()

        # CheckboxTree has focus, cursor highlight on first_match
        assert pilot.app.screen.focused is tree
        assert first_match.has_class("-cursor")


# ---------------------------------------------------------------------------
# Inline checkbox rendering tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inline_checkbox_renders_button_only() -> None:
    """_InlineCheckbox should render only the toggle button, no label padding."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        match_row = tree.match_rows_for(tree.file_rows()[0])[0]
        cb = match_row.query_one(_InlineCheckbox)
        rendered = cb.render()
        # Should be exactly 3 chars wide (▐X▌) — no label, no padding
        text = rendered.plain
        assert len(text) == 3


@pytest.mark.asyncio
async def test_tristate_partial_renders_warning_style() -> None:
    """TriStateCheckbox in partial state should have the -partial CSS class."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        # Make file partial by unchecking one match
        first_file = tree.file_rows()[0]
        first_match = tree.match_rows_for(first_file)[0]
        first_match.query_one(_InlineCheckbox).toggle()
        await pilot.pause()

        tri = first_file.query_one(_InlineTriState)
        assert tri.has_class("-partial")
        assert not tri.has_class("-on")


# ---------------------------------------------------------------------------
# Cursor highlight tests (blur state)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cursor_highlight_persists_on_blur() -> None:
    """Last-focused row retains -cursor CSS class when tree loses focus."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        tree.focus()
        await pilot.pause()
        second_match = tree.match_rows_for(tree.file_rows()[0])[1]
        tree._set_cursor(second_match)
        await pilot.pause()

        assert second_match.has_class("-cursor")

        # Move focus away
        tree.screen.set_focus(None)
        await pilot.pause()

        # -cursor class should still be present even without focus
        assert second_match.has_class("-cursor")


@pytest.mark.asyncio
async def test_cursor_color_differs_between_focus_and_blur() -> None:
    """Cursor row uses different background when tree is focused vs blurred.

    Focused: $block-cursor-background (bright)
    Blurred: $block-cursor-blurred-background (dim)
    """
    async with _FocusCycleApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        from textual.widgets import Input

        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        first_file = tree.file_rows()[0]
        tree._set_cursor(first_file)
        await pilot.pause()

        # When tree is focused, cursor row should have focused styling
        assert first_file.has_class("-cursor")
        focused_bg = first_file.styles.background

        # Move focus away
        pilot.app.query_one("#after", Input).focus()
        await pilot.pause()

        # Cursor row should still be highlighted but with blurred styling
        assert first_file.has_class("-cursor")
        blurred_bg = first_file.styles.background

        # The two backgrounds should differ
        assert focused_bg != blurred_bg, (
            f"Focused bg ({focused_bg}) should differ from blurred bg ({blurred_bg})"
        )


@pytest.mark.asyncio
async def test_label_click_moves_cursor() -> None:
    """Clicking a row's label should move the virtual cursor to that row."""
    from textual_code.widgets.checkbox_tree import _LabelClicked, _NodeLabel

    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        # Set cursor to first file row
        first_file = tree.file_rows()[0]
        tree._set_cursor(first_file)
        await pilot.pause()
        assert first_file.has_class("-cursor")

        # Click the label of the second file row
        second_file = tree.file_rows()[1]
        label = second_file.query_one(_NodeLabel)
        label.post_message(_LabelClicked(label))
        await pilot.pause()

        # Cursor should have moved to second file row
        assert second_file.has_class("-cursor")
        assert not first_file.has_class("-cursor")


# ---------------------------------------------------------------------------
# Left/Right arrow key tests (expand/collapse + parent/child navigation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_left_on_expanded_file_collapses() -> None:
    """Left arrow on an expanded file row collapses it."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        first_file = tree.file_rows()[0]
        tree._set_cursor(first_file)
        await pilot.pause()

        # File is expanded by default
        from textual_code.widgets.checkbox_tree import _ExpandToggle

        assert first_file.query_one(_ExpandToggle).expanded

        await pilot.press("left")
        await pilot.pause()

        # Should collapse
        assert not first_file.query_one(_ExpandToggle).expanded
        # Cursor stays on file row
        assert first_file.has_class("-cursor")


@pytest.mark.asyncio
async def test_left_on_collapsed_file_does_nothing() -> None:
    """Left arrow on already-collapsed file row stays put."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        first_file = tree.file_rows()[0]
        tree._set_cursor(first_file)
        tree.collapse_all()
        await pilot.pause()

        await pilot.press("left")
        await pilot.pause()

        # Still on same row, still collapsed
        assert first_file.has_class("-cursor")


@pytest.mark.asyncio
async def test_left_on_match_moves_to_parent_file() -> None:
    """Left arrow on a match row moves cursor to its parent file row."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        first_file = tree.file_rows()[0]
        first_match = tree.match_rows_for(first_file)[0]
        tree._set_cursor(first_match)
        await pilot.pause()

        await pilot.press("left")
        await pilot.pause()

        assert first_file.has_class("-cursor")
        assert not first_match.has_class("-cursor")


@pytest.mark.asyncio
async def test_right_on_collapsed_file_expands() -> None:
    """Right arrow on a collapsed file row expands it."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        first_file = tree.file_rows()[0]
        tree._set_cursor(first_file)
        tree.collapse_all()
        await pilot.pause()

        from textual_code.widgets.checkbox_tree import _ExpandToggle

        assert not first_file.query_one(_ExpandToggle).expanded

        await pilot.press("right")
        await pilot.pause()

        assert first_file.query_one(_ExpandToggle).expanded


@pytest.mark.asyncio
async def test_right_on_expanded_file_moves_to_first_child() -> None:
    """Right arrow on an already-expanded file row moves to first match."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        first_file = tree.file_rows()[0]
        tree._set_cursor(first_file)
        await pilot.pause()

        await pilot.press("right")
        await pilot.pause()

        first_match = tree.match_rows_for(first_file)[0]
        assert first_match.has_class("-cursor")


# ---------------------------------------------------------------------------
# Ctrl+Left/Right scroll tests
# ---------------------------------------------------------------------------


_LONG_RESULTS = _make_results(
    _WS,
    {
        "src/very_long_directory_name/extremely_long_file_name_that_exceeds_width.py": [
            (1, "x" * 200, 0, 1),
        ],
    },
)


@pytest.mark.asyncio
async def test_horizontal_scroll_with_long_content() -> None:
    """CheckboxTree supports horizontal scrolling for long file names."""
    async with _TreeApp(_LONG_RESULTS, _WS).run_test(size=(30, 10)) as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        # Virtual width should exceed visible width
        assert tree.virtual_size.width > tree.size.width

        # Ctrl+Right should scroll right
        await pilot.press("ctrl+right")
        await pilot.pause()
        assert tree.scroll_offset.x > 0


# ---------------------------------------------------------------------------
# Sidebar key hints test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sidebar_search_key_hints(tmp_path: Path) -> None:
    """WorkspaceSearchPane displays key hints below the tree."""
    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    ws = tmp_path / "ws_hints"
    ws.mkdir(exist_ok=True)
    (ws / "f.txt").write_bytes(b"x\n")

    app = make_app(ws)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        pane = app.query_one(WorkspaceSearchPane)
        from textual.widgets import Label

        hints = pane.query_one("#ws-key-hints", Label)
        rendered = hints.render()
        assert isinstance(rendered, Content)
        text = rendered.plain
        assert "Navigate" in text


# ---------------------------------------------------------------------------
# Search summary label tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_summary_label_shows_counts(tmp_path: Path) -> None:
    """Summary label shows file count and match count after search."""
    from textual.widgets import Label

    from tests.conftest import make_app
    from textual_code.search import WorkspaceSearchResponse
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    ws = tmp_path / "ws_summary"
    ws.mkdir(exist_ok=True)
    (ws / "f.txt").write_bytes(b"x\n")

    results = [
        WorkspaceSearchResult(
            file_path=Path("/a.txt"),
            line_number=1,
            line_text="hello",
            match_start=0,
            match_end=5,
        ),
        WorkspaceSearchResult(
            file_path=Path("/a.txt"),
            line_number=2,
            line_text="hello",
            match_start=0,
            match_end=5,
        ),
        WorkspaceSearchResult(
            file_path=Path("/b.txt"),
            line_number=1,
            line_text="hello",
            match_start=0,
            match_end=5,
        ),
    ]
    response = WorkspaceSearchResponse(results=results, is_truncated=False)

    app = make_app(ws)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()
        pane = app.query_one(WorkspaceSearchPane)
        pane._populate_results(response, ws)
        await pilot.pause()
        summary = pane.query_one("#ws-search-summary", Label)
        rendered = summary.render()
        assert isinstance(rendered, Content)
        text = rendered.plain
        assert "2 files" in text
        assert "3 matches" in text


@pytest.mark.asyncio
async def test_search_summary_shows_truncated_notation(tmp_path: Path) -> None:
    """Summary label shows '+' suffix when results are truncated."""
    from textual.widgets import Label

    from tests.conftest import make_app
    from textual_code.search import WorkspaceSearchResponse
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    ws = tmp_path / "ws_trunc"
    ws.mkdir(exist_ok=True)
    (ws / "f.txt").write_bytes(b"x\n")

    results = [
        WorkspaceSearchResult(
            file_path=Path("/a.txt"),
            line_number=1,
            line_text="hello",
            match_start=0,
            match_end=5,
        ),
        WorkspaceSearchResult(
            file_path=Path("/b.txt"),
            line_number=1,
            line_text="hello",
            match_start=0,
            match_end=5,
        ),
        WorkspaceSearchResult(
            file_path=Path("/c.txt"),
            line_number=1,
            line_text="hello",
            match_start=0,
            match_end=5,
        ),
    ]
    response = WorkspaceSearchResponse(results=results, is_truncated=True)

    app = make_app(ws)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()
        pane = app.query_one(WorkspaceSearchPane)
        pane._populate_results(response, ws)
        await pilot.pause()
        summary = pane.query_one("#ws-search-summary", Label)
        rendered = summary.render()
        assert isinstance(rendered, Content)
        text = rendered.plain
        assert "3+" in text
        assert "+" in text


@pytest.mark.asyncio
async def test_search_summary_singular_form(tmp_path: Path) -> None:
    """Summary label uses singular form for 1 file and 1 match."""
    from textual.widgets import Label

    from tests.conftest import make_app
    from textual_code.search import WorkspaceSearchResponse
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    ws = tmp_path / "ws_singular"
    ws.mkdir(exist_ok=True)
    (ws / "f.txt").write_bytes(b"x\n")

    results = [
        WorkspaceSearchResult(
            file_path=Path("/a.txt"),
            line_number=1,
            line_text="hello",
            match_start=0,
            match_end=5,
        ),
    ]
    response = WorkspaceSearchResponse(results=results, is_truncated=False)

    app = make_app(ws)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()
        pane = app.query_one(WorkspaceSearchPane)
        pane._populate_results(response, ws)
        await pilot.pause()
        summary = pane.query_one("#ws-search-summary", Label)
        rendered = summary.render()
        assert isinstance(rendered, Content)
        text = rendered.plain
        assert "1 file," in text
        assert "1 match" in text
        assert "files" not in text
        assert "matches" not in text


@pytest.mark.asyncio
async def test_search_summary_empty_when_no_results(tmp_path: Path) -> None:
    """Summary label is empty when no results found."""
    from textual.widgets import Label

    from tests.conftest import make_app
    from textual_code.search import WorkspaceSearchResponse
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    ws = tmp_path / "ws_empty"
    ws.mkdir(exist_ok=True)
    (ws / "f.txt").write_bytes(b"x\n")

    response = WorkspaceSearchResponse(results=[], is_truncated=False)

    app = make_app(ws)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()
        pane = app.query_one(WorkspaceSearchPane)
        pane._populate_results(response, ws)
        await pilot.pause()
        summary = pane.query_one("#ws-search-summary", Label)
        rendered = summary.render()
        assert isinstance(rendered, Content)
        assert rendered.plain.strip() == ""


@pytest.mark.asyncio
async def test_search_summary_cleared_on_option_change(tmp_path: Path) -> None:
    """Summary label is cleared when a search option checkbox changes."""
    from textual.widgets import Checkbox, Label

    from tests.conftest import make_app
    from textual_code.search import WorkspaceSearchResponse
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    ws = tmp_path / "ws_clear"
    ws.mkdir(exist_ok=True)
    (ws / "f.txt").write_bytes(b"x\n")

    results = [
        WorkspaceSearchResult(
            file_path=Path("/a.txt"),
            line_number=1,
            line_text="hello",
            match_start=0,
            match_end=5,
        ),
    ]
    response = WorkspaceSearchResponse(results=results, is_truncated=False)

    app = make_app(ws)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()
        pane = app.query_one(WorkspaceSearchPane)
        pane._populate_results(response, ws)
        await pilot.pause()

        # Toggle a search option checkbox to trigger clear
        regex_cb = pane.query_one("#ws-regex", Checkbox)
        regex_cb.value = not regex_cb.value
        await pilot.pause()

        summary = pane.query_one("#ws-search-summary", Label)
        rendered = summary.render()
        assert isinstance(rendered, Content)
        assert rendered.plain.strip() == ""


# ---------------------------------------------------------------------------
# Replace preview scope-info tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replace_preview_shows_scope_info() -> None:
    """ReplacePreviewScreen always shows scope-info label."""
    from textual.app import App
    from textual.content import Content
    from textual.widgets import Label

    from textual_code.modals import ReplacePreviewScreen
    from textual_code.search import FileDiffPreview

    preview = FileDiffPreview(
        file_path=Path("/tmp/test.txt"),
        rel_path="test.txt",
        original_hash="abc",
        replacement_count=1,
        diff_lines=["--- test.txt\n", "+++ test.txt\n", "-old\n", "+new\n"],
    )

    class _ModalApp(App):
        def on_mount(self) -> None:
            self.push_screen(ReplacePreviewScreen([preview]))

    async with _ModalApp().run_test() as pilot:
        await pilot.pause()
        scope_info = pilot.app.screen.query_one("#scope-info", Label)
        rendered = scope_info.render()
        assert isinstance(rendered, Content)
        assert "Only the checked matches" in rendered.plain


@pytest.mark.asyncio
async def test_replace_preview_always_shows_scope_info() -> None:
    """ReplacePreviewScreen shows scope-info regardless of result count."""
    from textual.app import App
    from textual.content import Content
    from textual.widgets import Label

    from textual_code.modals import ReplacePreviewScreen
    from textual_code.search import FileDiffPreview

    previews = [
        FileDiffPreview(
            file_path=Path("/tmp/a.txt"),
            rel_path="a.txt",
            original_hash="abc",
            replacement_count=3,
            diff_lines=["--- a.txt\n", "+++ a.txt\n", "-old\n", "+new\n"],
        ),
        FileDiffPreview(
            file_path=Path("/tmp/b.txt"),
            rel_path="b.txt",
            original_hash="def",
            replacement_count=2,
            diff_lines=["--- b.txt\n", "+++ b.txt\n", "-x\n", "+y\n"],
        ),
    ]

    class _ModalApp(App):
        def on_mount(self) -> None:
            self.push_screen(ReplacePreviewScreen(previews))

    async with _ModalApp().run_test() as pilot:
        await pilot.pause()
        scope_info = pilot.app.screen.query_one("#scope-info", Label)
        rendered = scope_info.render()
        assert isinstance(rendered, Content)
        assert "Only the checked matches" in rendered.plain


# ---------------------------------------------------------------------------
# expand_all / collapse_all tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expand_all() -> None:
    """expand_all() shows all match rows."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        tree.collapse_all()
        await pilot.pause()

        # All match rows should be hidden
        for fr in tree.file_rows():
            for mr in tree.match_rows_for(fr):
                assert mr.display is False

        tree.expand_all()
        await pilot.pause()

        # All match rows should be visible
        for fr in tree.file_rows():
            for mr in tree.match_rows_for(fr):
                assert mr.display is True


@pytest.mark.asyncio
async def test_collapse_all() -> None:
    """collapse_all() hides all match rows."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        tree.collapse_all()
        await pilot.pause()

        for fr in tree.file_rows():
            for mr in tree.match_rows_for(fr):
                assert mr.display is False


# ---------------------------------------------------------------------------
# cursor_node property test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cursor_node_property() -> None:
    """cursor_node returns the currently focused row."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        # Initially no cursor
        assert tree.cursor_node is None

        # Set cursor to a row
        first_file = tree.file_rows()[0]
        tree._set_cursor(first_file)
        await pilot.pause()

        assert tree.cursor_node is first_file


# ---------------------------------------------------------------------------
# remove_file_row / remove_match_row tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_match_row() -> None:
    """remove_match_row() removes a single match and updates parent."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        first_file = tree.file_rows()[0]
        matches = tree.match_rows_for(first_file)
        assert len(matches) == 2

        tree.remove_match_row(matches[0])
        await pilot.pause()

        assert len(tree.match_rows_for(first_file)) == 1


@pytest.mark.asyncio
async def test_remove_only_match_removes_file() -> None:
    """Removing the only match in a file also removes the file row."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        # b.py has 1 match
        second_file = tree.file_rows()[1]
        matches = tree.match_rows_for(second_file)
        assert len(matches) == 1

        tree.remove_match_row(matches[0])
        await pilot.pause()

        # File row should also be gone
        assert len(tree.file_rows()) == 1


@pytest.mark.asyncio
async def test_remove_file_row() -> None:
    """remove_file_row() removes a file and all its matches."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        assert len(tree.file_rows()) == 2
        tree.remove_file_row(tree.file_rows()[0])
        await pilot.pause()

        remaining = tree.file_rows()
        assert len(remaining) == 1
        assert "src/b.py" in remaining[0].label_text


# ---------------------------------------------------------------------------
# Navigation: page_down, page_up, toggle, select
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_page_down_up_navigation() -> None:
    """PageDown/PageUp navigate within the tree."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        # Navigate down first
        await pilot.press("down")
        await pilot.pause()

        # PageDown
        await pilot.press("pagedown")
        await pilot.pause()
        row_after_pagedown = tree._last_focused_row
        assert row_after_pagedown is not None

        # PageUp should navigate back
        await pilot.press("pageup")
        await pilot.pause()
        row_after_pageup = tree._last_focused_row
        assert row_after_pageup is not None


@pytest.mark.asyncio
async def test_toggle_cursor_check_on_match_row() -> None:
    """Space toggles the checkbox on the current cursor match row."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        # Navigate to a match row
        file_rows = tree.file_rows()
        match_rows = tree.match_rows_for(file_rows[0])
        tree._set_cursor(match_rows[0])
        await pilot.pause()

        # Toggle via action
        tree.action_toggle_cursor_check()
        await pilot.pause()
        cb = match_rows[0].query_one(_InlineCheckbox)
        assert cb.value is False  # was True, toggled to False


@pytest.mark.asyncio
async def test_toggle_cursor_check_on_file_row() -> None:
    """Space toggles the tri-state checkbox on a file row."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        file_row = tree.file_rows()[0]
        tree._set_cursor(file_row)
        await pilot.pause()

        tree.action_toggle_cursor_check()
        await pilot.pause()
        tri = file_row.query_one(_InlineTriState)
        # Was True (all checked), toggled to False
        assert tri.value is False


@pytest.mark.asyncio
async def test_select_cursor_node_posts_message() -> None:
    """Enter on a cursor row posts NodeSelected message."""
    messages: list[CheckboxTree.NodeSelected] = []

    class _App(App):
        def compose(self) -> ComposeResult:
            yield CheckboxTree(id="tree")

        def on_mount(self) -> None:
            self.query_one("#tree", CheckboxTree).populate(_SAMPLE_RESULTS, _WS)

        def on_checkbox_tree_node_selected(
            self, event: CheckboxTree.NodeSelected
        ) -> None:
            messages.append(event)

    async with _App().run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        tree.focus()
        await pilot.pause()

        # Set cursor to first match row
        match_row = tree.match_rows_for(tree.file_rows()[0])[0]
        tree._set_cursor(match_row)
        await pilot.pause()

        tree.action_select_cursor_node()
        await pilot.pause()
        assert len(messages) == 1
        assert messages[0].file_path == _WS / "src/a.py"
        assert messages[0].line_number == 10
