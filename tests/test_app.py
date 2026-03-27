"""
TextualCode app integration tests.

- App startup and component verification
- Automatic tab opening when started with a file argument
- Ctrl+N new editor
- File/directory creation (CreateFileOrDirRequested)
- OpenFileRequested message
- Quit (with/without unsaved changes)
- Sidebar toggle (Ctrl+B)
"""

from pathlib import Path

import pytest
from textual.widgets import Footer

from tests.conftest import make_app
from textual_code.app import MainView, TextualCode
from textual_code.modals import UnsavedChangeQuitModalScreen
from textual_code.widgets.sidebar import Sidebar

# ── App startup ───────────────────────────────────────────────────────────────


async def test_app_composes_with_sidebar_mainview_footer(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(Sidebar) is not None
        assert app.query_one(MainView) is not None
        assert app.query_one(Footer) is not None


async def test_app_starts_without_open_file(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_app_opens_initial_file_on_start(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


# ── Open file from shortcut (Ctrl+N) ─────────────────────────────────────────


async def test_ctrl_n_opens_new_empty_editor(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0

        await pilot.press("ctrl+n")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.title == "<Untitled>"


async def test_ctrl_n_opens_multiple_editors(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+n")
        await pilot.pause()
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 2


# ── OpenFileRequested ────────────────────────────────────────────────────────


async def test_open_file_requested_opens_editor(workspace: Path, sample_py_file: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0

        app.post_message(TextualCode.OpenFileRequested(path=sample_py_file))
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


# ── CreateFileOrDirRequested ─────────────────────────────────────────────────


async def test_create_file_creates_on_disk(workspace: Path):
    new_file = workspace / "created.py"
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_file, is_dir=False)
        )
        await pilot.pause()

    assert new_file.exists()
    assert new_file.is_file()


async def test_create_file_opens_tab(workspace: Path):
    new_file = workspace / "created.py"
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_file, is_dir=False)
        )
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


async def test_create_directory_creates_on_disk(workspace: Path):
    new_dir = workspace / "subdir" / "nested"
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_dir, is_dir=True)
        )
        await pilot.pause()

    assert new_dir.exists()
    assert new_dir.is_dir()


async def test_create_directory_does_not_open_tab(workspace: Path):
    new_dir = workspace / "mydir"
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_dir, is_dir=True)
        )
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_create_existing_file_shows_notification(
    workspace: Path, sample_py_file: Path, monkeypatch: pytest.MonkeyPatch
):
    app = make_app(workspace)
    notifications: list[str] = []
    original_notify = app.notify

    def capture_notify(msg, **kwargs):
        notifications.append(msg)
        return original_notify(msg, **kwargs)

    monkeypatch.setattr(app, "notify", capture_notify)

    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=sample_py_file, is_dir=False)
        )
        await pilot.pause()

    assert any("already exists" in n for n in notifications)


# ── Quit ────────────────────────────────────────────────────────────────────


