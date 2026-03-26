"""
Close tab behavior tests — ported from VSCode editorGroupModel.test.ts
and editorGroupsService.test.ts.

VSCode reference:
- editorGroupModel.test.ts lines 1311-1368: "closing picks next to the right"
- editorGroupModel.test.ts lines 1514-1567: "Close Others, Close Left, Close Right"
- editorGroupsService.test.ts lines 728-751: "closeEditors (except one)"
- editorGroupsService.test.ts lines 843-867: "closeEditors (direction: right)"
- editorGroupsService.test.ts lines 902-926: "closeEditors (direction: left)"
- editorGroupsService.test.ts lines 962-981: "closeAllEditors"

Our editor uses position-based tab selection after close (right-adjacent, then left),
which matches VSCode's behavior when focusRecentEditorAfterClose = false.
MRU-based activation is NOT implemented — see behavioral differences section below.
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _open_n_files(app, pilot, workspace: Path, count: int) -> list[str]:
    """Open *count* .py files and return their pane IDs in open order.

    Each file is activated after opening, so the last file opened is the
    active tab.
    """
    main = app.main_view
    pane_ids: list[str] = []
    for i in range(count):
        f = workspace / f"file{i + 1}.py"
        if not f.exists():
            f.write_text(f"# file{i + 1}\n")
        pane_id = await main.open_code_editor_pane(path=f)
        tc = main.tabbed_content
        main._safe_activate_tab(tc, pane_id)
        await pilot.pause()
        pane_ids.append(pane_id)
    return pane_ids


def _active_pane(app) -> str | None:
    """Return the active pane ID of the active leaf's TabbedContent."""
    return app.main_view.tabbed_content.active


def _tab_count(app) -> int:
    """Return the number of open panes in the active leaf."""
    tc = app.main_view.tabbed_content
    return len(tc.get_ordered_pane_ids())


# ── Position-based activation after close ─────────────────────────────────────
# Ported from VSCode "Multiple Editors - closing picks next to the right"
# (editorGroupModel.test.ts lines 1311-1368)
#
# VSCode default: focusRecentEditorAfterClose = true (MRU-based)
# Our editor: always position-based (same as VSCode focusRecentEditorAfterClose = false)
# Behavioral difference: we don't support MRU-based activation


async def test_close_last_activates_previous(workspace: Path):
    """Closing the rightmost (last) tab activates the previous tab.

    VSCode equivalent: close input5 → input4 becomes active.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        assert _tab_count(app) == 5
        assert _active_pane(app) == pane_ids[4]  # file5 is active

        # Close file5 (rightmost) → file4 should activate
        await app.main_view.action_close_code_editor(pane_ids[4])
        await pilot.pause()
        assert _tab_count(app) == 4
        assert _active_pane(app) == pane_ids[3]


async def test_close_first_activates_next_right(workspace: Path):
    """Closing the first tab activates the next tab to the right.

    VSCode equivalent: set input1 active, close input1 → input2 becomes active.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        tc = app.main_view.tabbed_content
        # Activate file1 (first tab)
        tc.active = pane_ids[0]
        await pilot.pause()
        assert _active_pane(app) == pane_ids[0]

        # Close file1 → file2 should activate (next to the right)
        await app.main_view.action_close_code_editor(pane_ids[0])
        await pilot.pause()
        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[1]


