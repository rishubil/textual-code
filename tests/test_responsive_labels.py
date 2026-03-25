"""Tests for responsive icon labels on sidebar tabs and search buttons."""

import pytest
from rich.cells import cell_len
from textual.css.query import NoMatches
from textual.widgets import Button

from tests.conftest import make_app
from textual_code.widgets.find_replace_bar import (
    _BTN_LABELS as _FR_BTN_LABELS,
)
from textual_code.widgets.find_replace_bar import (
    _BTN_MIN_WIDTHS as _FR_BTN_MIN_WIDTHS,
)
from textual_code.widgets.find_replace_bar import (
    _COMPACT_THRESHOLD as _FR_COMPACT_THRESHOLD,
)
from textual_code.widgets.find_replace_bar import (
    FindReplaceBar,
)
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


# ── Find/Replace bar responsive labels ───────────────────────────────────────


async def _open_find_bar(pilot, app):
    """Open find bar via Ctrl+F and return the FindReplaceBar widget."""
    await pilot.pause()
    editor = app.main_view.get_active_code_editor()
    assert editor is not None
    await pilot.press("ctrl+f")
    await pilot.pause()
    return editor.query_one(FindReplaceBar)


class TestFindReplaceBarLabelThreshold:
    """Find/replace bar buttons switch between icon+text and icon-only."""

    async def test_narrow_bar_shows_compact_labels(self, ws):
        """Below threshold, find/replace bar shows compact labels."""
        f = ws / "test.txt"
        f.write_text("hello\n")
        app = make_app(ws, open_file=f, light=True)
        async with app.run_test(size=(80, 30)) as pilot:
            bar = await _open_find_bar(pilot, app)
            for btn_id, (_full, icon) in _FR_BTN_LABELS.items():
                try:
                    btn = bar.query_one(f"#{btn_id}", Button)
                except NoMatches:
                    continue  # replace row buttons not mounted in find mode
                assert btn.label.plain.strip() == icon, (
                    f"{btn_id} should show icon-only at size 80"
                )

    async def test_wide_bar_shows_full_labels(self, ws):
        """At or above threshold, find/replace bar shows full labels."""
        f = ws / "test.txt"
        f.write_text("hello\n")
        app = make_app(ws, open_file=f, light=True)
        async with app.run_test(size=(_FR_COMPACT_THRESHOLD + 30, 30)) as pilot:
            bar = await _open_find_bar(pilot, app)
            for btn_id, (full, _icon) in _FR_BTN_LABELS.items():
                try:
                    btn = bar.query_one(f"#{btn_id}", Button)
                except NoMatches:
                    continue  # replace row buttons not mounted in find mode
                assert btn.label.plain.strip() == full, (
                    f"{btn_id} should show full label at wide size"
                )

    async def test_compact_labels_set_min_width(self, ws):
        """Compact mode sets min-width to match icon-only label length."""
        f = ws / "test.txt"
        f.write_text("hello\n")
        app = make_app(ws, open_file=f, light=True)
        async with app.run_test(size=(80, 30)) as pilot:
            bar = await _open_find_bar(pilot, app)
            for btn_id in _FR_BTN_LABELS:
                try:
                    btn = bar.query_one(f"#{btn_id}", Button)
                except NoMatches:
                    continue
                expected = _FR_BTN_MIN_WIDTHS[btn_id][1]
                assert btn.styles.min_width is not None
                assert btn.styles.min_width.value == expected, (
                    f"{btn_id} min-width {expected} != {btn.styles.min_width}"
                )

    async def test_tooltips_are_set(self, ws):
        """All buttons should have tooltips after mount."""
        f = ws / "test.txt"
        f.write_text("hello\n")
        app = make_app(ws, open_file=f, light=True)
        async with app.run_test(size=(80, 30)) as pilot:
            bar = await _open_find_bar(pilot, app)
            prev_btn = bar.query_one("#prev_match", Button)
            assert prev_btn.tooltip is not None
            assert "Previous" in str(prev_btn.tooltip)
            next_btn = bar.query_one("#next_match", Button)
            assert next_btn.tooltip is not None
            assert "Next" in str(next_btn.tooltip)
            close_btn = bar.query_one("#close_btn", Button)
            assert close_btn.tooltip is not None
            assert "Close" in str(close_btn.tooltip)
