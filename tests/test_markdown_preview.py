"""
Tests for the Markdown Preview tab feature.
"""

from pathlib import Path

import pytest

from tests.conftest import make_app, wait_for_condition
from textual_code.widgets.markdown_preview import (
    MARKDOWN_EXTENSIONS,
    MarkdownPreviewPane,
    _make_parser,
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


# ── 1. test_preview_tab_opens_for_markdown_file ───────────────────────────────


async def test_preview_tab_opens_for_markdown_file(workspace: Path, md_file: Path):
    """Opening preview for a markdown file adds a new pane."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        initial_count = len(app.main_view.opened_pane_ids)
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view.opened_pane_ids) == initial_count + 1


# ── 2. test_preview_tab_not_opened_for_non_markdown ──────────────────────────


async def test_preview_tab_not_opened_for_non_markdown(workspace: Path, py_file: Path):
    """Opening preview for a .py file is a no-op."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        initial_count = len(app.main_view.opened_pane_ids)
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view.opened_pane_ids) == initial_count


# ── 3. test_preview_tab_not_opened_without_open_file ─────────────────────────


async def test_preview_tab_not_opened_without_open_file(workspace: Path):
    """Opening preview with no editor open is a no-op."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        initial_count = len(app.main_view.opened_pane_ids)
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view.opened_pane_ids) == initial_count


# ── 4. test_preview_tab_switch_to_existing ────────────────────────────────────


async def test_preview_tab_switch_to_existing(workspace: Path, md_file: Path):
    """Calling open preview twice does not create a duplicate tab."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()
        count_after_first = len(app.main_view.opened_pane_ids)
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view.opened_pane_ids) == count_after_first


# ── 5. test_preview_tab_title ─────────────────────────────────────────────────


async def test_preview_tab_title(workspace: Path, md_file: Path):
    """Preview tab label includes 'Preview:' and the filename."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()
        pane_id = app.main_view._preview_pane_ids[md_file]
        tc = app.main_view._tc_for_pane(pane_id)
        assert tc is not None
        tab = tc.get_tab(pane_id)
        assert "Preview:" in str(tab.label)
        assert md_file.name in str(tab.label)


# ── 6. test_ctrl_shift_m_opens_tab ────────────────────────────────────────────


async def test_ctrl_shift_m_opens_tab(workspace: Path, md_file: Path):
    """Ctrl+Shift+M opens a markdown preview tab."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        initial_count = len(app.main_view.opened_pane_ids)
        await pilot.press("ctrl+shift+m")
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view.opened_pane_ids) == initial_count + 1


# ── 7. test_preview_tab_updates_on_text_change ────────────────────────────────


async def test_preview_tab_updates_on_text_change(workspace: Path, md_file: Path):
    """When editor text changes, the preview tab content updates."""
    from textual.widgets import Markdown as MarkdownWidget

    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Get editor reference before opening preview (focus shifts after)
        editor = app.main_view._get_active_code_editor_in_split("left")
        assert editor is not None

        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        pane_id = app.main_view._preview_pane_ids[md_file]
        tc = app.main_view._tc_for_pane(pane_id)
        assert tc is not None
        preview = tc.get_pane(pane_id).query_one(MarkdownPreviewPane)
        md_widget = preview.query_one(MarkdownWidget)

        new_text = "# Updated\n\nNew content\n"
        editor.text = new_text
        # Wait for debounce timer (0.3s) to fire and update preview
        await wait_for_condition(
            pilot,
            lambda: md_widget._markdown == new_text,
            msg="Preview did not update after debounce",
        )

        assert md_widget._markdown == new_text


# ── 8. test_preview_no_update_when_tab_closed ────────────────────────────────


async def test_preview_no_update_when_tab_closed(workspace: Path, md_file: Path):
    """After the preview tab is closed, text changes do not cause errors."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        pane_id = app.main_view._preview_pane_ids.get(md_file)
        assert pane_id is not None

        # Close the preview tab manually
        await app.main_view.close_pane(pane_id)
        app.main_view._preview_pane_ids.pop(md_file, None)
        await pilot.wait_for_scheduled_animations()

        # Text change should not raise
        editor = app.main_view._get_active_code_editor_in_split("left")
        assert editor is not None
        editor.text = "# Changed\n"
        await pilot.wait_for_scheduled_animations()
        # No exception means pass


# ── 9. test_preview_tab_closes_with_source ────────────────────────────────────


async def test_preview_tab_closes_with_source(workspace: Path, md_file: Path):
    """Closing the source editor also closes the preview tab."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Capture source editor reference before preview tab steals focus
        editor = app.main_view._get_active_code_editor_in_split("left")
        assert editor is not None

        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        preview_pane_id = app.main_view._preview_pane_ids.get(md_file)
        assert preview_pane_id is not None
        assert app.main_view.is_opened_pane(preview_pane_id)

        # Close via CodeEditor.action_close() to trigger on_code_editor_closed
        editor.action_close()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert not app.main_view.is_opened_pane(preview_pane_id)
        assert md_file not in app.main_view._preview_pane_ids