async def test_close_middle_activates_next_right(workspace: Path):
    """Closing a middle tab activates the tab that takes its position (right).

    VSCode equivalent: set input3 active, close input3 → input4 becomes active.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        tc = app.main_view.tabbed_content
        # Activate file3 (middle tab)
        tc.active = pane_ids[2]
        await pilot.pause()
        assert _active_pane(app) == pane_ids[2]

        # Close file3 → file4 should activate (slides into file3's position)
        await app.main_view.action_close_code_editor(pane_ids[2])
        await pilot.pause()
        assert _tab_count(app) == 4
        assert _active_pane(app) == pane_ids[3]


async def test_close_sequential_position_based(workspace: Path):
    """Closing multiple tabs sequentially follows position-based activation.

    Ports the full sequence from VSCode "closing picks next to the right":
    Open 5 files. Close in sequence, verifying the right tab activates each time.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        tc = app.main_view.tabbed_content
        assert _tab_count(app) == 5

        # 1. Close file5 (rightmost) → file4 activates
        await app.main_view.action_close_code_editor(pane_ids[4])
        await pilot.pause()
        assert _tab_count(app) == 4
        assert _active_pane(app) == pane_ids[3]

        # 2. Activate file1, close file1 → file2 activates (next to right)
        tc.active = pane_ids[0]
        await pilot.pause()
        await app.main_view.action_close_code_editor(pane_ids[0])
        await pilot.pause()
        assert _tab_count(app) == 3
        assert _active_pane(app) == pane_ids[1]

        # 3. Activate file3, close file3 → file2 activates (was to the left,
        #    because file3 is now rightmost after file4/5 were closed... wait,
        #    file4 is still open. Let me reconsider.
        #    Remaining after step 2: file2, file3, file4
        #    Activate file3 (middle), close → file4 activates (next right)
        tc.active = pane_ids[2]
        await pilot.pause()
        await app.main_view.action_close_code_editor(pane_ids[2])
        await pilot.pause()
        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[3]

        # 4. Close file4 → file2 activates (only one left)
        await app.main_view.action_close_code_editor(pane_ids[3])
        await pilot.pause()
        assert _tab_count(app) == 1
        assert _active_pane(app) == pane_ids[1]

        # 5. Close file2 → no active editor, group empty
        await app.main_view.action_close_code_editor(pane_ids[1])
        await pilot.pause()
        assert _tab_count(app) == 0


async def test_close_only_tab_leaves_no_active_editor(workspace: Path):
    """Closing the only open tab leaves no active editor.

    VSCode equivalent: single editor, close → group is empty.
    """
    f = workspace / "solo.py"
    f.write_text("# solo\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert _tab_count(app) == 1
        pane_id = _active_pane(app)
        assert pane_id is not None

        await app.main_view.action_close_code_editor(pane_id)
        await pilot.pause()
        await pilot.pause()  # extra pause for async pane removal
        assert _tab_count(app) == 0
        assert app.main_view.get_active_code_editor() is None


# ── Close all editors ────────────────────────────────────────────────────────
# Ported from VSCode "closeAllEditors" (editorGroupsService.test.ts lines 962-981)


async def test_close_all_editors_empties_group(workspace: Path):
    """Closing all editors leaves the group completely empty.

    VSCode equivalent: open 2 editors, closeAllEditors() → group.isEmpty = true.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await _open_n_files(app, pilot, workspace, 3)
        assert _tab_count(app) == 3

        await app.main_view.action_close_all_editors()
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


# ── Tab ordering after close ────────────────────────────────────────────────
# Verifies that remaining tabs maintain their relative order after a close.


async def test_close_preserves_remaining_tab_order(workspace: Path):
    """Closing a tab does not change the order of remaining tabs.

    Open [file1, file2, file3, file4, file5], close file3.
    Remaining order should be [file1, file2, file4, file5].
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)
        ordered_before = tc.get_ordered_pane_ids()
        assert ordered_before == pane_ids

        # Activate file3 and close it
        tc.active = pane_ids[2]
        await pilot.pause()
        await app.main_view.action_close_code_editor(pane_ids[2])
        await pilot.pause()

        ordered_after = tc.get_ordered_pane_ids()
        expected = [pane_ids[0], pane_ids[1], pane_ids[3], pane_ids[4]]
        assert ordered_after == expected


# ── Close non-active tab ─────────────────────────────────────────────────────


async def test_close_inactive_tab_keeps_active_unchanged(workspace: Path):
    """Closing a non-active tab does not change the active tab.

    This tests the case in VSCode where closing a non-active editor keeps
    the current active editor unchanged.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        pane_ids = await _open_n_files(app, pilot, workspace, 4)
        tc = app.main_view.tabbed_content
        # Activate file2
        tc.active = pane_ids[1]
        await pilot.pause()
        assert _active_pane(app) == pane_ids[1]

        # Close file4 (not active) — file2 should remain active
        await app.main_view.action_close_code_editor(pane_ids[3])
        await pilot.pause()
        assert _tab_count(app) == 3
        assert _active_pane(app) == pane_ids[1]

        # Close file1 (not active) — file2 should remain active
        await app.main_view.action_close_code_editor(pane_ids[0])
        await pilot.pause()
        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[1]
