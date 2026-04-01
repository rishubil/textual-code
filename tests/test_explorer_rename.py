"""
Explorer rename (F2) integration tests.

Tests for the feature: rename files/folders with the F2 key
in the sidebar DirectoryTree, the editor, and command palette.
"""

from pathlib import Path

import pytest
from textual.widgets import Input

from tests.conftest import make_app
from textual_code.modals import RenameModalScreen
from textual_code.widgets.explorer import Explorer

# ── FileRenameRequested message standalone tests ─────────────────────────────


async def test_file_rename_requested_message_posts(
    workspace: Path, sample_py_file: Path
):
    """Posting FileRenameRequested directly → modal opens."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, RenameModalScreen)


# ── File rename ──────────────────────────────────────────────────────────────


async def test_rename_file_from_explorer(workspace: Path, sample_py_file: Path):
    """Rename confirm → file is renamed on disk."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert sample_py_file.exists()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, RenameModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = "renamed.py"
        await pilot.pause()
        await pilot.click("#rename")
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / "renamed.py").exists()


async def test_rename_file_cancel(workspace: Path, sample_py_file: Path):
    """Cancel → file is unchanged."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for modal screen push
        assert isinstance(app.screen, RenameModalScreen)

        await pilot.click("#cancel")
        await pilot.pause()

    assert sample_py_file.exists()


async def test_rename_open_file_updates_tab(workspace: Path, sample_py_file: Path):
    """Renaming an open file → editor.path and tab title update."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == sample_py_file

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, RenameModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = "renamed.py"
        await pilot.pause()
        await pilot.click("#rename")
        await pilot.pause()

        assert editor.path == workspace / "renamed.py"
        assert "renamed.py" in editor.title


async def test_rename_to_existing_shows_error(workspace: Path, sample_py_file: Path):
    """Renaming to an existing name → error notification, file unchanged."""
    existing = workspace / "existing.py"
    existing.write_text("existing\n")

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "existing.py"
        await pilot.pause()  # Windows: extra pause for input value change
        await pilot.click("#rename")
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for rename action error handling

    assert sample_py_file.exists()
    assert existing.read_text() == "existing\n"


async def test_rename_unchanged_name_noop(workspace: Path, sample_py_file: Path):
    """Same name → no filesystem change."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()

        # Don't change the input value — keep it as the original name
        await pilot.click("#rename")
        await pilot.pause()

    assert sample_py_file.exists()


async def test_rename_with_path_separator_shows_error(
    workspace: Path, sample_py_file: Path
):
    """Name with path separator → error notification, file unchanged."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "sub/dir.py"
        await pilot.pause()  # Windows: extra pause for input value change
        await pilot.click("#rename")
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for rename action error handling

    assert sample_py_file.exists()


async def test_rename_empty_name_noop(
    workspace: Path, sample_py_file: Path, monkeypatch: pytest.MonkeyPatch
):
    """Empty name → error notification, file unchanged.

    VSCode origin: validateFileName (For Create) — empty string returns error.
    """
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, RenameModalScreen)

        notify_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        monkeypatch.setattr(
            app, "notify", lambda *a, **kw: notify_calls.append((a, kw))
        )

        inp = app.screen.query_one(Input)
        inp.value = ""
        await pilot.click("#rename")
        await pilot.pause()

    assert sample_py_file.exists()
    assert any(
        kw.get("severity") == "error" and any("empty" in str(x) for x in a)
        for a, kw in notify_calls
    )


async def test_rename_whitespace_only_noop(
    workspace: Path, sample_py_file: Path, monkeypatch: pytest.MonkeyPatch
):
    """Whitespace-only name → error notification, file unchanged.

    VSCode origin: validateFileName (For Create) — whitespace returns error.
    """
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, RenameModalScreen)

        notify_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        monkeypatch.setattr(
            app, "notify", lambda *a, **kw: notify_calls.append((a, kw))
        )

        inp = app.screen.query_one(Input)
        inp.value = "   "
        await pilot.click("#rename")
        await pilot.pause()

    assert sample_py_file.exists()
    assert any(
        kw.get("severity") == "error" and any("empty" in str(x) for x in a)
        for a, kw in notify_calls
    )


