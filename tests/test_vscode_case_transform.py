"""
VSCode case transformation tests ported from linesOperations.test.ts.

Source: src/vs/editor/contrib/linesOperations/test/browser/linesOperations.test.ts
Lines: 902-1178 ('toggle case' test block)

Our editor supports: uppercase, lowercase (via command palette).
Not yet supported: title case, snake case, camel case, kebab case, pascal case.

Behavioral difference from VSCode:
    VSCode: collapsed cursor (no selection) auto-selects the word under the
            cursor and transforms it.
    Ours:   collapsed cursor is a no-op (no word auto-select).
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_ta(app):
    """Return the MultiCursorTextArea from the active code editor."""
    return app.main_view.get_active_code_editor().editor


# ── Uppercase: VSCode assertions (lines 932-935, 957-960) ────────────────────


@pytest.mark.asyncio
async def test_uppercase_full_line(workspace: Path):
    """VSCode L932-935: select full line 'hello world' → 'HELLO WORLD'."""
    f = workspace / "case.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_uppercase()
        await pilot.pause()
        assert ta.document.get_line(0) == "HELLO WORLD"
        # Selection must be preserved (VSCode L935)
        assert ta.selection == Selection((0, 0), (0, 11))


@pytest.mark.asyncio
async def test_uppercase_unicode(workspace: Path):
    """VSCode L957-960: Unicode 'öçşğü' → 'ÖÇŞĞÜ'."""
    f = workspace / "unicode.txt"
    f.write_text("öçşğü\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 5))
        ta.action_transform_uppercase()
        await pilot.pause()
        assert ta.document.get_line(0) == "ÖÇŞĞÜ"
        assert ta.selection == Selection((0, 0), (0, 5))


# ── Lowercase: VSCode assertions (lines 937-940, 962-965) ────────────────────


@pytest.mark.asyncio
async def test_lowercase_full_line(workspace: Path):
    """VSCode L937-940: select 'HELLO WORLD' → 'hello world'."""
    f = workspace / "case.txt"
    f.write_text("HELLO WORLD\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_lowercase()
        await pilot.pause()
        assert ta.document.get_line(0) == "hello world"
        assert ta.selection == Selection((0, 0), (0, 11))


@pytest.mark.asyncio
async def test_lowercase_unicode(workspace: Path):
    """VSCode L962-965: Unicode 'ÖÇŞĞÜ' → 'öçşğü'."""
    f = workspace / "unicode.txt"
    f.write_text("ÖÇŞĞÜ\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 5))
        ta.action_transform_lowercase()
        await pilot.pause()
        assert ta.document.get_line(0) == "öçşğü"
        assert ta.selection == Selection((0, 0), (0, 5))


# ── Round-trip: VSCode L932-940 combined ─────────────────────────────────────


@pytest.mark.asyncio
async def test_uppercase_then_lowercase_round_trip(workspace: Path):
    """VSCode L932-940: 'hello world' → uppercase → lowercase returns original."""
    f = workspace / "case.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))

        ta.action_transform_uppercase()
        await pilot.pause()
        assert ta.document.get_line(0) == "HELLO WORLD"

        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_lowercase()
        await pilot.pause()
        assert ta.document.get_line(0) == "hello world"


# ── Idempotency ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_uppercase_idempotent(workspace: Path):
    """Applying uppercase to already-uppercase text is a no-op."""
    f = workspace / "case.txt"
    f.write_text("HELLO WORLD\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_uppercase()
        await pilot.pause()
        assert ta.document.get_line(0) == "HELLO WORLD"


@pytest.mark.asyncio
async def test_lowercase_idempotent(workspace: Path):
    """Applying lowercase to already-lowercase text is a no-op."""
    f = workspace / "case.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_lowercase()
        await pilot.pause()
        assert ta.document.get_line(0) == "hello world"


# ── Whitespace / empty: VSCode L1150-1178 ───────────────────────────────────


@pytest.mark.asyncio
async def test_uppercase_whitespace_only_selection(workspace: Path):
    """VSCode L1169-1172: selecting whitespace and transforming preserves it."""
    f = workspace / "space.txt"
    f.write_text("   \n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 3))
        ta.action_transform_uppercase()
        await pilot.pause()
        assert ta.document.get_line(0) == "   "


@pytest.mark.asyncio
async def test_uppercase_mixed_alphanumeric(workspace: Path):
    """Numbers and special characters are unaffected by uppercase."""
    f = workspace / "mixed.txt"
    f.write_text("test123!@#abc\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 13))
        ta.action_transform_uppercase()
        await pilot.pause()
        assert ta.document.get_line(0) == "TEST123!@#ABC"


# ── Collapsed cursor word transform: behavioral difference ──────────────────
# VSCode L942-950: collapsed cursor auto-selects the word and transforms it.
# Our editor: collapsed cursor is a no-op (documented difference).


@pytest.mark.asyncio
async def test_collapsed_cursor_uppercase_word_not_supported(workspace: Path):
    """VSCode L942-945: collapsed cursor at col 3 in 'hello world' uppercases
    'HELLO world'. Our editor does NOT auto-select the word — it is a no-op.

    VSCode behavior:
        cursor at (0,2), no selection → uppercase → 'HELLO world'
    Our behavior:
        cursor at (0,2), no selection → uppercase → 'hello world' (unchanged)
    """
    f = workspace / "case.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.cursor_location = (0, 2)
        ta.action_transform_uppercase()
        await pilot.pause()
        # Our editor: no-op (VSCode would produce 'HELLO world')
        assert ta.document.get_line(0) == "hello world"


@pytest.mark.asyncio
async def test_collapsed_cursor_lowercase_word_not_supported(workspace: Path):
    """VSCode L947-950: collapsed cursor at col 4 in 'HELLO world' lowercases
    'hello world'. Our editor does NOT auto-select the word — it is a no-op.

    VSCode behavior:
        cursor at (0,3), no selection → lowercase → 'hello world'
    Our behavior:
        cursor at (0,3), no selection → lowercase → 'HELLO world' (unchanged)
    """
    f = workspace / "case.txt"
    f.write_text("HELLO world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_ta(app)
        ta.cursor_location = (0, 3)
        ta.action_transform_lowercase()
        await pilot.pause()
        # Our editor: no-op (VSCode would produce 'hello world')
        assert ta.document.get_line(0) == "HELLO world"
