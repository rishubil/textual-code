"""Tests for explorer tree keyboard navigation.

Ported from VSCode's objectTree.test.ts TreeNavigator suite, adapted for
Textual's DirectoryTree keyboard model.

VSCode reference tests:
- "should be able to navigate" → test_cursor_down/up_traverses_visible_nodes
- "should skip collapsed nodes" → test_cursor_down_skips_collapsed_subtree
- Plus Textual-specific: enter, space, shift+left/up/down navigation

Directory structure used in tests (sorted: dirs first, then files, alphabetical):

  dir_a/
    a1.py
    a2.py
  dir_b/
    b1.py
    sub_b/
      deep.py
  alpha.py
  beta.py
  gamma.py
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.explorer import Explorer


@pytest.fixture
def nav_tree(workspace: Path) -> dict[str, Path]:
    """Create a directory tree suitable for navigation tests.

    Returns a dict mapping short names to paths for easy assertion.
    """
    dirs = {
        "dir_a": workspace / "dir_a",
        "dir_b": workspace / "dir_b",
        "sub_b": workspace / "dir_b" / "sub_b",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    files = {
        "a1": dirs["dir_a"] / "a1.py",
        "a2": dirs["dir_a"] / "a2.py",
        "b1": dirs["dir_b"] / "b1.py",
        "deep": dirs["sub_b"] / "deep.py",
        "alpha": workspace / "alpha.py",
        "beta": workspace / "beta.py",
        "gamma": workspace / "gamma.py",
    }
    for f in files.values():
        f.write_text(f"# {f.stem}\n")

    return {**dirs, **files}


def _get_cursor_path(explorer: Explorer) -> Path | None:
    """Return the path of the tree node currently under the cursor."""
    node = explorer.directory_tree.cursor_node
    if node is None or node.data is None:
        return None
    return node.data.path


async def _focus_tree_and_wait(pilot, app) -> Explorer:
    """Focus the explorer tree and wait for it to be ready.

    Sets cursor to the first visible node (cursor_line=0) since Textual's
    Tree starts with cursor_line=-1 (no selection) by default.
    """
    # Wait for initial tree load
    await pilot.wait_for_scheduled_animations()
    await pilot.wait_for_scheduled_animations()

    assert app.sidebar is not None
    explorer = app.sidebar.query_one(Explorer)
    tree = explorer.directory_tree
    tree.focus()
    await pilot.wait_for_scheduled_animations()

    # Initialize cursor at first visible node
    tree.cursor_line = 0
    await pilot.wait_for_scheduled_animations()
    return explorer


# ---------------------------------------------------------------------------
# 1. Basic down traversal — port of VSCode "should be able to navigate" (next)
# ---------------------------------------------------------------------------


async def test_cursor_down_traverses_visible_nodes(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Arrow-down moves through top-level nodes in sort order.

    With all directories collapsed, visible nodes are:
    dir_a/, dir_b/, alpha.py, beta.py, gamma.py
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Cursor should start at first visible node (dir_a)
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]

        # Move down through all top-level nodes
        expected_order = [
            nav_tree["dir_b"],
            nav_tree["alpha"],
            nav_tree["beta"],
            nav_tree["gamma"],
        ]
        for expected_path in expected_order:
            await pilot.press("down")
            await pilot.wait_for_scheduled_animations()
            assert _get_cursor_path(explorer) == expected_path, (
                f"Expected cursor at {expected_path.name}, "
                f"got {_get_cursor_path(explorer)}"
            )


# ---------------------------------------------------------------------------
# 2. Basic up traversal — port of VSCode "should be able to navigate" (previous)
# ---------------------------------------------------------------------------


async def test_cursor_up_traverses_visible_nodes(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Arrow-up moves backward through top-level nodes."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Move to the last node first
        for _ in range(4):
            await pilot.press("down")
            await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["gamma"]

        # Now move back up
        expected_reverse = [
            nav_tree["beta"],
            nav_tree["alpha"],
            nav_tree["dir_b"],
            nav_tree["dir_a"],
        ]
        for expected_path in expected_reverse:
            await pilot.press("up")
            await pilot.wait_for_scheduled_animations()
            assert _get_cursor_path(explorer) == expected_path


# ---------------------------------------------------------------------------
# 3. Collapsed subtree skip — port of VSCode "should skip collapsed nodes"
# ---------------------------------------------------------------------------


async def test_cursor_down_skips_collapsed_subtree(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Arrow-down on a collapsed directory skips its children.

    With dir_a collapsed: dir_a → (down) → dir_b (not a1.py).
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Cursor at dir_a (collapsed by default)
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]

        # Down should skip dir_a's children and go to dir_b
        await pilot.press("down")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_b"]


# ---------------------------------------------------------------------------
# 4. Enter expands directory — exposes children to navigation
# ---------------------------------------------------------------------------


async def test_enter_expands_directory(workspace: Path, nav_tree: dict[str, Path]):
    """Pressing Enter on a directory expands it, making children visible."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)
        tree = explorer.directory_tree

        # Cursor at dir_a — should be collapsed initially
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]
        node = tree.cursor_node
        assert node is not None
        assert not node.is_expanded

        # Enter expands the directory
        await pilot.press("enter")
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # extra pause for async directory load

        assert node.is_expanded

        # Children are now visible — down should go to a1.py
        await pilot.press("down")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["a1"]