async def test_rename_to_hidden_file(workspace: Path, sample_py_file: Path):
    """Rename to hidden file name (.hidden) → succeeds.

    VSCode origin: validateFileName (For Create) — '.foo' returns null (valid).
    """
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, RenameModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = ".hidden"
        await pilot.pause()
        await pilot.click("#rename")
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / ".hidden").exists()


async def test_rename_with_spaces_in_name(workspace: Path, sample_py_file: Path):
    """Name with spaces → succeeds.

    VSCode origin: validateFileName (For Create) — 'Read Me' returns null (valid).
    """
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, RenameModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = "Read Me.py"
        await pilot.pause()
        await pilot.click("#rename")
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / "Read Me.py").exists()


# ── Directory rename ─────────────────────────────────────────────────────────


async def test_rename_directory_from_explorer(workspace: Path):
    """Rename directory → old dir gone, new dir exists with contents."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    (subdir / "file.txt").write_text("content")

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=subdir)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, RenameModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = "newdir"
        await pilot.pause()
        await pilot.click("#rename")
        await pilot.pause()

    assert not subdir.exists()
    assert (workspace / "newdir").exists()
    assert (workspace / "newdir" / "file.txt").read_text() == "content"


async def test_rename_dir_updates_open_files(workspace: Path):
    """Renaming a directory updates all open tabs under that directory."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    child_file = subdir / "child.py"
    child_file.write_text("print('child')\n")

    app = make_app(workspace, open_file=child_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == child_file

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=subdir)
        )
        await pilot.pause()
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "newdir"
        await pilot.pause()
        await pilot.click("#rename")
        await pilot.pause()

        assert editor.path == workspace / "newdir" / "child.py"
        assert "child.py" in editor.title


# ── No cursor node ───────────────────────────────────────────────────────────


async def test_rename_no_cursor_no_modal(workspace: Path):
    """No cursor node → modal does not open."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        app.sidebar.explorer.action_rename_node()
        await pilot.pause()
        assert not isinstance(app.screen, RenameModalScreen)


# ── Unsaved changes preservation ─────────────────────────────────────────────


async def test_rename_file_preserves_unsaved_changes(
    workspace: Path, sample_py_file: Path
):
    """Renaming preserves unsaved (dirty) editor state."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Make the editor dirty
        editor.text = "modified content"
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "renamed.py"
        await pilot.pause()
        await pilot.click("#rename")
        await pilot.pause()

        # Path updated but content and dirty state preserved
        assert editor.path == workspace / "renamed.py"
        assert editor.text == "modified content"
        assert editor.text != editor.initial_text


# ── Editor F2 rename ─────────────────────────────────────────────────────────


async def test_rename_file_from_editor_f2(workspace: Path, sample_py_file: Path):
    """F2 in editor → rename modal opens, rename works."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_focus()
        await pilot.pause()

        await pilot.press("f2")
        await pilot.pause()
        assert isinstance(app.screen, RenameModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = "from_editor.py"
        await pilot.click("#rename")
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / "from_editor.py").exists()


async def test_rename_untitled_file_shows_error(workspace: Path):
    """F2 in editor with no path → error notification."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor()
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path is None
        editor.action_focus()
        await pilot.pause()

        await pilot.press("f2")
        await pilot.pause()
        assert not isinstance(app.screen, RenameModalScreen)


# ── Command palette rename ───────────────────────────────────────────────────


async def test_rename_via_command_palette(workspace: Path, sample_py_file: Path):
    """RenamePathWithPaletteRequested → modal → confirm → renamed."""
    from textual_code.app import TextualCode

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.RenamePathWithPaletteRequested(path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, RenameModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = "palette_renamed.py"
        await pilot.click("#rename")
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / "palette_renamed.py").exists()
