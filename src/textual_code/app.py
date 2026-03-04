from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.command import CommandPalette
from textual.events import Ready
from textual.message import Message
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Static,
    TabbedContent,
    TabPane,
)

from textual_code.commands import (
    create_create_file_or_dir_command_provider,
    create_open_file_command_provider,
)
from textual_code.modals import (
    UnsavedChangeQuitModalResult,
    UnsavedChangeQuitModalScreen,
)
from textual_code.widgets.code_editor import CodeEditor
from textual_code.widgets.explorer import Explorer
from textual_code.widgets.sidebar import Sidebar


class MainView(Static):
    """
    Main view of the app with a tabbed content for code editors.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+shift+s", "save_all", "Save all"),
        Binding("ctrl+w", "close", "Close tab", priority=True),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # a set of opened pane ids
        self.opened_pane_ids: set[str] = set()
        # a dict of opened file paths with their pane_id
        self.opened_files: dict[Path, str] = {}

    def compose(self) -> ComposeResult:
        yield TabbedContent()

    def is_opened_pane(self, pane_id: str) -> bool:
        """
        Check if a pane is already opened by its pane_id.
        """
        return pane_id in self.opened_pane_ids

    def pane_id_from_path(self, path: Path) -> str | None:
        """
        Get the pane_id of a file path if it is already opened.

        Returns None if the file is not opened.
        """
        return self.opened_files.get(path, None)

    async def open_new_pane(self, pane_id: str, pane: TabPane) -> bool:
        """
        Open a new pane if it is not already opened.

        Returns True if a new pane was opened.

        If the pane is already opened, it will not be opened again and return False.
        """
        if self.is_opened_pane(pane_id):
            return False
        self.opened_pane_ids.add(pane_id)
        await self.tabbed_content.add_pane(pane)
        return True

    async def close_pane(self, pane_id: str) -> bool:
        """
        Close a pane by its pane_id.

        Returns True if the pane was closed.

        If the pane is not opened, it will not be closed and return False.
        """
        if not self.is_opened_pane(pane_id):
            return False
        await self.tabbed_content.remove_pane(pane_id)
        self.opened_pane_ids.remove(pane_id)
        return True

    def focus_pane(self, pane_id: str) -> bool:
        """
        Focus a pane by its pane_id.

        Returns True if the pane was focused.
        """

        if not self.is_opened_pane(pane_id):
            return False

        # if the pane is not active, activate it first
        if self.tabbed_content.active != pane_id:
            self.tabbed_content.active = pane_id

        self.tabbed_content.get_pane(pane_id).focus()
        return True

    async def open_code_editor_pane(self, path: Path | None = None) -> str:
        """
        Open a new code editor pane.

        Returns the pane_id of the new pane.

        If a path is provided, open the file in the code editor.
        Otherwise, open a new empty code editor.

        If the pane is already opened, it will not be opened again.
        However, if the opened pane is not focused, it will be focused.
        """

        # get the pane_id for the file path, or generate a new one
        if path is None:
            pane_id = CodeEditor.generate_pane_id()
        else:
            existing_pane_id = self.pane_id_from_path(path)
            if existing_pane_id is None:
                pane_id = CodeEditor.generate_pane_id()
            else:
                pane_id = existing_pane_id

        if self.is_opened_pane(pane_id):
            # if the pane is already opened, focus it
            self.focus_pane(pane_id)
            return pane_id

        # create a new code editor pane
        pane = TabPane(
            "...",  # temporary title, will be updated later
            CodeEditor(pane_id=pane_id, path=path),
            id=pane_id,
        )
        if path is not None:
            self.opened_files[path] = pane_id
        await self.open_new_pane(pane_id, pane)
        return pane_id

    def get_active_code_editor(self) -> CodeEditor | None:
        """
        Get the active code editor widget.

        Returns None if no code editor is active.
        """
        active_pane_id = self.tabbed_content.active
        if not active_pane_id:
            return None
        active_pane = self.tabbed_content.get_pane(active_pane_id)
        return active_pane.query_one(CodeEditor)

    def has_unsaved_pane(self) -> bool:
        """
        Check if there is any unsaved code editor pane.
        """
        for pane_id in list(self.opened_pane_ids):
            pane = self.tabbed_content.get_pane(pane_id)
            code_editor = pane.query_one(CodeEditor)
            if code_editor.text != code_editor.initial_text:
                return True
        return False

    async def action_open_code_editor(
        self,
        path: Path | None = None,
        focus: bool = True,
    ) -> None:
        """
        Open a code editor pane with the given file path.

        Parameters:
            path: The file path to open in the code editor.
            focus: If True, focus the code editor after opening.
        """
        pane_id = await self.open_code_editor_pane(path)
        self.tabbed_content.active = pane_id
        if focus:
            editor = self.tabbed_content.get_pane(pane_id).query_one(CodeEditor)
            editor.action_focus()

    async def action_close_code_editor(self, pane_id: str) -> None:
        """
        Close a code editor pane by its pane_id.
        """
        await self.close_pane(pane_id)

        # remove the file from the opened_files dict
        self.opened_files = {k: v for k, v in self.opened_files.items() if v != pane_id}

    def action_save(self):
        """
        Save file in the active code editor.
        """
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_save()

    def action_save_all(self) -> None:
        """Save all open code editors with unsaved changes."""
        editors = []
        for pane_id in list(self.opened_pane_ids):
            pane = self.tabbed_content.get_pane(pane_id)
            code_editor = pane.query_one(CodeEditor)
            if code_editor.text != code_editor.initial_text:
                editors.append(code_editor)
        # Files with paths first (save synchronously), untitled last (needs modal)
        editors.sort(key=lambda e: e.path is None)
        self._save_next(editors)

    def _save_next(self, editors: list[CodeEditor]) -> None:
        if not editors:
            return
        editor = editors[0]
        remaining = editors[1:]
        if editor.path is not None:
            editor.action_save()
            self._save_next(remaining)
        else:
            self.tabbed_content.active = editor.pane_id
            editor.action_save_as(on_complete=lambda: self._save_next(remaining))

    def action_close(self):
        """
        Close the active code editor.
        """
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_close()

    @on(CodeEditor.TitleChanged)
    def on_code_editor_title_changed(self, event: CodeEditor.TitleChanged):
        # update the tab label when the title of the code editor changes
        if self.is_opened_pane(event.control.pane_id):
            self.tabbed_content.get_tab(
                event.control.pane_id
            ).label = event.control.title

    @on(CodeEditor.SavedAs)
    def on_code_editor_saved_as(self, event: CodeEditor.SavedAs):
        # update the opened_files dict when a file is saved as new file
        if event.control.path is None:
            raise ValueError("CodeEditor.SavedAs event must have a path")
        self.opened_files[event.control.path] = event.control.pane_id

    @on(CodeEditor.Closed)
    async def on_code_editor_closed(self, event: CodeEditor.Closed):
        # close the code editor pane when the code editor is closed
        await self.action_close_code_editor(event.control.pane_id)

    @on(CodeEditor.Deleted)
    async def on_code_editor_deleted(self, event: CodeEditor.Deleted):
        # close the code editor pane when the file is deleted
        await self.action_close_code_editor(event.control.pane_id)

    @property
    def tabbed_content(self) -> TabbedContent:
        return self.query_one(TabbedContent)


class TextualCode(App):
    """
    Textual Code app
    """

    @dataclass
    class ReloadExplorerRequested(Message):
        """
        Message to request reloading the explorer.
        """

    @dataclass
    class OpenFileRequested(Message):
        """
        Message to request opening a file in the code editor.
        """

        # the path to the file to open.
        path: Path

    @dataclass
    class CreateFileOrDirRequested(Message):
        """
        Message to request creating a new file or directory.
        """

        # the path to the file or directory to create.
        path: Path
        # if the path is a directory.
        is_dir: bool

    CSS_PATH = "style.tcss"

    BINDINGS = [Binding("ctrl+n", "new_editor", "New file")]

    def __init__(
        self, workspace_path: Path, with_open_file: Path | None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        # the workspace path to open the explorer
        self.workspace_path = workspace_path
        # the file path to open in the code editor
        # if provided, the file will be opened after the app is ready
        self.with_open_file = with_open_file

    def compose(self) -> ComposeResult:
        yield Sidebar(workspace_path=self.workspace_path)
        yield MainView()
        yield Footer()

    @on(Ready)
    async def on_ready(self, event: Ready):
        # open the file in the code editor if provided as with_open_file
        if self.with_open_file is not None:
            await self.main_view.action_open_code_editor(
                path=self.with_open_file, focus=True
            )

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Reload explorer", "Reload the explorer", self.action_reload_explorer
        )
        yield SystemCommand("Save file", "Save the current file", self.action_save_file)
        yield SystemCommand(
            "Save all files", "Save all open files", self.action_save_all_files
        )
        yield SystemCommand(
            "Save file as",
            "Save the current file as new file",
            self.action_save_file_as,
        )
        yield SystemCommand(
            "New file", "Open empty code editor", self.action_new_editor
        )
        yield SystemCommand(
            "Close file", "Close the current file", self.action_close_file
        )
        yield SystemCommand(
            "Delete file", "Delete the current file", self.action_delete_file
        )
        yield SystemCommand(
            "Open file",
            "Open a file in the code editor",
            self.action_open_file_with_command_palette,
        )
        yield SystemCommand(
            "Create file",
            "Create a new file at a path",
            self.action_create_file_with_command_palette,
        )
        yield SystemCommand(
            "Create directory",
            "Create a new directory at a path",
            self.action_create_directory_with_command_palette,
        )
        yield SystemCommand("Open folder", "Quit the app", self.action_quit)

    def action_save_all_files(self) -> None:
        """Save all open files."""
        self.call_next(self.main_view.action_save_all)

    def action_reload_explorer(self) -> None:
        """
        Reload the explorer directory tree.
        """
        # call with call_next to ensure the command palette is closed
        self.call_next(self.sidebar.explorer.directory_tree.reload)

    def action_save_file(self) -> None:
        """
        Save the file in the active code editor.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            # call with call_next to ensure the command palette is closed
            self.call_next(code_editor.action_save)
        else:
            self.notify("No file to save. Please open a file first.", severity="error")

    def action_save_file_as(self) -> None:
        """
        Save the file in the active code editor as a new file.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            # call with call_next to ensure the command palette is closed
            self.call_next(code_editor.action_save_as)
        else:
            self.notify("No file to save. Please open a file first.", severity="error")

    async def action_new_editor(self) -> None:
        """
        Open a new code editor with an empty file.
        """
        # call with call_next to ensure the command palette is closed
        self.call_next(
            partial(self.main_view.action_open_code_editor, path=None, focus=True)
        )

    def action_close_file(self) -> None:
        """
        Close the file in the active code editor.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            # call with call_next to ensure the command palette is closed
            self.call_next(code_editor.action_close)
        else:
            self.notify("No file to close. Please open a file first.", severity="error")

    def action_delete_file(self) -> None:
        """
        Delete the file in the active code editor.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            # call with call_next to ensure the command palette is closed
            self.call_next(code_editor.action_delete)
        else:
            self.notify(
                "No file to delete. Please open a file first.", severity="error"
            )

    def action_open_file_with_command_palette(self) -> None:
        """
        Open a file in the code editor with the command palette.
        """
        self.push_screen(
            CommandPalette(
                providers=[
                    create_open_file_command_provider(
                        self.workspace_path,
                        post_message_callback=lambda path: self.app.post_message(
                            self.OpenFileRequested(path=path)
                        ),
                    )
                ],
                placeholder="Search for files...",
            ),
        )

    def action_create_file_with_command_palette(self) -> None:
        """
        Create a new file with the command palette.
        """
        self.push_screen(
            CommandPalette(
                providers=[
                    create_create_file_or_dir_command_provider(
                        self.workspace_path,
                        is_dir=False,
                        post_message_callback=lambda path: self.app.post_message(
                            self.CreateFileOrDirRequested(path=path, is_dir=False)
                        ),
                    )
                ],
                placeholder="Enter file path...",
            ),
        )

    def action_create_directory_with_command_palette(self) -> None:
        """
        Create a new directory with the command palette.
        """
        self.push_screen(
            CommandPalette(
                providers=[
                    create_create_file_or_dir_command_provider(
                        self.workspace_path,
                        is_dir=True,
                        post_message_callback=lambda path: self.app.post_message(
                            self.CreateFileOrDirRequested(path=path, is_dir=True)
                        ),
                    )
                ],
                placeholder="Enter directory path...",
            ),
        )

    def action_quit(self) -> None:
        """
        Quit the app.
        """
        if self.main_view.has_unsaved_pane():

            def do_force_quit(
                result: UnsavedChangeQuitModalResult | None,
            ) -> None:
                if result is None or not result.should_quit:
                    return
                self.exit()

            self.push_screen(UnsavedChangeQuitModalScreen(), do_force_quit)
            return
        self.exit()

    @on(Explorer.FileOpenRequested)
    async def on_file_open_requested(self, event: Explorer.FileOpenRequested):
        # open the file in the code editor when requested from the explorer
        await self.main_view.action_open_code_editor(path=event.path, focus=True)

    @on(CodeEditor.Saved)
    @on(CodeEditor.SavedAs)
    @on(CodeEditor.Deleted)
    def on_file_changed(
        self, event: CodeEditor.Saved | CodeEditor.SavedAs | CodeEditor.Deleted
    ):
        # reload the explorer when a file is saved or deleted
        self.action_reload_explorer()

    @on(ReloadExplorerRequested)
    def on_reload_explorer_requested(self, event: ReloadExplorerRequested):
        # reload the explorer when requested
        self.action_reload_explorer()

    @on(OpenFileRequested)
    async def on_open_file_requested(self, event: OpenFileRequested):
        # open the file in the code editor when requested
        await self.main_view.action_open_code_editor(path=event.path, focus=True)

    @on(CreateFileOrDirRequested)
    async def on_create_file_or_dir_requested(self, event: CreateFileOrDirRequested):
        # check if the file or directory already exists
        if event.path.exists():
            self.notify(
                f"{'Directory' if event.is_dir else 'File'}"
                f" already exists: {event.path}",
                severity="error",
            )
            return

        # create the file or directory
        if not event.is_dir:
            try:
                event.path.touch()
            except Exception as e:
                self.notify(
                    f"Failed to create file: {event.path}: {e}", severity="error"
                )
                return
        else:
            try:
                event.path.mkdir(parents=True)
            except Exception as e:
                self.notify(
                    f"Failed to create directory: {event.path}: {e}", severity="error"
                )
                return

        # reload the explorer after creating the file or directory
        self.action_reload_explorer()

        # open the file in the code editor if it is a file
        if not event.is_dir:
            await self.main_view.action_open_code_editor(path=event.path, focus=True)

    @property
    def main_view(self) -> MainView:
        # Use the base screen so this works even when a modal is active
        return self.screen_stack[0].query_one(MainView)

    @property
    def sidebar(self) -> Sidebar:
        # Use the base screen so this works even when a modal is active
        return self.screen_stack[0].query_one(Sidebar)

    @property
    def footer(self) -> Footer:
        return self.query_one(Footer)
