"""
Indentation conversion feature tests.

Unit tests: _convert_indentation helper function
Integration tests: action_change_indent via ChangeIndentModalScreen
"""

from pathlib import Path

from textual.app import App, ComposeResult

from textual_code.widgets.code_editor import CodeEditor, _convert_indentation

# ── _convert_indentation unit tests ──────────────────────────────────────────


def test_tabs_to_spaces_size4():
    """\t → 4 spaces."""
    assert _convert_indentation("\thello", "spaces", 4) == "    hello"


def test_tabs_to_spaces_size2():
    """\t → 2 spaces."""
    assert _convert_indentation("\thello", "spaces", 2) == "  hello"


def test_spaces_to_tabs_basic():
    """4 spaces → 1 tab (size=4)."""
    assert _convert_indentation("    hello", "tabs", 4) == "\thello"


def test_spaces_to_tabs_remainder():
    """5 spaces → 1 tab + 1 space (size=4)."""
    assert _convert_indentation("     hello", "tabs", 4) == "\t hello"


def test_spaces_resize_2_to_4():
    """Converting 2-space indent to the same size leaves it unchanged."""
    # _convert_indentation normalizes directly to target type/size
    result = _convert_indentation("  hello", "spaces", 2)
    assert result == "  hello"


def test_multiline_all_converted():
    """All lines are converted."""
    text = "\thello\n\tworld"
    result = _convert_indentation(text, "spaces", 4)
    assert result == "    hello\n    world"


def test_empty_line_preserved():
    """Empty lines are preserved as-is."""
    text = "\thello\n\n\tworld"
    result = _convert_indentation(text, "spaces", 4)
    assert result == "    hello\n\n    world"


def test_no_indent_unchanged():
    """Lines with no indentation are unchanged."""
    assert _convert_indentation("hello", "spaces", 4) == "hello"
    assert _convert_indentation("hello", "tabs", 4) == "hello"


def test_already_tabs_to_tabs():
    """Tabs → tabs: same size leaves it unchanged."""
    assert _convert_indentation("\thello", "tabs", 4) == "\thello"


def test_already_spaces_to_spaces_same_size():
    """Spaces → spaces same size: no change."""
    assert _convert_indentation("    hello", "spaces", 4) == "    hello"


def test_double_indent_to_spaces():
    """Double tab → 8 spaces."""
    assert _convert_indentation("\t\thello", "spaces", 4) == "        hello"


def test_spaces_to_tabs_size8():
    """8 spaces → 1 tab (size=8)."""
    assert _convert_indentation("        hello", "tabs", 8) == "\thello"


# ── Integration tests ─────────────────────────────────────────────────────────


class _IndentTestApp(App):
    """Test app containing a CodeEditor for integration tests."""

    def __init__(self, text: str = "    hello\n    world"):
        super().__init__()
        self._initial_text = text

    def compose(self) -> ComposeResult:
        pane_id = CodeEditor.generate_pane_id()
        yield CodeEditor(pane_id=pane_id, path=None)

    async def on_mount(self) -> None:
        editor = self.query_one(CodeEditor)
        editor.replace_editor_text(self._initial_text)

    @property
    def code_editor(self) -> CodeEditor:
        return self.query_one(CodeEditor)


async def test_change_indent_modal_apply_spaces():
    """Apply Spaces 4 → text is converted to space indentation."""
    from textual.widgets import Input, Select

    app = _IndentTestApp(text="\thello\n\tworld")
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_indent()
        await pilot.pause()

        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "4"
        await pilot.click("#apply")
        await pilot.pause()

        final_text = app.screen_stack[0].query_one(CodeEditor).text

    assert "    hello" in final_text
    assert "    world" in final_text


async def test_change_indent_modal_apply_tabs():
    """Apply Tabs → text is converted to tab indentation."""
    from textual.widgets import Input, Select

    app = _IndentTestApp(text="    hello\n    world")
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_indent()
        await pilot.pause()

        app.screen.query_one("#indent_type", Select).value = "tabs"
        app.screen.query_one("#indent_size", Input).value = "4"
        await pilot.click("#apply")
        await pilot.pause()

        final_text = app.screen_stack[0].query_one(CodeEditor).text

    assert "\thello" in final_text
    assert "\tworld" in final_text


async def test_change_indent_cancel_no_change():
    """Cancel → text unchanged."""
    original = "\thello\n\tworld"
    app = _IndentTestApp(text=original)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_indent()
        await pilot.pause()

        await pilot.click("#cancel")
        await pilot.pause()

        final_text = app.screen_stack[0].query_one(CodeEditor).text

    assert final_text == original


async def test_change_indent_updates_textarea_settings():
    """After Apply, TextArea's indent_type and indent_width are updated."""
    from textual.widgets import Input, Select, TextArea

    app = _IndentTestApp(text="\thello")
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_indent()
        await pilot.pause()

        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "2"
        await pilot.click("#apply")
        await pilot.pause()

        code_editor = app.screen_stack[0].query_one(CodeEditor)
        textarea = code_editor.query_one(TextArea)
        indent_type = textarea.indent_type
        indent_width = textarea.indent_width

    assert indent_type == "spaces"
    assert indent_width == 2


# ── Footer button display tests ───────────────────────────────────────────────


async def test_footer_shows_default_indent():
    """Default indent → #indent_btn label == '4 Spaces'."""
    from textual.widgets import Button

    app = _IndentTestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        btn = app.query_one("#indent_btn", Button)
        label = str(btn.label)
    assert label == "4 Spaces"


