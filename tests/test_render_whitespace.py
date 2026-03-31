"""Tests for render whitespace feature (issue #59).

Groups:
  A — config layer (EDITOR_KEYS, DEFAULT_EDITOR_SETTINGS, load round-trip)
  B — app layer (default attribute)
  C — CodeEditor reactive + EditorState
  D — cycle action
  E — rendering logic (_inject_whitespace_rendering)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from textual_code.app import TextualCode
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    EDITOR_KEYS,
    load_editor_settings,
)

from .conftest import get_style_color_at, make_app

_SPACE_CHAR = "·"
_TAB_CHAR = "→"


def _find_whitespace_positions(
    strip, gutter_width: int, space_char: str = _SPACE_CHAR, tab_char: str = _TAB_CHAR
) -> dict[int, str]:
    """Return content-relative positions with whitespace markers.

    Returns {content_col: char} where char is space_char or tab_char.
    """
    from rich.segment import Segment

    positions: dict[int, str] = {}
    cell_pos = 0
    for seg in strip:
        text = seg.text if isinstance(seg, Segment) else str(seg)
        for ch in text:
            if cell_pos >= gutter_width:
                content_col = cell_pos - gutter_width
                if ch == space_char:
                    positions[content_col] = space_char
                elif ch == tab_char:
                    positions[content_col] = tab_char
            cell_pos += 1
    return positions


# ── Group A: config layer ────────────────────────────────────────────────────


class TestConfig:
    def test_a01_render_whitespace_in_editor_keys(self):
        assert "render_whitespace" in EDITOR_KEYS

    def test_a02_default_editor_settings_has_render_whitespace(self):
        assert DEFAULT_EDITOR_SETTINGS["render_whitespace"] == "none"

    @pytest.mark.parametrize("mode", ["none", "all", "boundary", "trailing"])
    def test_a03_load_settings_round_trip(self, tmp_path: Path, mode: str):
        cfg = tmp_path / "user.toml"
        cfg.write_text(f'[editor]\nrender_whitespace = "{mode}"\n')
        settings = load_editor_settings(tmp_path, user_config_path=cfg)
        assert settings["render_whitespace"] == mode


# ── Group B: app layer ───────────────────────────────────────────────────────


class TestApp:
    def test_b01_app_has_default_render_whitespace(self, tmp_path: Path):
        app = TextualCode(workspace_path=tmp_path, with_open_file=None)
        assert app.default_render_whitespace == "none"


# ── Group C: CodeEditor reactive + EditorState ───────────────────────────────


class TestCodeEditor:
    @pytest.mark.asyncio
    async def test_c01_code_editor_has_render_whitespace(self, workspace: Path):
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.main_view.action_open_code_editor()
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            assert editor.render_whitespace == "none"

    @pytest.mark.asyncio
    async def test_c02_watch_propagates_to_text_area(self, workspace: Path):
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.main_view.action_open_code_editor()
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "all"
            await pilot.pause()
            assert editor.editor._render_whitespace == "all"

    @pytest.mark.asyncio
    async def test_c03_editor_state_round_trip(
        self, workspace: Path, sample_py_file: Path
    ):
        app = make_app(workspace, light=True, open_file=sample_py_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "trailing"
            state = editor.capture_state()
            assert state.render_whitespace == "trailing"


# ── Group C2: on_mount propagation ────────────────────────────────────────────


class TestMountPropagation:
    @pytest.mark.asyncio
    async def test_c04_render_whitespace_applied_on_mount(self, workspace: Path):
        """render_whitespace must be propagated to MultiCursorTextArea on mount."""
        f = workspace / "mount.py"
        f.write_text("    code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            # Change to "all" and verify it reaches the text area
            editor.render_whitespace = "all"
            await pilot.pause()
            assert editor.editor._render_whitespace == "all"
            # Capture state, remove editor, and restore from state
            state = editor.capture_state()
            assert state.render_whitespace == "all"
            # Open a second file to trigger tab switch (lazy unmount)
            f2 = workspace / "other.py"
            f2.write_text("x\n")
            await app.main_view.action_open_code_editor(path=f2)
            await pilot.pause()
            # Switch back to the original tab
            tc = app.main_view.tabbed_content
            tc.active = state.pane_id
            await pilot.pause()
            await pilot.pause()  # Windows: extra pause for tab switch + remount
            restored = app.main_view.get_active_code_editor()
            assert restored is not None
            # The key assertion: text area must have the restored value
            assert restored.editor._render_whitespace == "all"


# ── Group D: cycle action + set render whitespace ────────────────────────────


class TestCycle:
    @pytest.mark.asyncio
    async def test_d01_cycle_through_all_modes(self, workspace: Path):
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.main_view.action_open_code_editor()
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            assert editor.render_whitespace == "none"
            editor.action_cycle_render_whitespace()
            await pilot.pause()
            assert editor.render_whitespace == "all"
            editor.action_cycle_render_whitespace()
            await pilot.pause()
            assert editor.render_whitespace == "boundary"
            editor.action_cycle_render_whitespace()
            await pilot.pause()
            assert editor.render_whitespace == "trailing"
            editor.action_cycle_render_whitespace()
            await pilot.pause()
            assert editor.render_whitespace == "none"

    @pytest.mark.asyncio
    async def test_d02_set_via_app_callback(self, workspace: Path):
        """Setting render whitespace via app callback updates editor."""
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.main_view.action_open_code_editor()
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            assert editor.render_whitespace == "none"
            # Simulate what the Provider callback does
            app._apply_render_whitespace("all")
            await pilot.pause()
            assert editor.render_whitespace == "all"

    @pytest.mark.asyncio
    async def test_d03_set_updates_app_default_and_settings(self, workspace: Path):
        """Setting render whitespace updates app default."""
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.main_view.action_open_code_editor()
            await pilot.pause()
            assert app.default_render_whitespace == "none"
            app._apply_render_whitespace("boundary")
            await pilot.pause()
            assert app.default_render_whitespace == "boundary"

    @pytest.mark.asyncio
    async def test_d04_set_no_editor_notifies_error(self, workspace: Path):
        """Setting render whitespace without an open file shows error."""
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            # No editor open
            app._apply_render_whitespace("all")
            await pilot.pause()
            # default should NOT change when no editor is open
            assert app.default_render_whitespace == "none"

    @pytest.mark.asyncio
    async def test_d05_set_all_modes(self, workspace: Path):
        """All 4 modes can be set via the app callback."""
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.main_view.action_open_code_editor()
            await pilot.pause()
            for mode in ("all", "boundary", "trailing", "none"):
                app._apply_render_whitespace(mode)
                await pilot.pause()
                editor = app.main_view.get_active_code_editor()
                assert editor is not None
                assert editor.render_whitespace == mode
                assert app.default_render_whitespace == mode


# ── Group E: rendering logic ─────────────────────────────────────────────────


class TestRendering:
    @pytest.mark.asyncio
    async def test_e01_no_markers_when_none(self, workspace: Path):
        """Mode "none" should not add any whitespace markers."""
        f = workspace / "spaces.py"
        f.write_text("    code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            # mode is "none" by default
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            assert _find_whitespace_positions(strip, gw) == {}

    @pytest.mark.asyncio
    async def test_e02_all_mode_spaces(self, workspace: Path):
        """Mode "all": spaces become middle dots."""
        f = workspace / "spaces.py"
        f.write_text("  x y\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "all"
            await pilot.pause()
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            positions = _find_whitespace_positions(strip, gw)
            # Spaces at col 0, 1 (leading), and col 3 (between x and y)
            assert positions.get(0) == _SPACE_CHAR
            assert positions.get(1) == _SPACE_CHAR
            assert positions.get(3) == _SPACE_CHAR

    @pytest.mark.asyncio
    async def test_e03_all_mode_tabs(self, workspace: Path):
        """Mode "all": tab start position gets arrow."""
        f = workspace / "tabs.py"
        f.write_text("\tcode\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "all"
            editor.show_indentation_guides = False
            await pilot.pause()
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            positions = _find_whitespace_positions(strip, gw)
            # Tab at col 0 should show arrow
            assert positions.get(0) == _TAB_CHAR

    @pytest.mark.asyncio
    async def test_e04_trailing_mode(self, workspace: Path):
        """Mode "trailing": only trailing whitespace is marked."""
        f = workspace / "trailing.py"
        f.write_text("  x  \n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "trailing"
            editor.show_indentation_guides = False
            await pilot.pause()
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            positions = _find_whitespace_positions(strip, gw)
            # Leading (col 0,1) should NOT be marked
            assert 0 not in positions
            assert 1 not in positions
            # Trailing (col 3,4): "  x  " → trailing starts at col 3
            assert positions.get(3) == _SPACE_CHAR
            assert positions.get(4) == _SPACE_CHAR

    @pytest.mark.asyncio
    async def test_e05_boundary_mode(self, workspace: Path):
        """Mode "boundary": leading + trailing marked, middle space untouched."""
        f = workspace / "boundary.py"
        f.write_text("  x y  \n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "boundary"
            editor.show_indentation_guides = False
            await pilot.pause()
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            positions = _find_whitespace_positions(strip, gw)
            # Leading: col 0, 1 → marked
            assert positions.get(0) == _SPACE_CHAR
            assert positions.get(1) == _SPACE_CHAR
            # Middle: col 3 (between x and y) → NOT marked
            assert 3 not in positions
            # Trailing: col 5, 6 → marked
            assert positions.get(5) == _SPACE_CHAR
            assert positions.get(6) == _SPACE_CHAR

    @pytest.mark.asyncio
    async def test_e06_interaction_with_indentation_guides(self, workspace: Path):
        """When both enabled, guides override whitespace dots at guide positions."""
        from tests.test_indentation_guides import _find_guide_positions

        f = workspace / "both.py"
        f.write_text("        code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "all"
            editor.show_indentation_guides = True
            await pilot.pause()
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            # Guides should be at col 0 and 4
            guides = _find_guide_positions(strip, gw)
            assert 0 in guides
            assert 4 in guides
            # Whitespace markers should be at non-guide positions
            ws = _find_whitespace_positions(strip, gw)
            # Guide positions should NOT also have whitespace markers
            assert 0 not in ws
            assert 4 not in ws
            # But other whitespace positions should have dots
            assert any(v == _SPACE_CHAR for v in ws.values())

    @pytest.mark.asyncio
    async def test_e07_empty_line(self, workspace: Path):
        """Empty line → no crash, no markers."""
        f = workspace / "empty.py"
        f.write_text("\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "all"
            await pilot.pause()
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            assert _find_whitespace_positions(strip, gw) == {}

    @pytest.mark.asyncio
    async def test_e08_no_trailing_whitespace(self, workspace: Path):
        """No trailing spaces → "trailing" mode shows nothing."""
        f = workspace / "clean.py"
        f.write_text("code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "trailing"
            await pilot.pause()
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            assert _find_whitespace_positions(strip, gw) == {}

    @pytest.mark.asyncio
    async def test_e09_mixed_tabs_spaces(self, workspace: Path):
        """Mixed tabs and spaces show both → and · correctly."""
        f = workspace / "mixed.py"
        f.write_text("\t    code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "all"
            editor.show_indentation_guides = False
            await pilot.pause()
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            positions = _find_whitespace_positions(strip, gw)
            # Tab expands to 4 spaces: col 0 = → (tab start)
            assert positions.get(0) == _TAB_CHAR
            # Following 4 spaces at col 4,5,6,7
            assert positions.get(4) == _SPACE_CHAR

    @pytest.mark.asyncio
    async def test_e10_horizontal_scroll_whitespace_alignment(self, workspace: Path):
        """Whitespace markers must stay aligned when scrolled horizontally.

        Regression test for #69: when word wrap is off and the editor is
        scrolled horizontally, whitespace markers appeared at wrong positions
        because _inject_whitespace_rendering used viewport-relative column
        indices to look up document-absolute whitespace positions.
        """
        f = workspace / "long.py"
        # 4 leading spaces + 'x' + 80 'a' chars + 4 trailing spaces
        content = "    x" + "a" * 80 + "    \n"
        f.write_text(content)
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "all"
            editor.show_indentation_guides = False
            ta = editor.editor
            ta.soft_wrap = False
            await pilot.pause()
            gw = ta.gutter_width

            # -- At scroll_x = 0: leading spaces at cols 0-3 should be marked
            strip_at_0 = ta._render_line(0)
            positions_at_0 = _find_whitespace_positions(strip_at_0, gw)
            assert positions_at_0.get(0) == _SPACE_CHAR, "leading space at col 0"
            assert positions_at_0.get(3) == _SPACE_CHAR, "leading space at col 3"

            # -- Scroll right by 10 columns
            ta.scroll_x = 10
            await pilot.pause()
            await pilot.pause()  # Windows: extra pause for scroll render update
            strip_at_10 = ta._render_line(0)
            positions_at_10 = _find_whitespace_positions(strip_at_10, gw)
            # Viewport cols 0-4 now map to doc cols 10-14 (all 'a' chars)
            for col in range(0, 5):
                assert col not in positions_at_10, (
                    f"viewport col {col} (doc col {col + 10}) should NOT have a "
                    f"marker — it's a non-space 'a' character, got {positions_at_10}"
                )

    @pytest.mark.asyncio
    async def test_e12_horizontal_scroll_trailing_visible(self, workspace: Path):
        """Trailing whitespace markers shift correctly when scrolled.

        Regression test for #69: verifies markers stay at correct relative
        positions after horizontal scroll.
        """
        f = workspace / "scroll_trailing.py"
        # 80 'a' chars + 4 trailing spaces
        content = "a" * 80 + "    \n"
        f.write_text(content)
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "trailing"
            editor.show_indentation_guides = False
            ta = editor.editor
            ta.soft_wrap = False
            await pilot.pause()
            gw = ta.gutter_width

            # At scroll_x=0: find trailing marker positions
            strip_before = ta._render_line(0)
            markers_before = _find_whitespace_positions(strip_before, gw)
            assert len(markers_before) == 4, (
                f"expected 4 trailing markers at scroll_x=0, got {markers_before}"
            )

            # Scroll right by a small amount (within max_scroll_x bounds)
            scroll_amount = 3
            ta.scroll_x = scroll_amount
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()  # Windows: extra pause for scroll render update
            strip_after = ta._render_line(0)
            markers_after = _find_whitespace_positions(strip_after, gw)

            # Should still have exactly 4 trailing markers
            assert len(markers_after) == 4, (
                f"expected 4 trailing markers at scroll_x={scroll_amount}, "
                f"got {markers_after}"
            )
            # Markers should shift left by scroll_amount
            before_positions = sorted(markers_before.keys())
            after_positions = sorted(markers_after.keys())
            for b, a in zip(before_positions, after_positions, strict=True):
                assert a == b - scroll_amount, (
                    f"expected position {b} to shift to {b - scroll_amount}, got {a}"
                )

    @pytest.mark.asyncio
    async def test_e11_all_whitespace_line(self, workspace: Path):
        """All-whitespace line → all modes render everything."""
        f = workspace / "allws.py"
        f.write_text("    \n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.show_indentation_guides = False
            ta = editor.editor
            gw = ta.gutter_width

            for mode in ("all", "boundary", "trailing"):
                editor.render_whitespace = mode
                await pilot.pause()
                strip = ta._render_line(0)
                positions = _find_whitespace_positions(strip, gw)
                assert len(positions) == 4, (
                    f"mode={mode}: expected 4 markers, got {positions}"
                )

    def test_e14_component_classes_defined(self):
        """MultiCursorTextArea must define whitespace component classes."""
        from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

        assert "text-area--whitespace" in MultiCursorTextArea.COMPONENT_CLASSES
        assert "text-area--whitespace-active" in MultiCursorTextArea.COMPONENT_CLASSES

    @pytest.mark.asyncio
    async def test_e15_overlay_fg_returns_color_object(self, workspace: Path):
        """_overlay_fg() must return a rich Color for whitespace feature."""
        from rich.color import Color

        f = workspace / "ws_color.py"
        f.write_text("    code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor
            result = ta._overlay_fg(0, feature="whitespace")
            assert isinstance(result, Color)

    @pytest.mark.asyncio
    async def test_e13_cursor_line_whitespace_has_distinct_fg(self, workspace: Path):
        """Whitespace marker fg on cursor line must differ from non-cursor line.

        Issue #106: the overlay color is too close to the cursor line background
        in many themes (e.g. monokai: overlay=#3E3E3E, cursor_bg=#3e3d32).
        The cursor line should use a higher-contrast overlay color.
        """
        f = workspace / "contrast.py"
        f.write_text("    x\n    y\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.render_whitespace = "all"
            editor.show_indentation_guides = False
            await pilot.pause()

            ta = editor.editor
            # Focus the textarea so cursor_line_style is applied
            ta.focus()
            await pilot.pause()
            # Cursor is on line 0 by default
            assert ta.cursor_location[0] == 0

            gw = ta.gutter_width

            # Render cursor line (y=0) and non-cursor line (y=1)
            strip_cursor = ta._render_line(0)
            strip_other = ta._render_line(1)

            # Both lines have a whitespace marker at content col 0
            assert _find_whitespace_positions(strip_cursor, gw)
            assert _find_whitespace_positions(strip_other, gw)

            # The fg color of whitespace markers on the cursor line
            # should differ from non-cursor lines for better contrast.
            fg_cursor = get_style_color_at(strip_cursor, gw, 0)
            fg_other = get_style_color_at(strip_other, gw, 0)
            assert fg_cursor is not None
            assert fg_other is not None
            assert fg_cursor != fg_other, (
                f"Whitespace marker fg should differ on cursor line "
                f"(got {fg_cursor} on both lines)"
            )