# ── 10. test_ctrl_w_closes_preview_tab ───────────────────────────────────────


async def test_ctrl_w_closes_preview_tab(workspace: Path, md_file: Path):
    """Ctrl+W closes a focused preview tab."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        preview_pane_id = app.main_view._preview_pane_ids.get(md_file)
        assert preview_pane_id is not None
        assert app.main_view.is_opened_pane(preview_pane_id)

        # Focus the preview tab then close via action_close
        app.main_view.focus_pane(preview_pane_id)
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_close_editor()
        await pilot.wait_for_scheduled_animations()

        assert not app.main_view.is_opened_pane(preview_pane_id)


# ── 11. test_preview_tab_and_split_coexist ────────────────────────────────────


async def test_preview_tab_and_split_coexist(workspace: Path, md_file: Path):
    """Preview tab works correctly alongside a split view."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        # Go back to left split and open preview
        app.main_view.action_focus_left_split()
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        assert md_file in app.main_view._preview_pane_ids
        preview_pane_id = app.main_view._preview_pane_ids[md_file]
        assert app.main_view.is_opened_pane(preview_pane_id)


# ── 12. test_clicking_preview_pane_updates_active_leaf ─────────────────────────


async def test_clicking_preview_pane_updates_active_leaf(
    workspace: Path, md_file: Path
):
    """Clicking on MarkdownPreviewPane gives it focus."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Get editor reference before preview steals focus
        editor = app.main_view._get_active_code_editor_in_split("left")
        assert editor is not None

        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        preview_pane_id = app.main_view._preview_pane_ids[md_file]
        tc = app.main_view._tc_for_pane(preview_pane_id)
        assert tc is not None

        # Activate the preview tab so it's visible
        tc.active = preview_pane_id
        await pilot.wait_for_scheduled_animations()

        # Focus the editor (simulates user clicking away from preview)
        editor.focus()
        await pilot.wait_for_scheduled_animations()

        # Click on the preview pane content
        preview = tc.get_pane(preview_pane_id).query_one(MarkdownPreviewPane)
        await pilot.click(MarkdownPreviewPane)
        await pilot.wait_for_scheduled_animations()

        # The preview pane should have received focus
        assert preview.has_focus


# ── 13. test_preview_update_is_debounced ──────────────────────────────────────


async def test_preview_update_is_debounced(workspace: Path, md_file: Path):
    """Rapid text changes should trigger only one preview update, not three."""
    from unittest.mock import patch

    from textual.widgets import Markdown as MarkdownWidget

    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view._get_active_code_editor_in_split("left")
        assert editor is not None

        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        pane_id = app.main_view._preview_pane_ids[md_file]
        tc = app.main_view._tc_for_pane(pane_id)
        assert tc is not None
        preview = tc.get_pane(pane_id).query_one(MarkdownPreviewPane)
        md_widget = preview.query_one(MarkdownWidget)

        # Spy on Markdown.update to count calls
        original_update = md_widget.update
        call_count = 0

        async def counting_update(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return await original_update(*args, **kwargs)

        with patch.object(md_widget, "update", side_effect=counting_update):
            # Rapid consecutive changes
            editor.text = "# One"
            editor.text = "# Two"
            editor.text = "# Three"

            # Wait for debounce timer (0.3s) to fire and update to complete
            await wait_for_condition(
                pilot,
                lambda: md_widget._markdown == "# Three",
                msg="Debounce timer did not fire or update did not complete",
            )

        # With debounce, update should be called once (not three times)
        assert call_count == 1, f"Expected 1 update call, got {call_count}"
        assert md_widget._markdown == "# Three"


# ── 14. test_preview_tab_focus_resets_footer ──────────────────────────────────


async def test_preview_tab_focus_resets_footer(workspace: Path, md_file: Path):
    """Activating a preview tab resets the footer (no active code editor)."""
    from textual_code.widgets.code_editor import CodeEditorFooter

    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Footer should have editor info initially
        footer = app.main_view.query_one(CodeEditorFooter)
        assert footer.path is not None

        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        preview_pane_id = app.main_view._preview_pane_ids[md_file]
        app.main_view.focus_pane(preview_pane_id)
        await pilot.wait_for_scheduled_animations()

        # Footer should be reset since preview pane has no code editor
        assert footer.path is None


# ── 15. test_preview_focus_does_not_shift_content ─────────────────────────────


async def test_preview_focus_does_not_shift_content(workspace: Path, md_file: Path):
    """Focus highlight must use outline (not border) so content doesn't shift."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        preview_pane_id = app.main_view._preview_pane_ids[md_file]
        tc = app.main_view._tc_for_pane(preview_pane_id)
        assert tc is not None
        preview = tc.get_pane(preview_pane_id).query_one(MarkdownPreviewPane)

        # Record size before focus
        size_before = preview.content_size

        # Focus the preview pane
        preview.focus()
        await pilot.wait_for_scheduled_animations()
        assert preview.has_focus

        # Content size must not change (outline doesn't consume space)
        size_after = preview.content_size
        assert size_before == size_after, (
            f"Content shifted: {size_before} -> {size_after}. "
            "Use outline instead of border for focus highlight."
        )


