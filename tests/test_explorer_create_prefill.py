"""
Explorer create file/directory pre-fill integration tests.

Tests that creating a file or directory from the explorer sidebar
pre-fills the command palette input with the selected folder's relative path.
"""

from pathlib import Path

from textual.command import CommandInput, CommandPalette

from tests.conftest import make_app

# ── _get_selected_dir_relative unit tests ────────────────────────────────────


async def test_selected_dir_relative_for_directory(workspace: Path):
    """When a directory is selected, returns its relative path with trailing '/'."""
    subdir = workspace / "src"
    subdir.mkdir()
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        # Move cursor down to find the "src" directory node
        tree = explorer.directory_tree
        for node in tree.root.children:
            if node.data and node.data.path == subdir:
                tree.move_cursor(node)
                break
        await pilot.pause()
        assert explorer._get_selected_dir_relative() == "src/"


async def test_selected_dir_relative_for_file(workspace: Path):
    """When a file is selected, returns its parent directory with trailing '/'."""
    subdir = workspace / "src"
    subdir.mkdir()
    pyfile = subdir / "main.py"
    pyfile.write_text("# main\n")
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        tree = explorer.directory_tree
        # Expand src dir and find main.py
        for node in tree.root.children:
            if node.data and node.data.path == subdir:
                node.expand()
                await pilot.pause()
                for child in node.children:
                    if child.data and child.data.path == pyfile:
                        tree.move_cursor(child)
                        break
                break
        await pilot.pause()
        assert explorer._get_selected_dir_relative() == "src/"


async def test_selected_dir_relative_for_root(workspace: Path):
    """When workspace root is selected (or equivalent), returns empty string."""
    (workspace / "hello.py").write_text("# hello\n")
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        # cursor_node at root level file should give parent = workspace root → ""
        tree = explorer.directory_tree
        for node in tree.root.children:
            if node.data and node.data.path == workspace / "hello.py":
                tree.move_cursor(node)
                break
        await pilot.pause()
        # File in root → parent is workspace → should return ""
        assert explorer._get_selected_dir_relative() == ""


async def test_selected_dir_relative_no_selection(workspace: Path):
    """When no node is selected, returns empty string."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        # Force cursor_node to None for testing
        tree = explorer.directory_tree
        tree.cursor_line = -1
        await pilot.pause()
        assert explorer._get_selected_dir_relative() == ""


# ── Integration: Ctrl+N pre-fills from explorer ──────────────────────────────


async def test_create_file_prefills_selected_folder(workspace: Path):
    """Ctrl+N in explorer with a selected folder pre-fills the command palette."""
    subdir = workspace / "src"
    subdir.mkdir()
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        tree = explorer.directory_tree

        # Select the "src" directory node
        for node in tree.root.children:
            if node.data and node.data.path == subdir:
                tree.move_cursor(node)
                break
        await pilot.pause()

        # Focus the directory tree and press Ctrl+N
        tree.focus()
        await pilot.pause()
        await pilot.press("ctrl+n")
        await pilot.pause()

        # Verify CommandPalette opened with pre-filled value
        assert isinstance(app.screen, CommandPalette)
        inp = app.screen.query_one(CommandInput)
        assert inp.value == "src/"


async def test_create_directory_prefills_selected_folder(workspace: Path):
    """Ctrl+D in explorer with a selected folder pre-fills the command palette."""
    subdir = workspace / "lib"
    subdir.mkdir()
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        tree = explorer.directory_tree

        # Select the "lib" directory node
        for node in tree.root.children:
            if node.data and node.data.path == subdir:
                tree.move_cursor(node)
                break
        await pilot.pause()

        # Focus the directory tree and press Ctrl+D
        tree.focus()
        await pilot.pause()
        await pilot.press("ctrl+d")
        await pilot.pause()

        # Verify CommandPalette opened with pre-filled value
        assert isinstance(app.screen, CommandPalette)
        inp = app.screen.query_one(CommandInput)
        assert inp.value == "lib/"


async def test_create_file_no_prefill_at_root(workspace: Path):
    """Ctrl+N with file at workspace root → command palette input is empty."""
    (workspace / "hello.py").write_text("# hello\n")
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        tree = explorer.directory_tree

        # Select hello.py (at root level)
        for node in tree.root.children:
            if node.data and node.data.path == workspace / "hello.py":
                tree.move_cursor(node)
                break
        await pilot.pause()

        tree.focus()
        await pilot.pause()
        await pilot.press("ctrl+n")
        await pilot.pause()

        assert isinstance(app.screen, CommandPalette)
        inp = app.screen.query_one(CommandInput)
        assert inp.value == ""


# ── From editor focus: command palette "Create file" still pre-fills ─────────


async def test_create_file_prefills_from_editor_focus(workspace: Path):
    """Create file via app action while editor focused uses explorer selection."""
    subdir = workspace / "src"
    subdir.mkdir()
    (subdir / "main.py").write_text("# main\n")
    app = make_app(workspace, open_file=subdir / "main.py")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        tree = explorer.directory_tree

        # Select the "src" directory in the explorer
        for node in tree.root.children:
            if node.data and node.data.path == subdir:
                tree.move_cursor(node)
                break
        await pilot.pause()

        # Focus is on the editor, not the explorer
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.focus()
        await pilot.pause()

        # Trigger create file via app action (as command palette would)
        await app.action_new_file()
        await pilot.pause()

        assert isinstance(app.screen, CommandPalette)
        inp = app.screen.query_one(CommandInput)
        assert inp.value == "src/"
