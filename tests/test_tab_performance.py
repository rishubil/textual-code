"""
Tab performance tests for issue #4.

Tests verify the three performance fixes:
- Fix 1: Footer refresh(layout=True) batched to 1 call on tab switch
- Fix 2: Only the active editor is polled (central timer, not per-editor)
- Fix 3: Only the active tab's CodeEditor is mounted in the DOM
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.code_editor import CodeEditor, CodeEditorFooter

# ── Fix 1: Footer batch update ────────────────────────────────────────────────


async def test_footer_labels_correct_after_tab_switch(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """After switching tabs, the footer shows the new editor's metadata."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        # Switch back to py tab
        tc = app.main_view.tabbed_content
        py_pane_id = app.main_view._active_leaf.opened_files[sample_py_file]
        tc.active = py_pane_id
        await pilot.pause()

        footer = app.main_view.query_one(CodeEditorFooter)
        assert footer.path == sample_py_file

        # Switch to json tab
        json_pane_id = app.main_view._active_leaf.opened_files[sample_json_file]
        tc.active = json_pane_id
        await pilot.pause()

        footer = app.main_view.query_one(CodeEditorFooter)
        assert footer.path == sample_json_file


# ── Fix 2: Central polling timer ─────────────────────────────────────────────


async def test_only_active_editor_polled_with_multiple_tabs(
    workspace: Path, sample_py_file: Path, sample_json_file: Path, tmp_path: Path
):
    """With N tabs open, only the active editor's poll methods are called."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        # Get both editors
        main = app.main_view
        py_pane_id = main._active_leaf.opened_files[sample_py_file]
        json_pane_id = main._active_leaf.opened_files[sample_json_file]
        tc = main.tabbed_content

        # Make py tab active (json tab becomes unmounted)
        tc.active = py_pane_id
        await pilot.pause()

        # py is active and mounted; json is unmounted (in _editor_states)
        py_editor = tc.get_pane(py_pane_id).query_one(CodeEditor)
        assert json_pane_id not in [
            e.id for e in tc.get_pane(py_pane_id).query(CodeEditor)
        ]

        py_poll_count = 0
        orig_py_poll = py_editor._poll_file_change

        def track_py():
            nonlocal py_poll_count
            py_poll_count += 1
            orig_py_poll()

        py_editor._poll_file_change = track_py

        # Call the central poll method - only active (py) editor should be polled
        main._poll_active_editor()

        assert py_poll_count == 1
        # json editor is unmounted so it cannot be polled - verify it's not in DOM
        assert len(tc.get_pane(json_pane_id).query(CodeEditor)) == 0


# ── Fix 3: Lazy tab mounting ──────────────────────────────────────────────────


async def test_only_active_tab_has_code_editor_mounted(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """After tab switch, only the active tab has a mounted CodeEditor."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        main = app.main_view
        tc = main.tabbed_content
        py_pane_id = main._active_leaf.opened_files[sample_py_file]
        json_pane_id = main._active_leaf.opened_files[sample_json_file]

        # json tab is currently active (last opened)
        # py tab should have no mounted CodeEditor
        py_pane = tc.get_pane(py_pane_id)
        json_pane = tc.get_pane(json_pane_id)

        assert len(py_pane.query(CodeEditor)) == 0, "Inactive tab should have no editor"
        assert len(json_pane.query(CodeEditor)) == 1, "Active tab should have editor"

        # Switch to py tab
        tc.active = py_pane_id
        await pilot.pause()

        # Now py should have editor, json should not
        assert len(py_pane.query(CodeEditor)) == 1, (
            "Newly active tab should have editor"
        )
        assert len(json_pane.query(CodeEditor)) == 0, (
            "Deactivated tab should have no editor"
        )