# ---------------------------------------------------------------------------
# 5. Space toggles expand/collapse
# ---------------------------------------------------------------------------


async def test_space_toggles_expand_collapse(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Space toggles a directory between expanded and collapsed."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)
        tree = explorer.directory_tree

        node = tree.cursor_node
        assert node is not None
        assert not node.is_expanded

        # Space → expand
        await pilot.press("space")
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert node.is_expanded

        # Space again → collapse
        await pilot.press("space")
        await pilot.wait_for_scheduled_animations()
        assert not node.is_expanded


# ---------------------------------------------------------------------------
# 6. Depth-first traversal through expanded tree
# ---------------------------------------------------------------------------


async def test_depth_first_traversal_through_expanded_tree(
    workspace: Path, nav_tree: dict[str, Path]
):
    """After expanding dir_a, down traversal follows depth-first order.

    Expected: dir_a → a1.py → a2.py → dir_b → alpha.py → ...
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Expand dir_a
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]
        await pilot.press("enter")
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Traverse down through expanded tree
        expected_order = [
            nav_tree["a1"],
            nav_tree["a2"],
            nav_tree["dir_b"],
            nav_tree["alpha"],
            nav_tree["beta"],
            nav_tree["gamma"],
        ]
        for expected_path in expected_order:
            await pilot.press("down")
            await pilot.wait_for_scheduled_animations()
            assert _get_cursor_path(explorer) == expected_path, (
                f"Expected {expected_path.name}, got {_get_cursor_path(explorer)}"
            )


# ---------------------------------------------------------------------------
# 7. Enter on file opens it in editor
# ---------------------------------------------------------------------------


async def test_enter_on_file_opens_in_editor(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Pressing Enter on a file node opens it in the editor."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Navigate to alpha.py (skip dir_a, dir_b)
        await pilot.press("down")  # dir_b
        await pilot.wait_for_scheduled_animations()
        await pilot.press("down")  # alpha.py
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["alpha"]

        # Press Enter to open file
        await pilot.press("enter")
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # File should now be open in the editor
        main_view = app.main_view
        active_editor = main_view.get_active_code_editor()
        assert active_editor is not None
        assert active_editor.path == nav_tree["alpha"]


# ---------------------------------------------------------------------------
# 8. Shift+Left moves to parent
# ---------------------------------------------------------------------------


async def test_shift_left_moves_to_parent(workspace: Path, nav_tree: dict[str, Path]):
    """Shift+Left on a child node moves cursor to its parent directory."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Expand dir_a and move to a1.py
        await pilot.press("enter")  # expand dir_a
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.press("down")  # a1.py
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["a1"]

        # Shift+Left should go back to parent (dir_a)
        await pilot.press("shift+left")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]


# ---------------------------------------------------------------------------
# 9. Shift+Down moves to next sibling
# ---------------------------------------------------------------------------


async def test_shift_down_moves_to_next_sibling(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Shift+Down skips children and moves to the next sibling."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Expand dir_a and stay on dir_a
        await pilot.press("enter")  # expand dir_a
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]

        # Shift+Down should jump to dir_b (next sibling), skipping a1/a2
        await pilot.press("shift+down")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_b"]


# ---------------------------------------------------------------------------
# 10. Shift+Up moves to previous sibling
# ---------------------------------------------------------------------------


async def test_shift_up_moves_to_previous_sibling(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Shift+Up moves cursor to the previous sibling node."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Move to dir_b
        await pilot.press("down")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_b"]

        # Shift+Up should go to dir_a (previous sibling)
        await pilot.press("shift+up")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]


