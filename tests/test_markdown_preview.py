"""
Tests for the Markdown Preview feature.

Red-Green TDD: written before implementation so all tests initially fail,
then pass once the feature is implemented.
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.markdown_preview import (
    MARKDOWN_EXTENSIONS,
    PLACEHOLDER,
    MarkdownPreviewPane,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def md_file(workspace: Path) -> Path:
    f = workspace / "notes.md"
    f.write_text("# Hello\n\nWorld\n")
    return f


@pytest.fixture
def py_file(workspace: Path) -> Path:
    f = workspace / "main.py"
    f.write_text("print('hello')\n")
    return f


# ── Group A — Initial state ───────────────────────────────────────────────────


async def test_preview_initially_hidden(workspace: Path, md_file: Path):
    """MarkdownPreviewPane starts hidden (display=False)."""
    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        preview = app.main_view.query_one(MarkdownPreviewPane)
        assert preview.display is False


async def test_preview_visible_flag_initially_false(workspace: Path):
    """_preview_visible is False on startup."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._preview_visible is False


# ── Group B — Toggle ──────────────────────────────────────────────────────────


async def test_toggle_preview_shows_panel(workspace: Path, md_file: Path):
    """Toggling preview makes MarkdownPreviewPane visible."""
    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_toggle_markdown_preview()
        preview = app.main_view.query_one(MarkdownPreviewPane)
        assert preview.display is True


async def test_toggle_preview_sets_flag(workspace: Path, md_file: Path):
    """Toggling preview sets _preview_visible to True."""
    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_toggle_markdown_preview()
        assert app.main_view._preview_visible is True


async def test_toggle_preview_twice_hides_panel(workspace: Path, md_file: Path):
    """Toggling preview twice hides the panel again."""
    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_toggle_markdown_preview()
        await app.main_view.action_toggle_markdown_preview()
        preview = app.main_view.query_one(MarkdownPreviewPane)
        assert preview.display is False


def test_ctrl_shift_m_binding_registered():
    """BINDINGS contains the ctrl+shift+m binding."""
    from textual_code.app import MainView

    binding_keys = [b.key for b in MainView.BINDINGS]
    assert "ctrl+shift+m" in binding_keys


async def test_ctrl_shift_m_toggles_preview(workspace: Path, md_file: Path):
    """Pressing Ctrl+Shift+M opens the preview panel."""
    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+shift+m")
        await pilot.pause()
        preview = app.main_view.query_one(MarkdownPreviewPane)
        assert preview.display is True


# ── Group C — Content rendering ───────────────────────────────────────────────


async def test_preview_shows_markdown_content(workspace: Path, md_file: Path):
    """After toggle, Markdown source matches the editor content."""
    from textual.widgets import Markdown as MarkdownWidget

    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_toggle_markdown_preview()
        await pilot.pause()
        preview = app.main_view.query_one(MarkdownPreviewPane)
        md_widget = preview.query_one(MarkdownWidget)
        editor = app.main_view._get_active_code_editor_in_split("left")
        assert md_widget._markdown == editor.text


async def test_preview_placeholder_for_non_markdown(workspace: Path, py_file: Path):
    """With a non-Markdown file open, preview shows the placeholder."""
    from textual.widgets import Markdown as MarkdownWidget

    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_toggle_markdown_preview()
        await pilot.pause()
        preview = app.main_view.query_one(MarkdownPreviewPane)
        md_widget = preview.query_one(MarkdownWidget)
        assert md_widget._markdown == PLACEHOLDER


async def test_preview_placeholder_when_no_file(workspace: Path):
    """With no file open, preview shows the placeholder."""
    from textual.widgets import Markdown as MarkdownWidget

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_toggle_markdown_preview()
        await pilot.pause()
        preview = app.main_view.query_one(MarkdownPreviewPane)
        md_widget = preview.query_one(MarkdownWidget)
        assert md_widget._markdown == PLACEHOLDER


# ── Group D — Live updates ────────────────────────────────────────────────────