async def test_editor_state_restored_after_tab_switch(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """After switching away and back, cursor position and text are restored."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        main = app.main_view
        tc = main.tabbed_content
        py_pane_id = main._active_leaf.opened_files[sample_py_file]

        # Type something in py editor
        await pilot.press("x")
        await pilot.pause()

        # Get the text from the py editor before switching
        py_pane = tc.get_pane(py_pane_id)
        py_text_before = py_pane.query_one(CodeEditor).text

        # Open json tab (switches away from py)
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        # Switch back to py
        tc.active = py_pane_id
        await pilot.pause()

        # py editor should be restored with same text
        py_editor = tc.get_pane(py_pane_id).query_one(CodeEditor)
        assert py_editor.text == py_text_before


async def test_has_unsaved_pane_detects_unmounted_editor_changes(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """has_unsaved_pane() returns True even when the modified editor is unmounted."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        main = app.main_view

        # Modify py editor
        await pilot.press("x")
        await pilot.pause()

        # Open json tab (py editor gets unmounted)
        await main.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        # py editor is now unmounted, but has_unsaved_pane() should still return True
        assert main.has_unsaved_pane() is True


async def test_dom_widget_count_constant_with_multiple_tabs(
    workspace: Path, tmp_path: Path
):
    """DOM widget count does not grow proportionally with tab count."""
    # Create several files
    files = []
    for i in range(5):
        f = workspace / f"file{i}.py"
        f.write_text(f"# file {i}\n")
        files.append(f)

    app = make_app(workspace, light=True, open_file=files[0])
    async with app.run_test() as pilot:
        await pilot.pause()

        count_1 = len(list(app.query("*")))

        for f in files[1:]:
            await app.main_view.action_open_code_editor(path=f)
            await pilot.pause()

        count_5 = len(list(app.query("*")))

        # With lazy mounting: count_5 should be close to count_1
        # Allow some growth for tabs/tab-bar items, but not 16 widgets per tab
        delta = count_5 - count_1
        assert delta < 30, (
            f"DOM grew by {delta} widgets for 4 extra tabs "
            f"(from {count_1} to {count_5}). Expected < 30."
        )


async def test_state_capture_and_restore(workspace: Path, sample_py_file: Path):
    """EditorState captures all fields and CodeEditor.from_state restores them."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        state = editor.capture_state()

        assert state.path == sample_py_file
        assert state.text == editor.text
        assert state.initial_text == editor.initial_text
        assert state.language == editor.language
        assert state.encoding == editor.encoding
        assert state.line_ending == editor.line_ending
        assert state.pane_id == editor.pane_id


async def test_binary_tab_not_lazily_unmounted(workspace: Path):
    """Binary file tabs (no CodeEditor) are not unmounted when switching away."""
    bin_file = workspace / "file.bin"
    bin_file.write_bytes(bytes(range(256)))

    py_file = workspace / "hello.py"
    py_file.write_text("print('hello')\n")

    app = make_app(workspace, light=True, open_file=bin_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        main = app.main_view
        await main.action_open_code_editor(path=py_file)
        await pilot.pause()

        bin_pane_id = main._active_leaf.opened_files[bin_file]
        tc = main.tabbed_content
        bin_pane = tc.get_pane(bin_pane_id)

        # Binary pane has no CodeEditor — should just have its Static widget
        assert len(bin_pane.query(CodeEditor)) == 0
        # It should have its binary notice Static
        from textual.widgets import Static

        statics = list(bin_pane.query(Static))
        assert len(statics) > 0


async def test_save_all_saves_unmounted_editors(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """action_save_all() saves editors that are currently unmounted."""
    app = make_app(workspace, light=True, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        main = app.main_view

        # Modify py editor
        await pilot.press("x")
        await pilot.pause()

        # Open json tab (py editor gets unmounted)
        await main.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        # Save all
        main.action_save_all()
        await pilot.pause()

        # py file should have been saved (its unsaved state is gone)
        assert main.has_unsaved_pane() is False


# ── Issue #15: Custom language tab switch crash ──────────────────────────────


@pytest.mark.parametrize(
    "filename,language",
    [
        ("Main.kt", "kotlin"),
        ("app.ts", "typescript"),
        ("main.c", "c"),
    ],
)
async def test_custom_language_tab_survives_lazy_remount(
    workspace: Path, sample_py_file: Path, filename: str, language: str
):
    """Issue #15: switching back to a custom-language tab must not crash."""
    content = "// sample code\n"
    custom_file = workspace / filename
    custom_file.write_text(content)

    app = make_app(workspace, light=True, open_file=custom_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        main = app.main_view
        tc = main.tabbed_content
        custom_pane_id = main._active_leaf.opened_files[custom_file]

        # Verify custom language is detected
        editor = main.get_active_code_editor()
        assert editor is not None
        assert editor.language == language

        # Open a second tab (triggers lazy unmount of custom-language tab)
        await main.action_open_code_editor(path=sample_py_file)
        await pilot.pause()

        # Verify custom-language tab is unmounted
        custom_pane = tc.get_pane(custom_pane_id)
        assert len(custom_pane.query(CodeEditor)) == 0

        # Switch back to custom-language tab — crash point before fix
        tc.active = custom_pane_id
        await pilot.pause()

        # Verify editor is restored correctly
        restored = main.get_active_code_editor()
        assert restored is not None
        assert restored.language == language
        assert language in restored.editor.available_languages
        assert restored.text == content
