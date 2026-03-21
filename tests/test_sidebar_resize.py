"""
Tests for the sidebar resize feature.

Covers:
- _parse_sidebar_resize helper (pure function)
- SidebarResizeModalScreen modal dialog
- action_resize_sidebar_cmd integration
"""

from textual.app import App, ComposeResult
from textual.widgets import Label

from tests.conftest import make_app
from textual_code.app import _parse_sidebar_resize
from textual_code.modals import SidebarResizeModalResult, SidebarResizeModalScreen

# ── _parse_sidebar_resize ─────────────────────────────────────────────────────


def test_parse_absolute_value():
    result = _parse_sidebar_resize("30", current_width=20, max_width=100)
    assert result == 30


def test_parse_relative_plus():
    result = _parse_sidebar_resize("+5", current_width=20, max_width=100)
    assert result == 25


def test_parse_relative_minus():
    result = _parse_sidebar_resize("-3", current_width=20, max_width=100)
    assert result == 17


def test_parse_percentage():
    result = _parse_sidebar_resize("30%", current_width=20, max_width=100)
    assert result == "30%"


def test_parse_invalid_string():
    result = _parse_sidebar_resize("abc", current_width=20, max_width=100)
    assert result is None


def test_parse_empty_string():
    result = _parse_sidebar_resize("", current_width=20, max_width=100)
    assert result is None


def test_parse_below_min_absolute():
    # Below minimum of 5
    result = _parse_sidebar_resize("3", current_width=20, max_width=100)
    assert result is None


def test_parse_above_max_absolute():
    # Above max_width
    result = _parse_sidebar_resize("200", current_width=20, max_width=100)
    assert result is None


def test_parse_relative_results_below_min():
    # current=6, -5 = 1 which is below min 5
    result = _parse_sidebar_resize("-5", current_width=6, max_width=100)
    assert result is None


def test_parse_relative_results_above_max():
    # current=90, +20 = 110 which is above max 100
    result = _parse_sidebar_resize("+20", current_width=90, max_width=100)
    assert result is None


def test_parse_percentage_below_min():
    # 0% is below 1%
    result = _parse_sidebar_resize("0%", current_width=20, max_width=100)
    assert result is None


def test_parse_percentage_above_max():
    # 91% is above 90%
    result = _parse_sidebar_resize("91%", current_width=20, max_width=100)
    assert result is None


def test_parse_percentage_at_min_boundary():
    result = _parse_sidebar_resize("1%", current_width=20, max_width=100)
    assert result == "1%"


def test_parse_percentage_at_max_boundary():
    result = _parse_sidebar_resize("90%", current_width=20, max_width=100)
    assert result == "90%"


def test_parse_absolute_at_min_boundary():
    result = _parse_sidebar_resize("5", current_width=20, max_width=100)
    assert result == 5


def test_parse_absolute_at_max_boundary():
    result = _parse_sidebar_resize("100", current_width=20, max_width=100)
    assert result == 100


# ── SidebarResizeModalScreen ──────────────────────────────────────────────────


class _SidebarResizeApp(App):
    def __init__(self):
        super().__init__()
        self.result: SidebarResizeModalResult | None = None

    def compose(self) -> ComposeResult:
        yield Label("test")

    def on_mount(self) -> None:
        self.push_screen(SidebarResizeModalScreen(), self._on_result)

    def _on_result(self, result: SidebarResizeModalResult | None) -> None:
        self.result = result


async def test_sidebar_resize_modal_cancel_returns_cancelled():
    app = _SidebarResizeApp()
    async with app.run_test() as pilot:
        await pilot.click("#cancel")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is True
    assert app.result.value is None


async def test_sidebar_resize_modal_submit_returns_value():
    app = _SidebarResizeApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("3", "0")
        await pilot.click("#submit")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.value == "30"


async def test_sidebar_resize_modal_enter_submits():
    app = _SidebarResizeApp()
    async with app.run_test() as pilot:
        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("2", "5", "%")
        await pilot.press("enter")
        await pilot.pause()

    assert app.result is not None
    assert app.result.is_cancelled is False
    assert app.result.value == "25%"


# ── action_resize_sidebar_cmd integration ─────────────────────────────────────


async def test_sidebar_resize_absolute_changes_width(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        app.action_resize_sidebar_cmd()
        await pilot.pause()

        # Type absolute value and submit
        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("3", "0")
        await pilot.click("#submit")
        await pilot.pause()

        # sidebar width should be set to 30
        assert app.sidebar is not None
        assert app.sidebar.styles.width is not None
        assert app.sidebar.styles.width.value == 30


async def test_sidebar_resize_relative_plus_changes_width(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        initial_width = app.sidebar.size.width

        app.action_resize_sidebar_cmd()
        await pilot.pause()

        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("+", "5")
        await pilot.click("#submit")
        await pilot.pause()

        assert app.sidebar.styles.width is not None
        assert app.sidebar.styles.width.value == initial_width + 5


async def test_sidebar_resize_relative_minus_changes_width(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        initial_width = app.sidebar.size.width

        app.action_resize_sidebar_cmd()
        await pilot.pause()

        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("-", "3")
        await pilot.click("#submit")
        await pilot.pause()

        assert app.sidebar.styles.width is not None
        assert app.sidebar.styles.width.value == initial_width - 3


async def test_sidebar_resize_percentage_changes_width(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()

        app.action_resize_sidebar_cmd()
        await pilot.pause()

        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("3", "0", "%")
        await pilot.click("#submit")
        await pilot.pause()

        # Width should be set as percentage (numeric value = 30)
        assert app.sidebar is not None
        width = app.sidebar.styles.width
        assert width is not None
        assert width.value == 30.0
        # The sidebar should render at approximately 30% of 120 = 36 cells
        assert 30 <= app.sidebar.size.width <= 40


async def test_sidebar_resize_invalid_shows_error_and_keeps_width(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        initial_width = app.sidebar.size.width

        app.action_resize_sidebar_cmd()
        await pilot.pause()

        input_widget = app.screen.query_one("#value")
        await pilot.click(input_widget)
        await pilot.press("a", "b", "c")
        await pilot.click("#submit")
        await pilot.pause()

        # Width should be unchanged
        assert app.sidebar.size.width == initial_width


async def test_sidebar_resize_cancel_keeps_width(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        initial_width = app.sidebar.size.width

        app.action_resize_sidebar_cmd()
        await pilot.pause()

        await pilot.click("#cancel")
        await pilot.pause()

        # Width should be unchanged
        assert app.sidebar.size.width == initial_width
