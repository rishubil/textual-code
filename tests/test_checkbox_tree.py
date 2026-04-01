"""Tests for CheckboxTree widget and TriStateCheckbox."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult

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


@pytest.mark.asyncio
async def test_focus_restored_on_tree_refocus() -> None:
    """When the tree regains focus, the last-focused row should be restored."""
    async with _TreeApp(_SAMPLE_RESULTS, _WS).run_test() as pilot:
        tree = pilot.app.query_one("#tree", CheckboxTree)
        await pilot.pause()

        # Focus the second match row
        second_match = tree.match_rows_for(tree.file_rows()[0])[1]
        second_match.focus()
        await pilot.pause()
        assert tree._last_focused_row is second_match

        # Move focus away from the tree entirely
        tree.screen.set_focus(None)
        await pilot.pause()

        # Re-focus the tree container
        tree.focus()
        await pilot.pause()

        # The previously focused row should be restored
        assert pilot.app.screen.focused is second_match


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

        second_match = tree.match_rows_for(tree.file_rows()[0])[1]
        second_match.focus()
        await pilot.pause()

        assert second_match.has_class("-cursor")

        # Move focus away
        tree.screen.set_focus(None)
        await pilot.pause()

        # -cursor class should still be present even without focus
        assert second_match.has_class("-cursor")


# ---------------------------------------------------------------------------
# Replace preview truncation warning test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replace_preview_shows_truncation_warning() -> None:
    """ReplacePreviewScreen shows warning when is_truncated is True."""
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
            self.push_screen(ReplacePreviewScreen([preview], is_truncated=True))

    async with _ModalApp().run_test() as pilot:
        await pilot.pause()
        warning = pilot.app.screen.query_one("#truncation-warning", Label)
        rendered = warning.render()
        assert isinstance(rendered, Content)
        assert "More files" in rendered.plain


@pytest.mark.asyncio
async def test_replace_preview_no_warning_when_not_truncated() -> None:
    """ReplacePreviewScreen does not show warning when is_truncated is False."""
    from textual.app import App
    from textual.css.query import NoMatches

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
            self.push_screen(ReplacePreviewScreen([preview], is_truncated=False))

    async with _ModalApp().run_test() as pilot:
        await pilot.pause()
        with pytest.raises(NoMatches):
            pilot.app.screen.query_one("#truncation-warning")


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

        # Focus a row
        first_file = tree.file_rows()[0]
        first_file.focus()
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
