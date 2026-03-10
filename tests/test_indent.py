"""
들여쓰기 변환 기능 테스트.

단위 테스트: _convert_indentation 헬퍼 함수
통합 테스트: action_change_indent via ChangeIndentModalScreen
"""

from pathlib import Path

from textual.app import App, ComposeResult

from textual_code.widgets.code_editor import CodeEditor, _convert_indentation

# ── _convert_indentation 단위 테스트 ─────────────────────────────────────────


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
    """2-space indent를 같은 크기로 변환하면 그대로."""
    # _convert_indentation은 target type/size로 직접 정규화
    result = _convert_indentation("  hello", "spaces", 2)
    assert result == "  hello"


def test_multiline_all_converted():
    """여러 줄 모두 변환."""
    text = "\thello\n\tworld"
    result = _convert_indentation(text, "spaces", 4)
    assert result == "    hello\n    world"


def test_empty_line_preserved():
    """빈 줄은 그대로 유지."""
    text = "\thello\n\n\tworld"
    result = _convert_indentation(text, "spaces", 4)
    assert result == "    hello\n\n    world"


def test_no_indent_unchanged():
    """들여쓰기 없는 줄은 변화 없음."""
    assert _convert_indentation("hello", "spaces", 4) == "hello"
    assert _convert_indentation("hello", "tabs", 4) == "hello"


def test_already_tabs_to_tabs():
    """탭 → 탭: 동일 크기면 그대로."""
    assert _convert_indentation("\thello", "tabs", 4) == "\thello"


def test_already_spaces_to_spaces_same_size():
    """스페이스 → 스페이스 같은 크기: 변화 없음."""
    assert _convert_indentation("    hello", "spaces", 4) == "    hello"


def test_double_indent_to_spaces():
    """이중 탭 → 8 spaces."""
    assert _convert_indentation("\t\thello", "spaces", 4) == "        hello"


def test_spaces_to_tabs_size8():
    """8 spaces → 1 tab (size=8)."""
    assert _convert_indentation("        hello", "tabs", 8) == "\thello"


# ── 통합 테스트 ───────────────────────────────────────────────────────────────


class _IndentTestApp(App):
    """CodeEditor를 포함한 통합 테스트용 앱."""

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
    """Apply Spaces 4 → 텍스트가 스페이스 들여쓰기로 변환된다."""
    from textual.widgets import Select

    app = _IndentTestApp(text="\thello\n\tworld")
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_indent()
        await pilot.pause()

        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Select).value = 4
        await pilot.click("#apply")
        await pilot.pause()

        final_text = app.screen_stack[0].query_one(CodeEditor).text

    assert "    hello" in final_text
    assert "    world" in final_text


async def test_change_indent_modal_apply_tabs():
    """Apply Tabs → 텍스트가 탭 들여쓰기로 변환된다."""
    from textual.widgets import Select

    app = _IndentTestApp(text="    hello\n    world")
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_indent()
        await pilot.pause()

        app.screen.query_one("#indent_type", Select).value = "tabs"
        app.screen.query_one("#indent_size", Select).value = 4
        await pilot.click("#apply")
        await pilot.pause()

        final_text = app.screen_stack[0].query_one(CodeEditor).text

    assert "\thello" in final_text
    assert "\tworld" in final_text


async def test_change_indent_cancel_no_change():
    """Cancel → 텍스트 변경 없음."""
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
    """Apply 후 TextArea의 indent_type과 indent_width가 업데이트된다."""
    from textual.widgets import Select, TextArea

    app = _IndentTestApp(text="\thello")
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.code_editor

        editor.action_change_indent()
        await pilot.pause()

        app.screen.query_one("#indent_type", Select).value = "spaces"
        app.screen.query_one("#indent_size", Select).value = 2
        await pilot.click("#apply")
        await pilot.pause()

        code_editor = app.screen_stack[0].query_one(CodeEditor)
        textarea = code_editor.query_one(TextArea)
        indent_type = textarea.indent_type
        indent_width = textarea.indent_width

    assert indent_type == "spaces"
    assert indent_width == 2


async def test_change_indent_cmd_no_editor_notifies(workspace: Path):
    """열린 파일 없을 때 command palette action → notify error."""
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
