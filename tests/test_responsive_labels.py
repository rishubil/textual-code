"""Tests for responsive icon labels on sidebar tabs and search buttons."""

import pytest

from tests.conftest import make_app
from textual_code.widgets.sidebar import (
    _BTN_ICON_ONLY_THRESHOLD,
    _TAB_ICON_ONLY_THRESHOLD,
    _TAB_LABELS,
)


@pytest.fixture
def ws(tmp_path):
    return tmp_path


async def _get_tab_labels(app):
    """Return current tab labels as dict {pane_id: label_text}."""
    tc = app.sidebar.tabbed_content
    return {pane_id: tc.get_tab(pane_id).label.plain for pane_id in _TAB_LABELS}


async def _get_button_labels(app):
    """Return (search_label, replace_label) from the workspace search pane."""
    from textual.widgets import Button

    ws = app.sidebar.workspace_search
    return (
        ws.query_one("#ws-search", Button).label.plain,
        ws.query_one("#ws-replace-all", Button).label.plain,
    )


class TestTabLabelThreshold:
    """Tab labels switch between icon+text and icon-only at the threshold."""

    async def test_wide_sidebar_shows_full_labels(self, ws):
        app = make_app(ws)
        async with app.run_test(size=(120, 40)) as pilot:
            app.sidebar.styles.width = _TAB_ICON_ONLY_THRESHOLD
            await pilot.pause()
            labels = await _get_tab_labels(app)
            for pane_id, (full, _icon) in _TAB_LABELS.items():
                assert labels[pane_id] == full, (
                    f"{pane_id} should show full label at threshold"
                )

    async def test_narrow_sidebar_shows_icon_only(self, ws):
        app = make_app(ws)
        async with app.run_test(size=(120, 40)) as pilot:
            app.sidebar.styles.width = _TAB_ICON_ONLY_THRESHOLD - 1
            await pilot.pause()
            labels = await _get_tab_labels(app)
            for pane_id, (_full, icon) in _TAB_LABELS.items():
                assert labels[pane_id] == icon, (
                    f"{pane_id} should show icon-only below threshold"
                )


class TestButtonLabelThreshold:
    """Search buttons switch between icon+text and icon-only at the threshold."""

    async def test_wide_sidebar_shows_full_button_labels(self, ws):
        app = make_app(ws)
        async with app.run_test(size=(120, 40)) as pilot:
            app.sidebar.styles.width = _BTN_ICON_ONLY_THRESHOLD
            await pilot.pause()
            search, replace = await _get_button_labels(app)
            assert "Search" in search
            assert "Replace All" in replace

    async def test_narrow_sidebar_shows_icon_only_buttons(self, ws):
        app = make_app(ws)
        async with app.run_test(size=(120, 40)) as pilot:
            app.sidebar.styles.width = _BTN_ICON_ONLY_THRESHOLD - 1
            await pilot.pause()
            search, replace = await _get_button_labels(app)
            assert search.strip() in ("🔍",)
            assert replace.strip() in ("🔄",)