async def test_preview_updates_on_text_change(workspace: Path, md_file: Path):
    """When editor text changes, preview auto-updates."""
    from textual.widgets import Markdown as MarkdownWidget

    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_toggle_markdown_preview()
        await pilot.pause()

        editor = app.main_view._get_active_code_editor_in_split("left")
        new_text = "# Updated\n\nNew content\n"
        editor.text = new_text
        # post_message is called synchronously via watch_text; pause to allow processing
        await pilot.pause()
        await pilot.pause()

        preview = app.main_view.query_one(MarkdownPreviewPane)
        md_widget = preview.query_one(MarkdownWidget)
        assert md_widget._markdown == new_text


async def test_preview_no_update_when_hidden(workspace: Path, md_file: Path):
    """When preview is hidden, text changes do not update the preview."""
    from textual.widgets import Markdown as MarkdownWidget

    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Open preview so it gets initial content
        await app.main_view.action_toggle_markdown_preview()
        await pilot.pause()
        preview = app.main_view.query_one(MarkdownPreviewPane)
        md_widget = preview.query_one(MarkdownWidget)
        initial_source = md_widget._markdown

        # Close preview
        await app.main_view.action_toggle_markdown_preview()
        await pilot.pause()

        # Now change editor text
        editor = app.main_view._get_active_code_editor_in_split("left")
        editor.text = "# Changed while hidden\n"
        await pilot.pause()
        await pilot.pause()

        # Source should not have changed
        assert md_widget._markdown == initial_source


async def test_preview_updates_on_tab_change(workspace: Path, md_file: Path):
    """Switching tabs refreshes the preview to the new tab's content."""
    from textual.widgets import Markdown as MarkdownWidget

    md_file2 = workspace / "other.md"
    md_file2.write_text("## Other\n\nDifferent content\n")

    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Open second file in left split
        await app.main_view.action_open_code_editor(path=md_file2, focus=True)
        await pilot.pause()

        # Open preview (tracks newly focused tab)
        await app.main_view.action_toggle_markdown_preview()
        await pilot.pause()

        preview = app.main_view.query_one(MarkdownPreviewPane)
        md_widget = preview.query_one(MarkdownWidget)
        assert "other.md" in str(md_file2)
        # Preview should show other.md content
        assert md_widget._markdown == md_file2.read_text()


# ── Group E — Split view compatibility ───────────────────────────────────────


async def test_preview_and_split_right_coexist(workspace: Path, md_file: Path):
    """Both split_right and markdown_preview can be displayed at the same time."""
    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_toggle_markdown_preview()
        await pilot.pause()

        right_tc = app.main_view.right_tabbed_content
        preview = app.main_view.query_one(MarkdownPreviewPane)
        assert right_tc.display is True
        assert preview.display is True


async def test_preview_tracks_left_split_editor(workspace: Path, md_file: Path):
    """Editing in right split does NOT change what preview shows (tracks left)."""
    from textual.widgets import Markdown as MarkdownWidget

    py_file = workspace / "right.py"
    py_file.write_text("x = 1\n")

    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Open preview showing left editor content
        await app.main_view.action_toggle_markdown_preview()
        await pilot.pause()

        preview = app.main_view.query_one(MarkdownPreviewPane)
        md_widget = preview.query_one(MarkdownWidget)
        left_content = md_widget._markdown

        # Open split and put py file in right
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=py_file, focus=True)
        await pilot.pause()

        # Simulate text change in right editor
        right_editor = app.main_view._get_active_code_editor_in_split("right")
        if right_editor is not None:
            right_editor.text = "x = 42\n"
            await pilot.pause()
            await pilot.pause()

        # Preview still shows left content (placeholder is acceptable too since
        # the right editor is a .py file, but the main check is: NOT right editor)
        assert md_widget._markdown == left_content or md_widget._markdown == PLACEHOLDER


# ── Group F — Command palette ─────────────────────────────────────────────────


async def test_toggle_preview_cmd_no_file(workspace: Path):
    """Toggling preview via command palette with no open file does not raise."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Should not raise
        app.action_toggle_markdown_preview_cmd()
        await pilot.pause()
        await pilot.pause()
        preview = app.main_view.query_one(MarkdownPreviewPane)
        assert preview.display is True


# ── Utility — extensions constant ─────────────────────────────────────────────


def test_markdown_extensions_constant():
    """MARKDOWN_EXTENSIONS includes the common extensions."""
    assert ".md" in MARKDOWN_EXTENSIONS
    assert ".markdown" in MARKDOWN_EXTENSIONS