# ---------------------------------------------------------------------------
# 11. Navigation through multi-level expanded tree
# ---------------------------------------------------------------------------


async def test_multi_level_expansion_and_traversal(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Expanding nested directories and traversing shows full depth-first order.

    Expand dir_b → shows sub_b/ and b1.py (dirs first). Expand sub_b → shows deep.py.
    Full order: dir_a, dir_b, sub_b, b1.py, ..., alpha.py, beta.py, gamma.py
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Move to dir_b and expand it
        await pilot.press("down")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_b"]
        await pilot.press("enter")  # expand dir_b
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Directories come first: sub_b/ before b1.py
        await pilot.press("down")  # sub_b (directory first)
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["sub_b"]

        await pilot.press("enter")  # expand sub_b
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Now traverse from sub_b down
        await pilot.press("down")  # deep.py (sub_b's child)
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["deep"]

        await pilot.press("down")  # b1.py (dir_b's file child)
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["b1"]

        await pilot.press("down")  # alpha.py (top-level)
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["alpha"]


# ---------------------------------------------------------------------------
# 12. Cursor stays at boundary (does not wrap)
# ---------------------------------------------------------------------------


async def test_cursor_stays_at_top_boundary(workspace: Path, nav_tree: dict[str, Path]):
    """Pressing up at the first node does not move the cursor."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        assert _get_cursor_path(explorer) == nav_tree["dir_a"]

        # Press up at the top — cursor should stay
        await pilot.press("up")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]


async def test_cursor_stays_at_bottom_boundary(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Pressing down at the last node does not move the cursor."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Navigate to the last node
        for _ in range(4):
            await pilot.press("down")
            await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["gamma"]

        # Press down at the bottom — cursor should stay
        await pilot.press("down")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["gamma"]


# ---------------------------------------------------------------------------
# 13. Home key jumps to first node
# ---------------------------------------------------------------------------


async def test_home_moves_cursor_to_first_node(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Pressing Home moves cursor to the first visible node."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Move to the last node first
        for _ in range(4):
            await pilot.press("down")
            await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["gamma"]

        # Home should jump back to first node
        await pilot.press("home")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]


# ---------------------------------------------------------------------------
# 14. End key jumps to last node
# ---------------------------------------------------------------------------


async def test_end_moves_cursor_to_last_node(
    workspace: Path, nav_tree: dict[str, Path]
):
    """Pressing End moves cursor to the last visible node."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Cursor starts at first node
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]

        # End should jump to last node
        await pilot.press("end")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["gamma"]


# ---------------------------------------------------------------------------
# 15. Home/End with expanded subtree
# ---------------------------------------------------------------------------


async def test_home_end_with_expanded_tree(workspace: Path, nav_tree: dict[str, Path]):
    """End moves to last visible node even when subtrees are expanded."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # Expand dir_a
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]
        await pilot.press("enter")
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # End should jump to last visible node (gamma.py, not a child of dir_a)
        await pilot.press("end")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["gamma"]

        # Home should jump back to first node (dir_a)
        await pilot.press("home")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]


# ---------------------------------------------------------------------------
# 16. Home/End from no-selection state (cursor_line=-1)
# ---------------------------------------------------------------------------


async def test_home_end_from_no_selection(workspace: Path, nav_tree: dict[str, Path]):
    """Home/End work when cursor has not been initialized (cursor_line=-1)."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)
        tree = explorer.directory_tree
        tree.focus()
        await pilot.wait_for_scheduled_animations()

        # Do NOT set cursor_line — leave at default (-1)
        assert tree.cursor_line == -1

        # Home should activate cursor at first node
        await pilot.press("home")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]

        # End should also work from no-selection state
        # Reset cursor to -1 by navigating away and back
        tree.cursor_line = -1
        await pilot.wait_for_scheduled_animations()

        await pilot.press("end")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["gamma"]


# ---------------------------------------------------------------------------
# 17. Home/End idempotent — consecutive presses stay at same position
# ---------------------------------------------------------------------------


async def test_home_end_idempotent(workspace: Path, nav_tree: dict[str, Path]):
    """Pressing Home/End twice keeps cursor at the same node."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        explorer = await _focus_tree_and_wait(pilot, app)

        # End twice — should stay at gamma
        await pilot.press("end")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["gamma"]
        await pilot.press("end")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["gamma"]

        # Home twice — should stay at dir_a
        await pilot.press("home")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]
        await pilot.press("home")
        await pilot.wait_for_scheduled_animations()
        assert _get_cursor_path(explorer) == nav_tree["dir_a"]
