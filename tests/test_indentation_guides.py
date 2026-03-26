"""Tests for indentation guides feature (issue #40).

Groups:
  A — config layer (EDITOR_KEYS, DEFAULT_EDITOR_SETTINGS, load round-trip)
  B — app layer (default attribute, _build_editor_settings)
  C — CodeEditor reactive + EditorState
  D — toggle action + app→editor delegation
  E — rendering logic (_inject_indentation_guides)
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

# ── Group A: config layer ────────────────────────────────────────────────────


class TestConfig:
    def test_a01_show_indentation_guides_in_editor_keys(self):
        assert "show_indentation_guides" in EDITOR_KEYS

    def test_a02_default_editor_settings_has_show_indentation_guides(self):
        assert DEFAULT_EDITOR_SETTINGS["show_indentation_guides"] is True

    def test_a03_load_settings_round_trip(self, tmp_path: Path):
        cfg = tmp_path / "user.toml"
        cfg.write_text("[editor]\nshow_indentation_guides = false\n")
        settings = load_editor_settings(tmp_path, user_config_path=cfg)
        assert settings["show_indentation_guides"] is False


# ── Group B: app layer ───────────────────────────────────────────────────────


class TestApp:
    def test_b01_app_has_default_show_indentation_guides(self, tmp_path: Path):
        app = TextualCode(workspace_path=tmp_path, with_open_file=None)
        assert app.default_show_indentation_guides is True

    def test_b02_build_editor_settings_includes_key(self, tmp_path: Path):
        app = TextualCode(workspace_path=tmp_path, with_open_file=None)
        settings = app._build_editor_settings()
        assert "show_indentation_guides" in settings
        assert settings["show_indentation_guides"] is True


# ── Group C: CodeEditor reactive + EditorState ───────────────────────────────


class TestCodeEditor:
    @pytest.mark.asyncio
    async def test_c01_code_editor_has_show_indentation_guides(self, workspace: Path):
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.main_view.action_open_code_editor()
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            assert editor.show_indentation_guides is True

    @pytest.mark.asyncio
    async def test_c02_watch_propagates_to_text_area(self, workspace: Path):
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.main_view.action_open_code_editor()
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.show_indentation_guides = False
            await pilot.pause()
            assert editor.editor._show_indentation_guides is False

    @pytest.mark.asyncio
    async def test_c03_editor_state_round_trip(
        self, workspace: Path, sample_py_file: Path
    ):
        app = make_app(workspace, light=True, open_file=sample_py_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.show_indentation_guides = False
            state = editor.capture_state()
            assert state.show_indentation_guides is False


# ── Group D: toggle action + app→editor delegation ──────────────────────────


class TestToggle:
    @pytest.mark.asyncio
    async def test_d01_toggle_flips_value(self, workspace: Path):
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.main_view.action_open_code_editor()
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            assert editor.show_indentation_guides is True
            editor.action_toggle_indentation_guides()
            await pilot.pause()
            assert editor.show_indentation_guides is False
            editor.action_toggle_indentation_guides()
            await pilot.pause()
            assert editor.show_indentation_guides is True

    @pytest.mark.asyncio
    async def test_d02_toggle_via_app_cmd(self, workspace: Path):
        app = make_app(workspace, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.main_view.action_open_code_editor()
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            assert editor.show_indentation_guides is True
            app.action_toggle_indentation_guides()
            await pilot.pause()
            assert editor.show_indentation_guides is False


# ── Helpers ──────────────────────────────────────────────────────────────────

_GUIDE_CHAR = "│"


def _find_guide_positions(
    strip, gutter_width: int, guide_char: str = _GUIDE_CHAR
) -> list[int]:
    """Walk strip segments and return content-relative positions with *guide_char*."""
    from rich.segment import Segment

    positions: list[int] = []
    cell_pos = 0
    for seg in strip:
        text = seg.text if isinstance(seg, Segment) else str(seg)
        for ch in text:
            if cell_pos >= gutter_width and ch == guide_char:
                positions.append(cell_pos - gutter_width)
            cell_pos += 1
    return positions


# ── Group E: rendering logic ─────────────────────────────────────────────────


class TestRendering:
    @pytest.mark.asyncio
    async def test_e01_no_guides_when_no_indent(self, workspace: Path):
        """Unindented code should have no guide characters."""
        f = workspace / "no_indent.py"
        f.write_text("x = 1\ny = 2\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            assert _find_guide_positions(strip, gw) == []

    @pytest.mark.asyncio
    async def test_e02_first_level_guide(self, workspace: Path):
        """4 spaces indent (width=4) → guide at content col 0."""
        f = workspace / "indent4.py"
        f.write_text("    code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            guides = _find_guide_positions(strip, gw)
            assert guides == [0]

    @pytest.mark.asyncio
    async def test_e03_guides_at_correct_positions(self, workspace: Path):
        """8 spaces indent (width=4) → guides at content col 0 and 4."""
        f = workspace / "indent8.py"
        f.write_text("        code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            guides = _find_guide_positions(strip, gw)
            assert guides == [0, 4]

    @pytest.mark.asyncio
    async def test_e04_multi_level_indent(self, workspace: Path):
        """12 spaces indent → guides at col 0, 4, and 8."""
        f = workspace / "indent12.py"
        f.write_text("            code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            guides = _find_guide_positions(strip, gw)
            assert guides == [0, 4, 8]

    @pytest.mark.asyncio
    async def test_e05_no_guides_when_disabled(self, workspace: Path):
        """Disabled → no guides even on indented lines."""
        f = workspace / "disabled.py"
        f.write_text("        code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.show_indentation_guides = False
            await pilot.pause()
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            assert _find_guide_positions(strip, gw) == []

    @pytest.mark.asyncio
    async def test_e06_empty_line_no_guides(self, workspace: Path):
        """Empty line → no crash, no guides."""
        f = workspace / "empty.py"
        f.write_text("\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            assert _find_guide_positions(strip, gw) == []

    @pytest.mark.asyncio
    async def test_e07_indent_shorter_than_width_no_guides(self, workspace: Path):
        """2 spaces (width=4) → no guides."""
        f = workspace / "short.py"
        f.write_text("  code\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            assert _find_guide_positions(strip, gw) == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "text, expected_guide_cols",
        [
            ("\tcode\n", [0]),  # 1 tab = 4 spaces → guide at col 0
            ("\t\tcode\n", [0, 4]),  # 2 tabs = 8 spaces → guides at col 0, 4
            ("\t    code\n", [0, 4]),  # tab + 4 spaces = 8 → guides at col 0, 4
        ],
        ids=["one_tab", "two_tabs", "mixed_tab_spaces"],
    )
    async def test_e08_tab_expanded_correctly(
        self, workspace: Path, text: str, expected_guide_cols: list[int]
    ):
        f = workspace / "tabs.py"
        f.write_text(text)
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor
            gw = ta.gutter_width
            strip = ta._render_line(0)
            assert _find_guide_positions(strip, gw) == expected_guide_cols

    @pytest.mark.asyncio
    async def test_e09_horizontal_scroll_guides_alignment(self, workspace: Path):
        """Indentation guides must stay aligned when scrolled horizontally.

        Regression test for #69: same offset bug as whitespace rendering.
        """
        f = workspace / "long_indent.py"
        # 8 leading spaces + 'x' + 80 'a' chars
        content = "        x" + "a" * 80 + "\n"
        f.write_text(content)
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor
            ta.soft_wrap = False
            await pilot.pause()
            gw = ta.gutter_width

            # At scroll_x=0: guides at doc cols 0 and 4
            strip_at_0 = ta._render_line(0)
            guides_at_0 = _find_guide_positions(strip_at_0, gw)
            assert 0 in guides_at_0
            assert 4 in guides_at_0

            # Scroll right by 10 — all guide positions (0, 4) are off-screen
            ta.scroll_x = 10
            await pilot.pause()
            strip_at_10 = ta._render_line(0)
            guides_at_10 = _find_guide_positions(strip_at_10, gw)
            assert guides_at_10 == [], (
                f"No guides expected after scrolling past indent region, "
                f"got {guides_at_10}"
            )

    @pytest.mark.asyncio
    async def test_e10_cursor_line_guides_have_distinct_fg(self, workspace: Path):
        """Guide fg on cursor line must differ from non-cursor line.

        Issue #106: the overlay color (#3E3E3E) is too close to cursor line
        background (#3e3d32 for monokai), making guides invisible.
        """
        f = workspace / "guide_contrast.py"
        f.write_text("        x\n        y\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            editor.show_indentation_guides = True
            await pilot.pause()

            ta = editor.editor
            ta.focus()
            await pilot.pause()
            assert ta.cursor_location[0] == 0

            gw = ta.gutter_width

            strip_cursor = ta._render_line(0)
            strip_other = ta._render_line(1)

            assert _find_guide_positions(strip_cursor, gw)
            assert _find_guide_positions(strip_other, gw)

            fg_cursor = get_style_color_at(strip_cursor, gw, 0)
            fg_other = get_style_color_at(strip_other, gw, 0)
            assert fg_cursor is not None
            assert fg_other is not None
            assert fg_cursor != fg_other, (
                f"Guide fg should differ on cursor line (got {fg_cursor} on both lines)"
            )