# ── 16. test_preview_tab_receives_focus_on_open ──────────────────────────────


async def test_preview_tab_receives_focus_on_open(workspace: Path, md_file: Path):
    """Opening a preview tab should give focus to the MarkdownPreviewPane."""
    app = make_app(workspace, open_file=md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        preview_pane_id = app.main_view._preview_pane_ids[md_file]
        tc = app.main_view._tc_for_pane(preview_pane_id)
        assert tc is not None
        preview = tc.get_pane(preview_pane_id).query_one(MarkdownPreviewPane)
        assert preview.has_focus


# ── Utility — extensions constant ─────────────────────────────────────────────


def test_markdown_extensions_constant():
    """MARKDOWN_EXTENSIONS includes the common extensions."""
    assert ".md" in MARKDOWN_EXTENSIONS
    assert ".markdown" in MARKDOWN_EXTENSIONS


# ── _move_trailing_spaces core rule ───────────────────────────────────────────


def _render_inline(md, source: str) -> list[tuple[str, str]]:
    """Return [(token.type, token.content), ...] for inline children."""
    tokens = md.parse(source)
    for tok in tokens:
        if tok.type == "inline":
            return [(c.type, c.content) for c in tok.children]
    return []


def test_move_trailing_spaces_bold():
    """Space after **bold** moves into the bold span's trailing text."""
    md = _make_parser()
    children = _render_inline(md, "**bold** text")
    # The text token inside the bold span should now end with a space.
    text_tokens = [(t, c) for t, c in children if t == "text"]
    assert any(c.endswith(" ") for _, c in text_tokens), (
        f"Expected a text token ending with space, got: {text_tokens}"
    )
    # The text following strong_close should NOT start with a space.
    types = [t for t, _ in children]
    close_idx = types.index("strong_close")
    if close_idx + 1 < len(children) and children[close_idx + 1][0] == "text":
        assert not children[close_idx + 1][1].startswith(" ")


def test_move_trailing_spaces_italic():
    """Space after *italic* moves into the italic span's trailing text."""
    md = _make_parser()
    children = _render_inline(md, "*italic* text")
    text_tokens = [(t, c) for t, c in children if t == "text"]
    assert any(c.endswith(" ") for _, c in text_tokens)


def test_move_trailing_spaces_strikethrough():
    """Space after ~~strike~~ moves into the span's trailing text."""
    md = _make_parser()
    children = _render_inline(md, "~~strike~~ text")
    text_tokens = [(t, c) for t, c in children if t == "text"]
    assert any(c.endswith(" ") for _, c in text_tokens)


def test_move_trailing_spaces_link():
    """Space after [link](url) moves into the link span's trailing text."""
    md = _make_parser()
    children = _render_inline(md, "[link](http://example.com) text")
    text_tokens = [(t, c) for t, c in children if t == "text"]
    assert any(c.endswith(" ") for _, c in text_tokens)


def test_move_trailing_spaces_no_space():
    """No change when there is no space after the closing tag."""
    md = _make_parser()
    children = _render_inline(md, "**bold**text")
    text_tokens = [(t, c) for t, c in children if t == "text"]
    # None of the text tokens should have an artificially added trailing space.
    assert not any(c.endswith(" ") for _, c in text_tokens)


def test_move_trailing_spaces_multiple_spans():
    """Each span's space is handled independently without cross-contamination."""
    md = _make_parser()
    children = _render_inline(md, "**bold** *italic* text")
    # Two inline spans, two spaces should be absorbed.
    text_tokens = [(t, c) for t, c in children if t == "text"]
    trailing_space_count = sum(1 for _, c in text_tokens if c.endswith(" "))
    assert trailing_space_count >= 1


async def test_markdown_widget_renders_with_space(workspace: Path):
    """Markdown widget correctly stores bold+space+normal text content."""
    from textual.widgets import Markdown as MarkdownWidget

    bold_md_file = workspace / "bold_test.md"
    bold_md_file.write_text("# Hello\n\nThis is a **Markdown** preview.\n")

    app = make_app(workspace, open_file=bold_md_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_markdown_preview()
        await pilot.wait_for_scheduled_animations()

        pane_id = app.main_view._preview_pane_ids[bold_md_file]
        tc = app.main_view._tc_for_pane(pane_id)
        assert tc is not None
        preview = tc.get_pane(pane_id).query_one(MarkdownPreviewPane)
        md_widget = preview.query_one(MarkdownWidget)

        # Content is stored with the space intact in the raw markdown.
        assert "**Markdown** preview." in md_widget._markdown
