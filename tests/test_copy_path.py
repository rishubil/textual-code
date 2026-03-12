"""
Tests for copy relative/absolute path commands.

Covers:
- action_copy_relative_path: copies relative path to clipboard
- action_copy_absolute_path: copies absolute path to clipboard
- Error cases: no file open, unsaved new file
- Fallback: file outside workspace uses absolute path
- Command palette entries
"""

from pathlib import Path

import pytest

from .conftest import make_app

# ---------------------------------------------------------------------------
# Group A: copy relative path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a01_copy_relative_path(workspace, sample_py_file):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        app.action_copy_relative_path()
        await pilot.pause()
        assert app.clipboard == "hello.py"


@pytest.mark.asyncio
async def test_a02_copy_absolute_path(workspace, sample_py_file):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        app.action_copy_absolute_path()
        await pilot.pause()
        assert app.clipboard == str(sample_py_file)


# ---------------------------------------------------------------------------
# Group B: error cases — no file / unsaved new file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_b01_copy_path_no_editor_open(workspace, monkeypatch):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        notify_calls = []
        monkeypatch.setattr(app, "notify", lambda *a, **kw: notify_calls.append(kw))
        app.action_copy_relative_path()
        await pilot.pause()
        assert any(kw.get("severity") == "error" for kw in notify_calls)


@pytest.mark.asyncio
async def test_b02_copy_path_unsaved_new_file(workspace, monkeypatch):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor()
        await pilot.pause()
        notify_calls = []
        monkeypatch.setattr(app, "notify", lambda *a, **kw: notify_calls.append(kw))
        app.action_copy_relative_path()
        await pilot.pause()
        assert any(kw.get("severity") == "error" for kw in notify_calls)


# ---------------------------------------------------------------------------
# Group C: file outside workspace falls back to absolute path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_c01_copy_relative_path_outside_workspace(workspace):
    import tempfile

    # Create file in a completely separate temp dir (outside workspace)
    with tempfile.TemporaryDirectory() as other_dir:
        outside_file = Path(other_dir) / "outside.py"
        outside_file.write_text("# outside\n")
        app = make_app(workspace, open_file=outside_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.action_copy_relative_path()
            await pilot.pause()
            # Should fall back to absolute path since file is outside workspace
            assert app.clipboard == str(outside_file)


# ---------------------------------------------------------------------------
# Group D: command palette entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_d01_copy_path_commands_in_system_commands(workspace):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))
        titles = [c.title for c in commands]
        assert "Copy relative path" in titles
        assert "Copy absolute path" in titles
