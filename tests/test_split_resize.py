"""
Tests for the split view resize from command palette feature.

Covers:
- _parse_split_resize helper (pure function)
- SplitResizeModalScreen modal dialog
- action_resize_split integration
"""

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Label

from tests.conftest import make_app
from textual_code.app import _parse_split_resize
from textual_code.modals import SplitResizeModalResult, SplitResizeModalScreen
from textual_code.widgets.split_tree import all_leaves

# ── _parse_split_resize ───────────────────────────────────────────────────────


def test_parse_absolute_value():
    result = _parse_split_resize("50", current_width=40, total_width=100)
    assert result == 50


def test_parse_relative_plus():
    result = _parse_split_resize("+10", current_width=40, total_width=100)
    assert result == 50


def test_parse_relative_minus():
    result = _parse_split_resize("-5", current_width=40, total_width=100)
    assert result == 35


def test_parse_percentage():
    result = _parse_split_resize("40%", current_width=40, total_width=100)
    assert result == "40%"


def test_parse_invalid_string():
    result = _parse_split_resize("abc", current_width=40, total_width=100)
    assert result is None


def test_parse_empty_string():
    result = _parse_split_resize("", current_width=40, total_width=100)
    assert result is None


def test_parse_below_min_absolute():
    # Below minimum of 10
    result = _parse_split_resize("5", current_width=40, total_width=100)
    assert result is None


def test_parse_above_max_absolute():
    # Above max (total - 10 = 90)
    result = _parse_split_resize("95", current_width=40, total_width=100)
    assert result is None


def test_parse_relative_below_min():
    # 40 - 35 = 5, which is < 10
    result = _parse_split_resize("-35", current_width=40, total_width=100)
    assert result is None


def test_parse_relative_above_max():
    # 40 + 55 = 95, which is > 90
    result = _parse_split_resize("+55", current_width=40, total_width=100)
    assert result is None


def test_parse_percentage_below_min():
    result = _parse_split_resize("9%", current_width=40, total_width=100)
    assert result is None


def test_parse_percentage_above_max():
    result = _parse_split_resize("91%", current_width=40, total_width=100)
    assert result is None


def test_parse_percentage_at_min_boundary():
    result = _parse_split_resize("10%", current_width=40, total_width=100)
    assert result == "10%"


def test_parse_percentage_at_max_boundary():
    result = _parse_split_resize("90%", current_width=40, total_width=100)
    assert result == "90%"


def test_parse_absolute_at_min_boundary():
    result = _parse_split_resize("10", current_width=40, total_width=100)
    assert result == 10


def test_parse_absolute_at_max_boundary():
    # max = total_width - 10 = 90
    result = _parse_split_resize("90", current_width=40, total_width=100)
    assert result == 90


def test_parse_whitespace_trimmed():
    result = _parse_split_resize("  50  ", current_width=40, total_width=100)
    assert result == 50


# ── SplitResizeModalScreen ────────────────────────────────────────────────────


class _SplitResizeApp(App):
    def __init__(self):
        super().__init__()
        self.result: SplitResizeModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(SplitResizeModalScreen(), self._on_result)

    def _on_result(self, result: SplitResizeModalResult | None) -> None:
        self.result = result


async def test_split_resize_modal_cancel_returns_cancelled():
    app = _SplitResizeApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.value is None


async def test_split_resize_modal_submit_returns_value():
    app = _SplitResizeApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("5", "0")
        await pilot.click("#submit")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.value == "50"


async def test_split_resize_modal_enter_submits():
    app = _SplitResizeApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("4", "0", "%")
        await pilot.press("enter")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.value == "40%"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def py_file(workspace: Path) -> Path:
    f = workspace / "main.py"
    f.write_text("print('hello')\n")
    return f


# ── action_resize_split integration ───────────────────────────────────────


async def test_resize_split_absolute_changes_width(workspace, py_file):
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        app.action_resize_split()
        await pilot.pause()

        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("4", "0")
        await pilot.click("#submit")
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        first_dtc = app.main_view.query_one(f"#{leaves[0].leaf_id}")
        width = first_dtc.styles.width
        assert width is not None
        assert width.value == 40


async def test_resize_split_relative_plus_changes_width(workspace, py_file):
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        first_dtc = app.main_view.query_one(f"#{leaves[0].leaf_id}")
        initial_width = first_dtc.size.width

        app.action_resize_split()
        await pilot.pause()

        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("+", "5")
        await pilot.click("#submit")
        await pilot.pause()

        width = first_dtc.styles.width
        assert width is not None
        assert width.value == initial_width + 5


async def test_resize_split_percentage_changes_width(workspace, py_file):
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        app.action_resize_split()
        await pilot.pause()

        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("4", "0", "%")
        await pilot.click("#submit")
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        first_dtc = app.main_view.query_one(f"#{leaves[0].leaf_id}")
        width = first_dtc.styles.width
        assert width is not None
        assert width.value == 40.0


async def test_resize_split_invalid_shows_error(workspace, py_file):
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        first_dtc = app.main_view.query_one(f"#{leaves[0].leaf_id}")
        initial_width = first_dtc.size.width

        app.action_resize_split()
        await pilot.pause()

        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("a", "b", "c")
        await pilot.click("#submit")
        await pilot.pause()

        # Width should be unchanged
        assert first_dtc.size.width == initial_width


async def test_resize_split_cancel_keeps_width(workspace, py_file):
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        first_dtc = app.main_view.query_one(f"#{leaves[0].leaf_id}")
        initial_width = first_dtc.size.width

        app.action_resize_split()
        await pilot.pause()

        await pilot.click("#cancel")
        await pilot.pause()

        # Width should be unchanged
        assert first_dtc.size.width == initial_width


async def test_resize_split_no_split_visible_shows_error(workspace, py_file):
    """Resize split command is a no-op (shows error) when split is not visible."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert app.main_view._split_visible is False

        app.action_resize_split()
        await pilot.pause()

        # No modal pushed — still on the main screen only
        assert len(app.screen_stack) == 1
