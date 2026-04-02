"""
Close tab behavior tests — ported from VSCode editorGroupModel.test.ts
and editorGroupsService.test.ts.

VSCode reference:
- editorGroupModel.test.ts lines 1262-1309: "closing picks next from MRU list"
- editorGroupModel.test.ts lines 1311-1368: "closing picks next to the right"
- editorGroupModel.test.ts lines 1514-1567: "Close Others, Close Left, Close Right"
- editorGroupsService.test.ts lines 728-751: "closeEditors (except one)"
- editorGroupsService.test.ts lines 843-867: "closeEditors (direction: right)"
- editorGroupsService.test.ts lines 902-926: "closeEditors (direction: left)"
- editorGroupsService.test.ts lines 962-981: "closeAllEditors"
- editorGroupsService.test.ts lines 646-694: "closeEditor - dirty editor handling"
- editorGroupsService.test.ts lines 696-745: "closeEditors - dirty editor handling"
- editorGroupsService.test.ts lines 983-1026: "closeAllEditors - dirty editor handling"
- editorGroupModel.test.ts lines 1962-2020: "Multiple Editors - Editor Emits Dirty"
- editorGroupsService.test.ts lines 1299-1322: "find editors"
- editorGroupModel.test.ts lines 220-260: "tab opening position"

Supports both:
- MRU-based activation (close_tab_focus_recent = true, default)
  → VSCode default: focusRecentEditorAfterClose = true
- Position-based activation (close_tab_focus_recent = false)
  → VSCode: focusRecentEditorAfterClose = false
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.modals import UnsavedChangeModalScreen
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
from textual_code.widgets.split_tree import all_leaves

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
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for lazy editor mount
        pane_ids.append(pane_id)
    return pane_ids


def _active_pane(app) -> str | None:
    """Return the active pane ID of the active leaf's TabbedContent."""
    return app.main_view.tabbed_content.active


def _tab_count(app) -> int:
    """Return the number of open panes in the active leaf."""
    tc = app.main_view.tabbed_content
    return len(tc.get_ordered_pane_ids())


def _position_based_config(workspace: Path) -> Path:
    """Write a TOML config that disables MRU-based close activation."""
    cfg = workspace / "_test_position_close.toml"
    cfg.write_text("[editor]\nclose_tab_focus_recent = false\n")
    return cfg


# ── Position-based activation after close ─────────────────────────────────────
# Ported from VSCode "Multiple Editors - closing picks next to the right"
# (editorGroupModel.test.ts lines 1311-1368)
#
# Requires close_tab_focus_recent = false (position-based mode).