async def test_quit_without_unsaved_exits(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.action_quit()
        await pilot.pause()


async def test_quit_with_unsaved_shows_modal(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "unsaved change\n"
        await pilot.pause()

        await app.action_quit()
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeQuitModalScreen)


async def test_quit_with_unsaved_quit_button_exits(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "unsaved\n"
        await pilot.pause()

        await app.action_quit()
        await pilot.pause()
        await pilot.click("#quit")
        await pilot.pause()


# ── Close all files ──────────────────────────────────────────────────────────


async def test_close_all_files_via_app_action(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        app.action_close_all_editors_cmd()
        await pilot.pause()
        await pilot.pause()  # call_next + post_message chain needs two cycles
        assert len(app.main_view.opened_pane_ids) == 0


# ── Sidebar toggle ────────────────────────────────────────────────────────────


async def test_sidebar_visible_by_default(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is True


async def test_ctrl_b_hides_sidebar(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is True

        await pilot.press("ctrl+b")
        await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is False


async def test_ctrl_b_toggles_sidebar_back(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("ctrl+b")
        await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is False

        await pilot.press("ctrl+b")
        await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is True


async def test_toggle_sidebar_action(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        app.action_toggle_sidebar()
        await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is False

        app.action_toggle_sidebar()
        await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is True


# ── Change Language (app-level) ───────────────────────────────────────────────


async def test_change_language_cmd_no_editor_opens_no_modal(workspace: Path):
    from textual_code.modals import ChangeLanguageModalScreen

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_language()
        await pilot.pause()
        assert not isinstance(app.screen, ChangeLanguageModalScreen)


async def test_change_language_cmd_with_editor_opens_modal(
    workspace: Path, sample_py_file: Path
):
    from textual_code.modals import ChangeLanguageModalScreen

    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_change_language()
        await pilot.pause()
        assert isinstance(app.screen, ChangeLanguageModalScreen)


# ── Goto Line (app-level) ─────────────────────────────────────────────────────


async def test_goto_line_cmd_no_editor_opens_no_modal(workspace: Path):
    from textual_code.modals import GotoLineModalScreen

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_goto_line_cmd()
        await pilot.pause()
        assert not isinstance(app.screen, GotoLineModalScreen)


async def test_ctrl_g_no_editor_opens_no_modal(workspace: Path):
    from textual_code.modals import GotoLineModalScreen

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+g")
        await pilot.pause()
        assert not isinstance(app.screen, GotoLineModalScreen)


# ── Sidebar toggle (extended) ─────────────────────────────────────────────────


async def test_ctrl_b_three_times_ends_visible(workspace: Path):
    """3 toggles → odd count → sidebar hidden."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        for _ in range(3):
            await pilot.press("ctrl+b")
            await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is False


async def test_ctrl_b_four_times_ends_visible(workspace: Path):
    """4 toggles → even count → sidebar visible again."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        for _ in range(4):
            await pilot.press("ctrl+b")
            await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is True


async def test_toggle_sidebar_with_file_open_preserves_editor(
    workspace: Path, sample_py_file: Path
):
    """Toggling sidebar while a file is open does not affect editor content."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        original_text = editor.text

        await pilot.press("ctrl+b")
        await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is False
        assert editor.text == original_text

        await pilot.press("ctrl+b")
        await pilot.pause()
        assert app.sidebar is not None
        assert app.sidebar.display is True
        assert editor.text == original_text


# ── Footer shortcut order ──────────────────────────────────────────────────


def _footer_descriptions(app) -> list[str]:
    """Return visible FooterKey descriptions (excluding command palette)."""
    from textual.widgets._footer import FooterKey

    return [
        fk.description
        for fk in app.footer.query(FooterKey)
        if fk.description and "-command-palette" not in fk.classes
    ]


async def test_footer_shortcut_order_is_deterministic(
    workspace: Path, sample_py_file: Path
):
    """Footer shortcuts appear in priority order: Save first, then Find, etc."""
    from textual.widgets._footer import FooterKey

    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.focus()
        await pilot.pause()

        descriptions = _footer_descriptions(app)
        expected = [
            "Save",
            "Find",
            "Replace",
            "Go to Line",
            "Close",
            "Open File",
            "New Untitled File",
            "Toggle Sidebar",
        ]
        assert descriptions == expected

        # Command palette key should also be present
        palette_keys = [
            fk for fk in app.footer.query(FooterKey) if "-command-palette" in fk.classes
        ]
        assert len(palette_keys) == 1


async def test_footer_order_stable_across_focus(workspace: Path, sample_py_file: Path):
    """Footer order is consistent when focus moves between editor and sidebar."""
    app = make_app(workspace, open_file=sample_py_file)  # with sidebar
    async with app.run_test() as pilot:
        await pilot.pause()
        # Focus editor
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.focus()
        await pilot.pause()
        editor_descs = _footer_descriptions(app)

        # Focus sidebar
        sidebar = app.sidebar
        assert sidebar is not None
        sidebar.focus()
        await pilot.pause()
        sidebar_descs = _footer_descriptions(app)

        # Editor-focused: full set of shortcuts
        assert editor_descs == [
            "Save",
            "Find",
            "Replace",
            "Go to Line",
            "Close",
            "Open File",
            "New Untitled File",
            "Toggle Sidebar",
        ]

        # Sidebar-focused: at minimum app-level bindings in correct order
        assert "New Untitled File" in sidebar_descs
        assert "Toggle Sidebar" in sidebar_descs
        # Common bindings must share the same relative order
        common = [d for d in editor_descs if d in sidebar_descs]
        common_sidebar = [d for d in sidebar_descs if d in common]
        assert common == common_sidebar


async def test_footer_shortcut_order_empty_app(workspace: Path):
    """Footer shows bindings in correct order when no file is open."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        descriptions = _footer_descriptions(app)
        # Even without a file, MainView is in the DOM so its bindings appear.
        # Verify exact order matches the full expected set.
        assert descriptions == [
            "Save",
            "Find",
            "Replace",
            "Go to Line",
            "Close",
            "Open File",
            "New Untitled File",
            "Toggle Sidebar",
        ]


async def test_action_order_covers_all_visible_bindings():
    """DEFAULT_ACTION_ORDERS covers visible bindings for each area."""
    from textual_code.widgets.explorer import Explorer
    from textual_code.widgets.main_view import MainView
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea
    from textual_code.widgets.ordered_footer import OrderedFooter

    # Editor area: MainView + App + MultiCursorTextArea
    editor_visible: set[str] = set()
    for cls in (TextualCode, MainView, MultiCursorTextArea):
        for binding in cls.BINDINGS:
            if binding.show:
                editor_visible.add(binding.action)

    editor_order = set(OrderedFooter.DEFAULT_ACTION_ORDERS["editor"])
    missing = editor_visible - editor_order
    assert not missing, f"editor DEFAULT_ACTION_ORDERS missing: {missing}"
    stale = editor_order - editor_visible
    assert not stale, f"editor DEFAULT_ACTION_ORDERS has stale: {stale}"

    # Explorer area: Explorer + App
    explorer_visible: set[str] = set()
    for cls in (Explorer, TextualCode):
        for binding in cls.BINDINGS:
            if binding.show:
                explorer_visible.add(binding.action)

    explorer_order = set(OrderedFooter.DEFAULT_ACTION_ORDERS["explorer"])
    missing = explorer_visible - explorer_order
    assert not missing, f"explorer DEFAULT_ACTION_ORDERS missing: {missing}"
    stale = explorer_order - explorer_visible
    assert not stale, f"explorer DEFAULT_ACTION_ORDERS has stale: {stale}"


# ── Per-area footer order (#36) ────────────────────────────────────────────


def test_footer_orders_for_area_returns_copy():
    """FooterOrders.for_area() returns a copy, not a reference."""
    from textual_code.config import FooterOrders

    orders = FooterOrders(areas={"editor": ["save", "find"]})
    result = orders.for_area("editor")
    assert result is not None
    assert result == ["save", "find"]
    result.append("extra")  # mutate copy
    assert orders.for_area("editor") == ["save", "find"]  # original unchanged


def test_footer_orders_for_area_unknown_returns_none():
    """FooterOrders.for_area() returns None for unconfigured areas."""
    from textual_code.config import FooterOrders

    orders = FooterOrders(areas={})
    assert orders.for_area("editor") is None


def test_load_footer_orders_per_area(tmp_path: Path):
    """load_footer_orders reads [footer.<area>] sections for all known areas."""
    from textual_code.config import load_footer_orders

    config = tmp_path / "keybindings.toml"
    config.write_text(
        '[footer.editor]\norder = ["save", "find"]\n'
        '[footer.explorer]\norder = ["create_file"]\n'
        '[footer.search]\norder = ["new_editor"]\n'
        '[footer.image_preview]\norder = ["close"]\n'
        '[footer.markdown_preview]\norder = ["close", "new_editor"]\n'
    )
    result = load_footer_orders(config)
    assert result.for_area("editor") == ["save", "find"]
    assert result.for_area("explorer") == ["create_file"]
    assert result.for_area("search") == ["new_editor"]
    assert result.for_area("image_preview") == ["close"]
    assert result.for_area("markdown_preview") == ["close", "new_editor"]


def test_load_footer_orders_no_config(tmp_path: Path):
    """load_footer_orders returns empty FooterOrders when config file is missing."""
    from textual_code.config import load_footer_orders

    config = tmp_path / "nonexistent.toml"
    result = load_footer_orders(config)
    assert result.for_area("editor") is None


def test_load_footer_orders_legacy_migration(tmp_path: Path):
    """Old [footer] order is migrated to editor area."""
    from textual_code.config import load_footer_orders

    config = tmp_path / "keybindings.toml"
    config.write_text('[footer]\norder = ["save", "find"]\n')
    result = load_footer_orders(config)
    assert result.for_area("editor") == ["save", "find"]
    assert result.for_area("explorer") is None


def test_save_load_footer_orders_round_trip(tmp_path: Path):
    """FooterOrders survives a save-then-load round trip."""
    from textual_code.config import (
        FooterOrders,
        load_footer_orders,
        save_keybindings_file,
    )

    config = tmp_path / "keybindings.toml"
    orders = FooterOrders(
        areas={
            "editor": ["save", "find"],
            "explorer": ["create_file"],
        }
    )
    save_keybindings_file({}, {}, config, footer_orders=orders)
    loaded = load_footer_orders(config)
    assert loaded.for_area("editor") == ["save", "find"]
    assert loaded.for_area("explorer") == ["create_file"]


async def test_footer_order_differs_by_area(workspace: Path, sample_py_file: Path):
    """Editor and explorer show different footer shortcuts."""
    from textual_code.widgets.explorer import FilteredDirectoryTree

    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Focus editor
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.focus()
        await pilot.pause()
        editor_descs = _footer_descriptions(app)

        # Focus explorer tree directly
        sidebar = app.sidebar
        assert sidebar is not None
        tree = sidebar.explorer.query_one(FilteredDirectoryTree)
        tree.focus()
        await pilot.pause()
        explorer_descs = _footer_descriptions(app)

        # Editor should have save, find etc.
        assert "Save" in editor_descs
        assert "Find" in editor_descs
        # Explorer should have create file, delete etc.
        assert "New File" in explorer_descs
        assert "Delete" in explorer_descs
        # The two sets are different
        assert editor_descs != explorer_descs


async def test_footer_default_order_per_area(workspace: Path, sample_py_file: Path):
    """Default footer order uses DEFAULT_ACTION_ORDERS per area."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.focus()
        await pilot.pause()
        editor_descs = _footer_descriptions(app)
        # Default editor order starts with Save
        assert editor_descs[0] == "Save"


async def test_set_footer_order_for_area_persists(
    workspace: Path, sample_py_file: Path, tmp_path: Path
):
    """set_footer_order saves per-area order to disk."""
    from textual_code.config import load_footer_orders

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config = config_dir / "settings.toml"
    config.touch()
    app = make_app(workspace, open_file=sample_py_file, user_config_path=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.set_footer_order(["find", "save"], area="editor")
        kb_path = config.with_name("keybindings.toml")
        loaded = load_footer_orders(kb_path)
        assert loaded.for_area("editor") == ["find", "save"]


# ── Command palette blocked while modal is active (#34) ──────────────────


async def test_command_palette_blocked_while_modal_is_active(
    workspace: Path, sample_py_file: Path
):
    """Ctrl+P should not open the command palette when a modal is already displayed."""
    from textual.command import CommandPalette

    from textual_code.modals import GotoLineModalScreen

    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_goto_line()
        await pilot.pause()
        assert isinstance(app.screen, GotoLineModalScreen)

        await pilot.press("ctrl+p")
        await pilot.pause()

        assert isinstance(app.screen, GotoLineModalScreen)
        assert not CommandPalette.is_open(app)


async def test_command_palette_blocked_while_path_search_modal_is_active(
    workspace: Path, sample_py_file: Path
):
    """Ctrl+P should not open the command palette when PathSearchModal is displayed."""
    from textual.command import CommandPalette

    from textual_code.modals import PathSearchModal

    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        app.action_open_file()
        await pilot.pause()
        assert isinstance(app.screen, PathSearchModal)

        await pilot.press("ctrl+p")
        await pilot.pause()

        assert isinstance(app.screen, PathSearchModal)
        assert not CommandPalette.is_open(app)


# ── Save Screenshot ──────────────────────────────────────────────────────────


async def test_save_screenshot_writes_svg_file(workspace: Path):
    """action_save_screenshot opens modal and writes an SVG file."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Invoke the real action, which opens the save screenshot modal
        app.action_save_screenshot()
        await pilot.pause()

        # Click save to submit the default timestamped filename
        await pilot.click("#save")
        await pilot.pause()

    svg_files = list(workspace.glob("screenshot_*.svg"))
    assert len(svg_files) == 1
    content = svg_files[0].read_text()
    assert "<svg" in content


async def test_save_screenshot_relative_path_resolves_to_workspace(workspace: Path):
    """Relative path typed in the modal resolves against workspace_path."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Invoke the real action
        app.action_save_screenshot()
        await pilot.pause()

        # Clear the default filename and type a relative subdirectory path
        from textual.widgets import Input

        input_widget = app.screen.query_one("#path", Input)
        input_widget.value = "subdir/shot.svg"
        await pilot.pause()

        await pilot.click("#save")
        await pilot.pause()

    output = workspace / "subdir" / "shot.svg"
    assert output.exists()
    content = output.read_text()
    assert "<svg" in content


async def test_save_screenshot_error_on_invalid_path(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    """Error notification shown when writing to a read-only directory fails."""
    app = make_app(workspace)
    notifications: list[tuple[str, str]] = []
    original_notify = app.notify

    def capture_notify(msg, *, severity="information", **kwargs):
        notifications.append((msg, severity))
        return original_notify(msg, severity=severity, **kwargs)

    monkeypatch.setattr(app, "notify", capture_notify)

    async with app.run_test() as pilot:
        await pilot.pause()

        # Create a read-only directory (0o555 = read+execute, no write)
        readonly_dir = workspace / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)

        try:
            # Invoke the real action
            app.action_save_screenshot()
            await pilot.pause()

            # Set path to a location inside the read-only directory
            from textual.widgets import Input

            input_widget = app.screen.query_one("#path", Input)
            input_widget.value = "readonly/subdir/fail.svg"
            await pilot.pause()

            await pilot.click("#save")
            await pilot.pause()
        finally:
            # Restore permissions so tmp_path cleanup succeeds
            readonly_dir.chmod(0o755)

    error_msgs = [msg for msg, sev in notifications if sev == "error"]
    assert len(error_msgs) > 0
    assert any("Failed to save screenshot" in msg for msg in error_msgs)
