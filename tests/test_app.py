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
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace)
    notifications: list[str] = []
    original_notify = app.notify

    def capture_notify(msg, **kwargs):
        notifications.append(msg)
        return original_notify(msg, **kwargs)

    app.notify = capture_notify  # type: ignore[method-assign]  # monkey-patch to capture notifications in test

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

        app.action_close_all_files()
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
        app.action_change_language_cmd()
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
            "Goto line",
            "Close tab",
            "New file",
            "Toggle sidebar",
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
            "Goto line",
            "Close tab",
            "New file",
            "Toggle sidebar",
        ]

        # Sidebar-focused: at minimum app-level bindings in correct order
        assert "New file" in sidebar_descs
        assert "Toggle sidebar" in sidebar_descs
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
            "Goto line",
            "Close tab",
            "New file",
            "Toggle sidebar",
        ]


async def test_action_order_covers_all_visible_bindings():
    """ACTION_ORDER includes every show=True action from all BINDINGS sources."""
    from textual_code.widgets.main_view import MainView
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea
    from textual_code.widgets.ordered_footer import OrderedFooter

    visible_actions: set[str] = set()
    for cls in (TextualCode, MainView, MultiCursorTextArea):
        for binding in cls.BINDINGS:
            if binding.show:
                visible_actions.add(binding.action)

    missing = visible_actions - set(OrderedFooter.ACTION_ORDER)
    assert not missing, f"ACTION_ORDER is missing actions: {missing}"

    stale = set(OrderedFooter.ACTION_ORDER) - visible_actions
    assert not stale, f"ACTION_ORDER has stale actions: {stale}"