async def test_close_last_activates_previous(workspace: Path):
    """Closing the rightmost (last) tab activates the previous tab.

    VSCode equivalent: close input5 → input4 becomes active.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        assert _tab_count(app) == 5
        assert _active_pane(app) == pane_ids[4]  # file5 is active

        # Close file5 (rightmost) → file4 should activate
        await app.main_view.action_close_code_editor(pane_ids[4])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 4
        assert _active_pane(app) == pane_ids[3]


async def test_close_first_activates_next_right(workspace: Path):
    """Closing the first tab activates the next tab to the right.

    VSCode equivalent: set input1 active, close input1 → input2 becomes active.
    Requires close_tab_focus_recent = false (position-based mode).
    """
    app = make_app(
        workspace, light=True, user_config_path=_position_based_config(workspace)
    )
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        tc = app.main_view.tabbed_content
        # Activate file1 (first tab)
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for tab switch + lazy mount
        assert _active_pane(app) == pane_ids[0]

        # Close file1 → file2 should activate (next to the right)
        await app.main_view.action_close_code_editor(pane_ids[0])
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for close + next tab activation
        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[1]


async def test_close_middle_activates_next_right(workspace: Path):
    """Closing a middle tab activates the tab that takes its position (right).

    VSCode equivalent: set input3 active, close input3 → input4 becomes active.
    Requires close_tab_focus_recent = false (position-based mode).
    """
    app = make_app(
        workspace, light=True, user_config_path=_position_based_config(workspace)
    )
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        tc = app.main_view.tabbed_content
        # Activate file3 (middle tab)
        tc.active = pane_ids[2]
        await pilot.wait_for_scheduled_animations()
        assert _active_pane(app) == pane_ids[2]

        # Close file3 → file4 should activate (slides into file3's position)
        await app.main_view.action_close_code_editor(pane_ids[2])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 4
        assert _active_pane(app) == pane_ids[3]


async def test_close_sequential_position_based(workspace: Path):
    """Closing multiple tabs sequentially follows position-based activation.

    Ports the full sequence from VSCode "closing picks next to the right":
    Open 5 files. Close in sequence, verifying the right tab activates each time.
    Requires close_tab_focus_recent = false (position-based mode).
    """
    app = make_app(
        workspace, light=True, user_config_path=_position_based_config(workspace)
    )
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        tc = app.main_view.tabbed_content
        assert _tab_count(app) == 5

        # 1. Close file5 (rightmost) → file4 activates
        await app.main_view.action_close_code_editor(pane_ids[4])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 4
        assert _active_pane(app) == pane_ids[3]

        # 2. Activate file1, close file1 → file2 activates (next to right)
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_close_code_editor(pane_ids[0])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 3
        assert _active_pane(app) == pane_ids[1]

        # 3. Remaining: [file2, file3, file4]
        #    Activate file3 (middle), close → file4 activates (next right)
        tc.active = pane_ids[2]
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_close_code_editor(pane_ids[2])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[3]

        # 4. Close file4 → file2 activates (only one left)
        await app.main_view.action_close_code_editor(pane_ids[3])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 1
        assert _active_pane(app) == pane_ids[1]

        # 5. Close file2 → no active editor, group empty
        await app.main_view.action_close_code_editor(pane_ids[1])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 0


async def test_close_only_tab_leaves_no_active_editor(workspace: Path):
    """Closing the only open tab leaves no active editor.

    VSCode equivalent: single editor, close → group is empty.
    """
    f = workspace / "solo.py"
    f.write_text("# solo\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 1
        pane_id = _active_pane(app)
        assert pane_id is not None

        await app.main_view.action_close_code_editor(pane_id)
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # extra pause for async pane removal
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
        await pilot.wait_for_scheduled_animations()
        await _open_n_files(app, pilot, workspace, 3)
        assert _tab_count(app) == 3

        await app.main_view.action_close_all_editors()
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for close all completion
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
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)
        ordered_before = tc.get_ordered_pane_ids()
        assert ordered_before == pane_ids

        # Activate file3 and close it
        tc.active = pane_ids[2]
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_close_code_editor(pane_ids[2])
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for tab close + reorder settling

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
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 4)
        tc = app.main_view.tabbed_content
        # Activate file2
        tc.active = pane_ids[1]
        await pilot.wait_for_scheduled_animations()
        assert _active_pane(app) == pane_ids[1]

        # Close file4 (not active) — file2 should remain active
        await app.main_view.action_close_code_editor(pane_ids[3])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 3
        assert _active_pane(app) == pane_ids[1]

        # Close file1 (not active) — file2 should remain active
        await app.main_view.action_close_code_editor(pane_ids[0])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[1]


# ── Dirty editor close behavior ─────────────────────────────────────────────
# Ported from VSCode "closeEditor - dirty editor handling"
# (editorGroupsService.test.ts lines 646-694)
#
# VSCode flow: dirty editor close → confirm dialog → CANCEL / DONT_SAVE / SAVE
# Our flow:    dirty editor close → UnsavedChangeModalScreen → cancel / dont_save / save


async def test_close_dirty_editor_cancel_keeps_editor(workspace: Path):
    """Closing a dirty editor and pressing Cancel keeps the editor open.

    VSCode equivalent: accessor.fileDialogService.setConfirmResult(ConfirmResult.CANCEL)
    → closed = false, editor NOT disposed.
    """
    f = workspace / "dirty_cancel.py"
    f.write_text("original\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.wait_for_scheduled_animations()

        # Close the dirty editor
        await pilot.press("ctrl+w")
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, UnsavedChangeModalScreen)

        # Press Cancel
        await pilot.click("#cancel")
        await pilot.wait_for_scheduled_animations()

        # Editor should still be open and unchanged
        assert _tab_count(app) == 1
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.text == "modified\n"


async def test_close_dirty_editor_dont_save_closes_tab(workspace: Path):
    """Closing a dirty editor and pressing Don't Save closes it.

    VSCode equivalent: setConfirmResult(ConfirmResult.DONT_SAVE)
    → closed = true, editor disposed.
    """
    f = workspace / "dirty_dontsave.py"
    f.write_text("original\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified\n"
        await pilot.wait_for_scheduled_animations()

        await pilot.press("ctrl+w")
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, UnsavedChangeModalScreen)

        await pilot.click("#dont_save")
        await pilot.wait_for_scheduled_animations()

        # Editor should be closed and file content unchanged on disk
        assert _tab_count(app) == 0
        assert f.read_text() == "original\n"


async def test_close_dirty_editor_save_closes_and_persists(workspace: Path):
    """Closing a dirty editor and pressing Save writes the file and closes.

    VSCode equivalent: saving dirty editor before close → file content updated,
    editor closed.
    """
    f = workspace / "dirty_save.py"
    f.write_text("original\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "saved content\n"
        await pilot.wait_for_scheduled_animations()

        await pilot.press("ctrl+w")
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, UnsavedChangeModalScreen)

        await pilot.click("#save")
        await pilot.wait_for_scheduled_animations()

        # Editor should be closed and file content updated on disk
        assert _tab_count(app) == 0
        assert f.read_text() == "saved content\n"


# ── Dirty editor batch close behavior ───────────────────────────────────────
# Ported from VSCode "closeEditors - dirty editor handling"
# (editorGroupsService.test.ts lines 696-745)
#
# VSCode: batch close with dirty → atomic: CANCEL stops ALL, DONT_SAVE closes ALL
# Our editor: close-all is sequential — each dirty editor gets its own modal prompt


async def test_close_all_dirty_cancel_stops_all(workspace: Path):
    """Close-all with dirty editor: Cancel stops the operation, all editors stay.

    VSCode equivalent: closeEditors([dirty, clean]) with CANCEL → none disposed.
    """
    f1 = workspace / "batch_dirty1.py"
    f2 = workspace / "batch_clean2.py"
    f1.write_text("clean1\n")
    f2.write_text("clean2\n")
    app = make_app(workspace, light=True, open_file=f1)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.open_code_editor_pane(path=f2)
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 2

        # Make the first file dirty
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Activate f1
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)
        pane_ids = tc.get_ordered_pane_ids()
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "dirty!\n"
        await pilot.wait_for_scheduled_animations()

        # Close all editors
        await app.main_view.action_close_all_editors()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, UnsavedChangeModalScreen)

        # Cancel — all editors stay
        await pilot.click("#cancel")
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 2


async def test_close_all_dirty_dont_save_closes_all(workspace: Path):
    """Close-all with dirty editor: Don't Save closes everything.

    VSCode equivalent: closeAllEditors() with DONT_SAVE → all disposed.
    """
    f1 = workspace / "batch_dirty_ds1.py"
    f2 = workspace / "batch_clean_ds2.py"
    f1.write_text("clean1\n")
    f2.write_text("clean2\n")
    app = make_app(workspace, light=True, open_file=f1)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.open_code_editor_pane(path=f2)
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 2

        # Make f1 dirty
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)
        pane_ids = tc.get_ordered_pane_ids()
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "dirty!\n"
        await pilot.wait_for_scheduled_animations()

        # Close all editors
        await app.main_view.action_close_all_editors()
        await pilot.wait_for_scheduled_animations()

        # Modal should appear for dirty editor
        assert isinstance(app.screen, UnsavedChangeModalScreen)
        await pilot.click("#dont_save")
        await pilot.wait_for_scheduled_animations()

        # All editors should be closed
        assert len(app.main_view.opened_pane_ids) == 0


# ── Dirty state detection across splits ──────────────────────────────────────
# Ported from VSCode "Multiple Editors - Editor Emits Dirty and Label Changed"
# (editorGroupModel.test.ts lines 1962-2020)
#
# VSCode: dirty state changes emit events per group, isolated across groups
# Our editor: has_unsaved_pane() scans all splits; dirty indicator in tab title


async def test_dirty_state_detected_across_splits(workspace: Path):
    """Dirty state in one split is detected by has_unsaved_pane().

    VSCode equivalent: dirty state events are tracked per editor group.
    In our architecture, has_unsaved_pane() scans all splits.
    """
    f1 = workspace / "split_dirty1.py"
    f2 = workspace / "split_clean2.py"
    f1.write_text("clean1\n")
    f2.write_text("clean2\n")
    app = make_app(workspace, light=True, open_file=f1)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        main = app.main_view

        # Initially clean
        assert main.has_unsaved_pane() is False

        # Open f2 in a split
        await app.main_view.open_code_editor_pane(path=f2)
        await pilot.wait_for_scheduled_animations()
        await main.action_split_right()
        await pilot.wait_for_scheduled_animations()

        # Make f1 dirty (in the original split)
        tc = main.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)
        pane_ids = tc.get_ordered_pane_ids()
        assert pane_ids, "Expected at least one pane after split"
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        editor = main.get_active_code_editor()
        assert editor is not None, "Expected active editor after activating pane"
        editor.text = "dirty in split 1\n"
        await pilot.wait_for_scheduled_animations()

        # has_unsaved_pane() should detect dirty state across splits
        assert main.has_unsaved_pane() is True


# ── Find editors by file path ─────────────────────────────────────────────
# Ported from VSCode "find editors" (editorGroupsService.test.ts lines 1299-1322)
#
# VSCode: group.findEditors(URI.file('foo/bar')) returns matching editors
# Our editor: pane_id_from_path() for active leaf; LeafNode.opened_files for any leaf


async def test_find_editor_by_path_in_active_leaf(workspace: Path):
    """Finding an editor by path in the active leaf returns its pane ID.

    VSCode equivalent: group.findEditors(URI.file('foo/bar1'))
    → returns array with matching editor(s).
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        main = app.main_view

        # Open 3 files
        f1 = workspace / "find1.py"
        f2 = workspace / "find2.py"
        f3 = workspace / "find3.py"
        f1.write_text("# find1\n")
        f2.write_text("# find2\n")
        f3.write_text("# find3\n")

        pane1 = await main.open_code_editor_pane(path=f1)
        await pilot.wait_for_scheduled_animations()
        pane2 = await main.open_code_editor_pane(path=f2)
        await pilot.wait_for_scheduled_animations()
        pane3 = await main.open_code_editor_pane(path=f3)
        await pilot.wait_for_scheduled_animations()

        # Find by path — should return correct pane IDs
        assert main.pane_id_from_path(f1) == pane1
        assert main.pane_id_from_path(f2) == pane2
        assert main.pane_id_from_path(f3) == pane3