async def test_footer_shows_tabs_after_change():
    """After applying Tabs → #indent_btn label == 'Tabs'."""
    from textual.widgets import Button, Input, Select

    app = _IndentTestApp(text="    hello\n    world")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_indent()
        await pilot.pause()
        app.screen.query_one("#indent_type", Select).value = "tabs"
        app.screen.query_one("#indent_size", Input).value = "4"
        await pilot.click("#apply")
        await pilot.pause()
        btn = app.screen_stack[0].query_one("#indent_btn", Button)
        label = str(btn.label)
    assert label == "Tabs"


async def test_footer_shows_2_spaces_after_change():
    """After applying 2 Spaces → #indent_btn label == '2 Spaces'."""
    from textual.widgets import Button, Input, Select

    app = _IndentTestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_indent()
        await pilot.pause()
        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "2"
        await pilot.click("#apply")
        await pilot.pause()
        btn = app.screen_stack[0].query_one("#indent_btn", Button)
        label = str(btn.label)
    assert label == "2 Spaces"


async def test_indent_button_opens_modal():
    """Clicking #indent_btn → ChangeIndentModalScreen becomes active."""
    from textual_code.modals import ChangeIndentModalScreen

    app = _IndentTestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#indent_btn")
        await pilot.pause()
        assert isinstance(app.screen, ChangeIndentModalScreen)


async def test_change_indent_updates_editor_reactives():
    """After applying indent change, editor indent_type and indent_size are updated."""
    from textual.widgets import Input, Select

    app = _IndentTestApp(text="\thello")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_indent()
        await pilot.pause()
        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "2"
        await pilot.click("#apply")
        await pilot.pause()
        ce = app.screen_stack[0].query_one(CodeEditor)
    assert ce.indent_type == "spaces"
    assert ce.indent_size == 2


async def test_change_indent_custom_size_3():
    """Custom indent size 3 → text indented by 3 spaces."""
    from textual.widgets import Input, Select

    app = _IndentTestApp(text="\thello\n\tworld")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_indent()
        await pilot.pause()
        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "3"
        await pilot.click("#apply")
        await pilot.pause()
        final_text = app.screen_stack[0].query_one(CodeEditor).text

    assert "   hello" in final_text  # 3 spaces
    assert "   world" in final_text


async def test_change_indent_custom_size_6():
    """Custom indent size 6 → text indented by 6 spaces."""
    from textual.widgets import Input, Select

    app = _IndentTestApp(text="\thello")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_indent()
        await pilot.pause()
        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "6"
        await pilot.click("#apply")
        await pilot.pause()
        final_text = app.screen_stack[0].query_one(CodeEditor).text

    assert "      hello" in final_text  # 6 spaces


async def test_change_indent_invalid_size_zero():
    """Input '0' for size → modal stays open (rejected)."""
    from textual.widgets import Input, Select

    from textual_code.modals import ChangeIndentModalScreen

    app = _IndentTestApp(text="\thello")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_indent()
        await pilot.pause()
        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "0"
        await pilot.click("#apply")
        await pilot.pause()
        # Modal should still be open because input is invalid
        assert isinstance(app.screen, ChangeIndentModalScreen)


async def test_change_indent_invalid_size_negative():
    """Input '-1' for size → modal stays open (rejected)."""
    from textual.widgets import Input, Select

    from textual_code.modals import ChangeIndentModalScreen

    app = _IndentTestApp(text="\thello")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_indent()
        await pilot.pause()
        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "-1"
        await pilot.click("#apply")
        await pilot.pause()
        assert isinstance(app.screen, ChangeIndentModalScreen)


async def test_change_indent_invalid_size_text():
    """Input 'abc' for size → modal stays open (rejected)."""
    from textual.widgets import Input, Select

    from textual_code.modals import ChangeIndentModalScreen

    app = _IndentTestApp(text="\thello")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.code_editor.action_change_indent()
        await pilot.pause()
        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "abc"
        await pilot.click("#apply")
        await pilot.pause()
        assert isinstance(app.screen, ChangeIndentModalScreen)


async def test_change_indent_modal_prepopulates_current_values():
    """ChangeIndentModalScreen pre-fills current indent type and size."""
    from textual.widgets import Input, Select

    app = _IndentTestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Apply custom 3-space indent first
        app.code_editor.action_change_indent()
        await pilot.pause()
        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Input).value = "3"
        await pilot.click("#apply")
        await pilot.pause()

        # Open modal again and check pre-populated values
        app.screen_stack[0].query_one(CodeEditor).action_change_indent()
        await pilot.pause()
        indent_type = app.screen.query_one("#indent_type", Select).value
        indent_size_val = app.screen.query_one("#indent_size", Input).value

    assert indent_type == "spaces"
    assert indent_size_val == "3"


async def test_change_indent_cmd_no_editor_notifies(workspace: Path):
    """No open file when command palette action triggered → error notification."""
    from tests.conftest import make_app

    tc_app = make_app(workspace)
    notified: list[str] = []

    async with tc_app.run_test() as pilot:
        original_notify = tc_app.notify

        def capture_notify(message, *, severity="information", **kwargs):
            notified.append(f"{severity}:{message}")
            return original_notify(message, severity=severity, **kwargs)

        tc_app.notify = capture_notify  # type: ignore
        tc_app.action_change_indent_cmd()
        await pilot.pause()

    assert any("error" in n for n in notified)
