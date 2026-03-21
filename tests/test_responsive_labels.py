"""Tests for responsive icon labels on sidebar tabs and search buttons."""

import pytest
from rich.cells import cell_len
from textual.widgets import Button

from tests.conftest import make_app
from textual_code.widgets.sidebar import (
    _BTN_ICON_ONLY_THRESHOLD,
    _TAB_ICON_ONLY_THRESHOLD,
    _TAB_LABELS,
)
from textual_code.widgets.workspace_search import _BTN_LABELS, _BTN_PADDING


@pytest.fixture
def ws(tmp_path):
    return tmp_path


async def _get_tab_labels(app):
    """Return current tab labels as dict {pane_id: label_text}."""
    tc = app.sidebar.tabbed_content
    return {pane_id: tc.get_tab(pane_id).label.plain for pane_id in _TAB_LABELS}


async def _get_button_labels(app):
    """Return (search_label, replace_label) from the workspace search pane."""
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
            assert app.sidebar is not None
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
            assert app.sidebar is not None
            app.sidebar.styles.width = _TAB_ICON_ONLY_THRESHOLD - 1
            await pilot.pause()
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
            assert app.sidebar is not None
            app.sidebar.styles.width = _BTN_ICON_ONLY_THRESHOLD
            await pilot.pause()
            await pilot.pause()
            search, replace = await _get_button_labels(app)
            assert "Search" in search
            assert "Replace All" in replace

    async def test_narrow_sidebar_shows_icon_only_buttons(self, ws):
        app = make_app(ws)
        async with app.run_test(size=(120, 40)) as pilot:
            assert app.sidebar is not None
            app.sidebar.styles.width = _BTN_ICON_ONLY_THRESHOLD - 1
            await pilot.pause()
            search, replace = await _get_button_labels(app)
            assert search.strip() in ("🔍",)
            assert replace.strip() in ("🔄",)

    async def test_full_labels_set_min_width(self, ws):
        """Wide sidebar sets min-width to match full label text length."""
        app = make_app(ws)
        async with app.run_test(size=(120, 40)) as pilot:
            assert app.sidebar is not None
            app.sidebar.styles.width = _BTN_ICON_ONLY_THRESHOLD
            await pilot.pause()
            await pilot.pause()
            assert app.sidebar is not None
            wsp = app.sidebar.workspace_search
            for btn_id, (full, _icon) in _BTN_LABELS.items():
                btn = wsp.query_one(f"#{btn_id}", Button)
                expected = cell_len(full) + _BTN_PADDING
                assert btn.styles.min_width is not None
                assert btn.styles.min_width.value == expected, (
                    f"{btn_id} min-width {expected} != {btn.styles.min_width}"
                )

    async def test_compact_labels_set_min_width(self, ws):
        """Narrow sidebar sets min-width to match icon-only label length."""
        app = make_app(ws)
        async with app.run_test(size=(120, 40)) as pilot:
            assert app.sidebar is not None
            app.sidebar.styles.width = _BTN_ICON_ONLY_THRESHOLD - 1
            await pilot.pause()
            assert app.sidebar is not None
            wsp = app.sidebar.workspace_search
            for btn_id, (_full, icon) in _BTN_LABELS.items():
                btn = wsp.query_one(f"#{btn_id}", Button)
                expected = cell_len(icon) + _BTN_PADDING
                assert btn.styles.min_width is not None
                assert btn.styles.min_width.value == expected, (
                    f"{btn_id} min-width {expected} != {btn.styles.min_width}"
                )

    async def test_initial_mount_sets_min_width(self, ws):
        """Icon-only min-width after initial mount (default sidebar < threshold)."""
        app = make_app(ws)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.sidebar is not None
            wsp = app.sidebar.workspace_search
            for btn_id, (_full, icon) in _BTN_LABELS.items():
                btn = wsp.query_one(f"#{btn_id}", Button)
                expected = cell_len(icon) + _BTN_PADDING
                assert btn.styles.min_width is not None, (
                    f"{btn_id} should have min-width set after mount"
                )
                assert btn.styles.min_width.value == expected, (
                    f"{btn_id} min-width {expected} != {btn.styles.min_width}"
                )