async def test_find_editor_path_not_found_returns_none(workspace: Path):
    """Finding an editor by a path that isn't open returns None.

    VSCode equivalent: findEditors(unknownURI) → empty array.
    """
    f = workspace / "exists.py"
    f.write_text("# exists\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        main = app.main_view

        not_open = workspace / "not_open.py"
        assert main.pane_id_from_path(not_open) is None


async def test_find_editor_by_path_across_splits(workspace: Path):
    """Finding an editor by path works across different split groups.

    VSCode equivalent: findEditors scoped per group — we must iterate all leaves.
    Our pane_id_from_path() only searches the active leaf, so cross-split lookup
    requires iterating all_leaves().
    """
    f1 = workspace / "left_file.py"
    f2 = workspace / "right_file.py"
    f1.write_text("# left\n")
    f2.write_text("# right\n")
    app = make_app(workspace, light=True, open_file=f1)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        main = app.main_view

        # Split right and open f2 in the right leaf
        await main.action_split_right()
        await pilot.wait_for_scheduled_animations()
        await main.open_code_editor_pane(path=f2)
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(main._split_root)
        assert len(leaves) == 2

        # pane_id_from_path() only searches active leaf
        # Active leaf is the right one (after split)
        assert main.pane_id_from_path(f2) is not None
        # f1 is in left leaf — not found via pane_id_from_path()
        # (it may or may not be found depending on which leaf is active)

        # Cross-split lookup via all_leaves iteration
        found_f1 = None
        found_f2 = None
        for leaf in leaves:
            if f1 in leaf.opened_files:
                found_f1 = leaf.opened_files[f1]
            if f2 in leaf.opened_files:
                found_f2 = leaf.opened_files[f2]

        assert found_f1 is not None, "f1 should be found in some leaf"
        assert found_f2 is not None, "f2 should be found in some leaf"
        # Files should be in different leaves
        leaf_for_f1 = next(lf for lf in leaves if f1 in lf.opened_files)
        leaf_for_f2 = next(lf for lf in leaves if f2 in lf.opened_files)
        assert leaf_for_f1.leaf_id != leaf_for_f2.leaf_id


# ── Tab opening position ──────────────────────────────────────────────────
# Ported from VSCode "Multiple Editors - Editor Open Ordering"
# (editorGroupModel.test.ts lines 220-260)
#
# VSCode: new editor opens to the right of the active editor by default.
# Our editor: same — new tabs are inserted after the active tab.


async def test_new_tabs_sequential_when_last_is_active(workspace: Path):
    """Sequential tab opens preserve order when last tab is always active.

    Since the last-opened tab is always active, inserting "after active"
    produces the same result as appending at the end.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 4)
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)

        ordered = tc.get_ordered_pane_ids()
        # Tabs should be in the order they were opened
        assert ordered == pane_ids


async def test_new_tab_opens_after_active_tab(workspace: Path):
    """New tabs are inserted immediately after the active tab (VSCode default).

    Open A, B, C (C is active). Activate A. Open D → D appears after A: [A, D, B, C].
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)

        # Activate the first tab (index 0)
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        assert _active_pane(app) == pane_ids[0]

        # Open a 4th file — should appear AFTER pane_ids[0], not at end
        f4 = workspace / "file4.py"
        f4.write_text("# file4\n")
        pane4 = await app.main_view.open_code_editor_pane(path=f4)
        await pilot.wait_for_scheduled_animations()

        ordered = tc.get_ordered_pane_ids()
        # New tab inserted after active tab (pane_ids[0])
        assert ordered == [pane_ids[0], pane4, pane_ids[1], pane_ids[2]]


async def test_new_tab_opens_after_active_when_middle_tab_active(workspace: Path):
    """Multiple insertions respect the active tab at each point.

    Open A, B, C. Activate A. Open D → [A, D, B, C].
    Activate C. Open E → [A, D, B, C, E].
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)

        # Activate first tab
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()

        # Open D — should go after A: [A, D, B, C]
        f4 = workspace / "file4.py"
        f4.write_text("# file4\n")
        pane4 = await app.main_view.open_code_editor_pane(path=f4)
        await pilot.wait_for_scheduled_animations()

        ordered = tc.get_ordered_pane_ids()
        assert ordered == [pane_ids[0], pane4, pane_ids[1], pane_ids[2]]

        # Activate last tab (C)
        tc.active = pane_ids[2]
        await pilot.wait_for_scheduled_animations()

        # Open E — should go after C: [A, D, B, C, E]
        f5 = workspace / "file5.py"
        f5.write_text("# file5\n")
        pane5 = await app.main_view.open_code_editor_pane(path=f5)
        await pilot.wait_for_scheduled_animations()

        ordered = tc.get_ordered_pane_ids()
        assert ordered == [pane_ids[0], pane4, pane_ids[1], pane_ids[2], pane5]


# ── Close Other Editors ──────────────────────────────────────────────────────
# Ported from VSCode "closeEditors (except one)"
# (editorGroupsService.test.ts lines 728-751)


async def test_close_others_keeps_active_only(workspace: Path):
    """Close Others closes all tabs except the active one.

    VSCode equivalent: group.closeEditors({ except: input3 }) → only input3 remains.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        tc = app.main_view.tabbed_content
        # Activate file3 (middle tab)
        tc.active = pane_ids[2]
        await pilot.wait_for_scheduled_animations()
        assert _active_pane(app) == pane_ids[2]

        await app.main_view.action_close_other_editors()
        await pilot.wait_for_scheduled_animations()

        assert _tab_count(app) == 1
        assert _active_pane(app) == pane_ids[2]


async def test_close_others_with_single_tab_is_noop(workspace: Path):
    """Close Others with only one tab open is a no-op."""
    f = workspace / "solo.py"
    f.write_text("# solo\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_id = _active_pane(app)
        assert _tab_count(app) == 1

        await app.main_view.action_close_other_editors()
        await pilot.wait_for_scheduled_animations()

        assert _tab_count(app) == 1
        assert _active_pane(app) == pane_id


async def test_close_others_preserves_dirty_unmounted_editors(workspace: Path):
    """Close Others skips dirty unmounted editors (they can't show a modal).

    With lazy mounting, non-active editors are unmounted.  Dirty unmounted
    editors are preserved to prevent silent data loss.  Only clean editors
    are closed.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        tc = app.main_view.tabbed_content

        # Activate file1 and make it dirty
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "dirty!\n"
        await pilot.wait_for_scheduled_animations()

        # Activate file2 (the one to keep)
        tc.active = pane_ids[1]
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_close_other_editors()
        await pilot.wait_for_scheduled_animations()

        # file1 (dirty, unmounted) is preserved; file3 (clean) is closed
        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[1]
        # No modal shown
        assert not isinstance(app.screen, UnsavedChangeModalScreen)


# ── Close Editors to the Right ──────────────────────────────────────────────
# Ported from VSCode "closeEditors (direction: right)"
# (editorGroupsService.test.ts lines 843-867)


async def test_close_right_removes_tabs_to_right(workspace: Path):
    """Close to the Right closes all tabs after the active tab.

    VSCode equivalent: group.closeEditors({ direction: RIGHT, except: input2 })
    → input1 and input2 remain.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)
        # Activate file2
        tc.active = pane_ids[1]
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_close_editors_to_the_right()
        await pilot.wait_for_scheduled_animations()

        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[1]
        assert tc.get_ordered_pane_ids() == [pane_ids[0], pane_ids[1]]


async def test_close_right_from_last_tab_is_noop(workspace: Path):
    """Close to the Right from the last tab is a no-op."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        # file3 is already active (last opened)
        assert _active_pane(app) == pane_ids[2]

        await app.main_view.action_close_editors_to_the_right()
        await pilot.wait_for_scheduled_animations()

        assert _tab_count(app) == 3


async def test_close_right_preserves_dirty_unmounted_editors(workspace: Path):
    """Close Right skips dirty unmounted editors to the right.

    Clean editors to the right are closed; dirty ones are preserved.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)

        # Make file3 (rightmost) dirty
        tc.active = pane_ids[2]
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "dirty!\n"
        await pilot.wait_for_scheduled_animations()

        # Activate file1
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_close_editors_to_the_right()
        await pilot.wait_for_scheduled_animations()

        # file2 (clean) closed; file3 (dirty, unmounted) preserved
        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[0]
        assert not isinstance(app.screen, UnsavedChangeModalScreen)


# ── Close Editors to the Left ───────────────────────────────────────────────
# Ported from VSCode "closeEditors (direction: left)"
# (editorGroupsService.test.ts lines 902-926)


async def test_close_left_removes_tabs_to_left(workspace: Path):
    """Close to the Left closes all tabs before the active tab.

    VSCode equivalent: group.closeEditors({ direction: LEFT, except: input4 })
    → input4 and input5 remain.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)
        # Activate file4
        tc.active = pane_ids[3]
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_close_editors_to_the_left()
        await pilot.wait_for_scheduled_animations()

        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[3]
        assert tc.get_ordered_pane_ids() == [pane_ids[3], pane_ids[4]]


async def test_close_left_from_first_tab_is_noop(workspace: Path):
    """Close to the Left from the first tab is a no-op."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        tc = app.main_view.tabbed_content
        # Activate file1 (first tab)
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_close_editors_to_the_left()
        await pilot.wait_for_scheduled_animations()

        assert _tab_count(app) == 3


async def test_close_left_preserves_dirty_unmounted_editors(workspace: Path):
    """Close Left skips dirty unmounted editors to the left.

    Clean editors to the left are closed; dirty ones are preserved.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        tc = app.main_view.tabbed_content
        assert isinstance(tc, DraggableTabbedContent)

        # Make file1 (leftmost) dirty
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "dirty!\n"
        await pilot.wait_for_scheduled_animations()

        # Activate file3
        tc.active = pane_ids[2]
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_close_editors_to_the_left()
        await pilot.wait_for_scheduled_animations()

        # file2 (clean) closed; file1 (dirty, unmounted) preserved
        assert _tab_count(app) == 2
        assert _active_pane(app) == pane_ids[2]
        assert not isinstance(app.screen, UnsavedChangeModalScreen)


# ── Close Saved Editors ─────────────────────────────────────────────────────
# Ported from VSCode "closeEditors (saved only)"
# (editorGroupsService.test.ts lines 788-810)


async def test_close_saved_skips_dirty_tabs(workspace: Path):
    """Close Saved closes clean tabs and skips dirty ones.

    VSCode equivalent: group.closeEditors({ savedOnly: true })
    → only dirty editors remain.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        tc = app.main_view.tabbed_content

        # Make file2 dirty
        tc.active = pane_ids[1]
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "dirty!\n"
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_close_saved_editors()
        await pilot.wait_for_scheduled_animations()

        assert _tab_count(app) == 1
        assert _active_pane(app) == pane_ids[1]


async def test_close_saved_all_clean_closes_all(workspace: Path):
    """Close Saved with all clean tabs closes everything."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await _open_n_files(app, pilot, workspace, 3)
        assert _tab_count(app) == 3

        await app.main_view.action_close_saved_editors()
        await pilot.wait_for_scheduled_animations()

        assert _tab_count(app) == 0


async def test_close_saved_all_dirty_is_noop(workspace: Path):
    """Close Saved with all dirty tabs is a no-op."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 2)
        tc = app.main_view.tabbed_content

        # Make both dirty
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for tab switch + lazy mount
        editor1 = app.main_view.get_active_code_editor()
        assert editor1 is not None
        editor1.text = "dirty1!\n"
        await pilot.wait_for_scheduled_animations()

        tc.active = pane_ids[1]
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for tab switch + lazy mount
        editor2 = app.main_view.get_active_code_editor()
        assert editor2 is not None
        editor2.text = "dirty2!\n"
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_close_saved_editors()
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for async close operation

        assert _tab_count(app) == 2


async def test_close_saved_no_modal_shown(workspace: Path):
    """Close Saved never shows an unsaved changes modal."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 2)
        tc = app.main_view.tabbed_content

        # Make file1 dirty
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "dirty!\n"
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_close_saved_editors()
        await pilot.wait_for_scheduled_animations()

        # file2 (clean) closed, file1 (dirty) remains, no modal
        assert _tab_count(app) == 1
        assert _active_pane(app) == pane_ids[0]
        assert not isinstance(app.screen, UnsavedChangeModalScreen)


# ── Close operations: split isolation ───────────────────────────────────────


async def test_close_others_does_not_affect_other_splits(workspace: Path):
    """Close Others only affects the active split, not other splits.

    Open files in two splits. Close Others in the right split.
    The left split should be unaffected.
    """
    f1 = workspace / "split_left.py"
    f2 = workspace / "split_right1.py"
    f3 = workspace / "split_right2.py"
    f1.write_text("# left\n")
    f2.write_text("# right1\n")
    f3.write_text("# right2\n")
    app = make_app(workspace, light=True, open_file=f1)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        main = app.main_view

        # Split right and open files in the new split
        await main.action_split_right()
        await pilot.wait_for_scheduled_animations()
        p2 = await main.open_code_editor_pane(path=f2)
        await pilot.wait_for_scheduled_animations()
        await main.open_code_editor_pane(path=f3)
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(main._split_root)
        assert len(leaves) == 2

        # Activate p2 in right split
        tc = main.tabbed_content
        tc.active = p2
        await pilot.wait_for_scheduled_animations()

        # Close Others in right split — should only close p3
        await main.action_close_other_editors()
        await pilot.wait_for_scheduled_animations()

        # Right split: only p2 remains
        right_count = len(tc.get_ordered_pane_ids())
        assert right_count == 1

        # Left split: still has its file
        left_leaf = [lf for lf in all_leaves(main._split_root) if f1 in lf.opened_files]
        assert len(left_leaf) == 1


# ── MRU-based activation after close ─────────────────────────────────────────
# Ported from VSCode "Multiple Editors - closing picks next from MRU list"
# (editorGroupModel.test.ts lines 1262-1309)
#
# MRU is the default (close_tab_focus_recent = true).


async def test_mru_history_tracks_activation_order(workspace: Path):
    """MRU history records tab activations in most-recent-first order."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        main = app.main_view
        leaf_id = main._active_leaf_id
        history = main._mru_history.get(leaf_id, [])
        # Last opened file should be first in MRU
        assert history == [pane_ids[2], pane_ids[1], pane_ids[0]]


async def test_mru_history_updates_on_reactivation(workspace: Path):
    """Re-activating a tab moves it to the front of MRU."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 3)
        tc = app.main_view.tabbed_content
        # Activate file1 (was last in MRU)
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        main = app.main_view
        leaf_id = main._active_leaf_id
        history = main._mru_history.get(leaf_id, [])
        assert history[0] == pane_ids[0]
        assert history[1] == pane_ids[2]
        assert history[2] == pane_ids[1]


async def test_mru_close_activates_most_recent(workspace: Path):
    """Closing active tab activates the most recently used tab (MRU).

    VSCode reference (editorGroupModel.test.ts:1262-1285):
    Open 1..5, close 5 → 4 active (MRU next).
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        # MRU order: [5, 4, 3, 2, 1] (5 is most recent)
        assert _active_pane(app) == pane_ids[4]

        # Close file5 → file4 should activate (MRU-next)
        await app.main_view.action_close_code_editor(pane_ids[4])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 4
        assert _active_pane(app) == pane_ids[3]


async def test_mru_close_after_reactivation(workspace: Path):
    """MRU close respects reactivation order.

    VSCode reference (editorGroupModel.test.ts:1287-1292):
    Open 1..5, setActive(1), setActive(4), close 4 → 1 active.
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        tc = app.main_view.tabbed_content

        # Reactivate file1, then file4
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        tc.active = pane_ids[3]
        await pilot.wait_for_scheduled_animations()
        # MRU: [4, 1, 5, 3, 2]

        # Close file4 → file1 active (MRU-next)
        await app.main_view.action_close_code_editor(pane_ids[3])
        await pilot.wait_for_scheduled_animations()
        assert _active_pane(app) == pane_ids[0]


async def test_mru_close_sequential(workspace: Path):
    """Full VSCode MRU close sequence.

    VSCode reference (editorGroupModel.test.ts:1262-1309):
    1. Open 1..5 → MRU: [5, 4, 3, 2, 1]
    2. Close 5 → 4 active
    3. setActive(1), setActive(4) → MRU: [4, 1, 3, 2]
    4. Close 4 → 1 active
    5. Close 1 → 3 active
    6. setActive(2), close 2 → 3 active
    7. Close 3 → no active
    """
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 5)
        main = app.main_view
        tc = main.tabbed_content
        leaf_id = main._active_leaf_id

        # Step 2: Close 5 → 4 active
        await main.action_close_code_editor(pane_ids[4])
        await pilot.wait_for_scheduled_animations()
        assert _active_pane(app) == pane_ids[3]
        assert pane_ids[4] not in main._mru_history.get(leaf_id, [])

        # Step 3: setActive(1), setActive(4)
        tc.active = pane_ids[0]
        await pilot.wait_for_scheduled_animations()
        tc.active = pane_ids[3]
        await pilot.wait_for_scheduled_animations()

        # Step 4: Close 4 → 1 active
        await main.action_close_code_editor(pane_ids[3])
        await pilot.wait_for_scheduled_animations()
        assert _active_pane(app) == pane_ids[0]
        assert pane_ids[3] not in main._mru_history.get(leaf_id, [])

        # Step 5: Close 1 → 3 active
        await main.action_close_code_editor(pane_ids[0])
        await pilot.wait_for_scheduled_animations()
        assert _active_pane(app) == pane_ids[2]
        assert pane_ids[0] not in main._mru_history.get(leaf_id, [])

        # Step 6: setActive(2), close 2 → 3 active
        tc.active = pane_ids[1]
        await pilot.wait_for_scheduled_animations()
        await main.action_close_code_editor(pane_ids[1])
        await pilot.wait_for_scheduled_animations()
        assert _active_pane(app) == pane_ids[2]
        assert pane_ids[1] not in main._mru_history.get(leaf_id, [])

        # Step 7: Close 3 → no active
        await main.action_close_code_editor(pane_ids[2])
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 0


async def test_mru_close_inactive_tab_keeps_active(workspace: Path):
    """Closing a non-active tab does not change the active tab (MRU mode)."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_ids = await _open_n_files(app, pilot, workspace, 4)
        tc = app.main_view.tabbed_content
        tc.active = pane_ids[1]
        await pilot.wait_for_scheduled_animations()

        # Close file4 (not active) — file2 should remain active
        await app.main_view.action_close_code_editor(pane_ids[3])
        await pilot.wait_for_scheduled_animations()
        assert _active_pane(app) == pane_ids[1]


async def test_mru_close_only_tab(workspace: Path):
    """Closing the only tab leaves no active (MRU mode)."""
    f = workspace / "solo.py"
    f.write_text("# solo\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        pane_id = _active_pane(app)
        assert pane_id is not None
        await app.main_view.action_close_code_editor(pane_id)
        await pilot.wait_for_scheduled_animations()
        assert _tab_count(app) == 0
