from collections.abc import Iterable
from functools import partial
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.events import Ready
from textual.message import Message
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Static,
    TabbedContent,
    TabPane,
)

from textual_code.modals import (
    UnsavedChangeQuitModalResult,
    UnsavedChangeQuitModalScreen,
)
from textual_code.widgets.code_editor import CodeEditor
from textual_code.widgets.explorer import Explorer
from textual_code.widgets.sidebar import Sidebar


class MainContent(Static):
    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+w", "close", "Close tab", priority=True),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.opened_pane_ids: set[str] = set()
        self.opened_files: dict[Path, str] = {}

    def compose(self) -> ComposeResult:
        yield TabbedContent()

    def is_opened_pane(self, pane_id: str):
        return pane_id in self.opened_pane_ids

    def _pane_id_from_path(self, path: Path) -> str | None:
        return self.opened_files.get(path, None)

    async def _open_new_pane(self, pane_id: str, pane: TabPane) -> bool:
        """
        Open a new pane if it is not already opened.

        Returns True if a new pane was opened.
        """
        if self.is_opened_pane(pane_id):
            return False
        self.opened_pane_ids.add(pane_id)
        await self.tabbed_content.add_pane(pane)
        return True

    async def close_pane(self, pane_id: str) -> None:
        await self.tabbed_content.remove_pane(pane_id)
        self.opened_pane_ids.remove(pane_id)

    async def add_code_editor_pane(self, path: Path | None = None) -> str:
        """
        Add a new code editor pane.

        Returns the pane_id.

        If a path is provided, open the file in the code-editor.
        Otherwise, open a new empty code-editor.

        If the pane is already opened, it will not be opened again.
        """

        if path is not None:
            existing_pane_id = self._pane_id_from_path(path)
            if existing_pane_id is None:
                pane_id = CodeEditor.generate_pane_id()
            else:
                pane_id = existing_pane_id
        else:
            pane_id = CodeEditor.generate_pane_id()

        if self.is_opened_pane(pane_id):
            return pane_id

        pane = TabPane(
            "...",  # temporary title, will be updated later
            CodeEditor(pane_id=pane_id, path=path),
            id=pane_id,
        )
        if path is not None:
            self.opened_files[path] = pane_id
        await self._open_new_pane(pane_id, pane)
        return pane_id

    def get_active_code_editor(self) -> CodeEditor | None:
        active_pane_id = self.tabbed_content.active
        if not active_pane_id:
            return None
        active_pane = self.tabbed_content.get_pane(active_pane_id)
        return active_pane.query_one(CodeEditor)

    def has_unsaved_pane(self) -> bool:
        for pane_id in list(self.opened_pane_ids):
            pane = self.tabbed_content.get_pane(pane_id)
            code_editor = pane.query_one(CodeEditor)
            if code_editor.text != code_editor.initial_text:
                return True
        return False

    async def action_open_code_editor(
        self, path: Path | None = None, focus: bool = True
    ) -> None:
        pane_id = await self.add_code_editor_pane(path)
        self.tabbed_content.active = pane_id
        if focus:
            editor = self.tabbed_content.get_pane(pane_id).query_one(CodeEditor)

            # We need to call_later because the editor is not composed yet
            editor.call_later(editor.action_focus)

    async def action_close_code_editor(self, pane_id: str) -> None:
        await self.close_pane(pane_id)

        # Remove the file from the opened_files dict
        self.opened_files = {k: v for k, v in self.opened_files.items() if v != pane_id}

    def action_save(self):
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_save()

    def action_close(self):
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_close()

    @on(CodeEditor.TitleChanged)
    def code_editor_title_changed(self, event: CodeEditor.TitleChanged):
        if self.is_opened_pane(event.control.pane_id):
            self.tabbed_content.get_tab(
                event.control.pane_id
            ).label = event.control.title

    @on(CodeEditor.SavedAs)
    def code_editor_saved_as(self, event: CodeEditor.SavedAs):
        if event.control.path is None:
            raise ValueError("CodeEditor.SavedAs event must have a path")
        self.opened_files[event.control.path] = event.control.pane_id

    @on(CodeEditor.Closed)
    async def code_editor_closed(self, event: CodeEditor.Closed):
        await self.action_close_code_editor(event.control.pane_id)

    @on(CodeEditor.Deleted)
    async def code_editor_deleted(self, event: CodeEditor.Deleted):
        await self.action_close_code_editor(event.control.pane_id)

    @property
    def tabbed_content(self) -> TabbedContent:
        return self.query_one(TabbedContent)


class TextualCode(App):
    class ReloadExplorerRequested(Message):
        def __init__(self) -> None:
            super().__init__()

    CSS_PATH = "style.tcss"

    BINDINGS = [Binding("ctrl+n", "new_editor", "New file")]

    def __init__(
        self, workspace_path: Path, with_open_file: Path | None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.workspace_path = workspace_path
        self.with_open_file = with_open_file

    def compose(self) -> ComposeResult:
        yield Sidebar(workspace_path=self.workspace_path)
        yield MainContent()
        yield Footer()

    @on(Ready)
    async def readied(self, event: Ready):
        if self.with_open_file is not None:
            await self.main_content.action_open_code_editor(
                path=self.with_open_file, focus=True
            )

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Reload explorer", "Reload the explorer", self.action_reload_explorer
        )
        yield SystemCommand("Save file", "Save the current file", self.action_save_file)
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

    def action_reload_explorer(self) -> None:
        self.call_next(self.sidebar.explorer.directory_tree.reload)

    def action_save_file(self) -> None:
        code_editor = self.main_content.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_save)
        else:
            self.notify("No file to save. Please open a file first.", severity="error")

    def action_save_file_as(self) -> None:
        code_editor = self.main_content.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_save_as)
        else:
            self.notify("No file to save. Please open a file first.", severity="error")

    async def action_new_editor(self) -> None:
        self.call_next(
            partial(self.main_content.action_open_code_editor, path=None, focus=True)
        )

    def action_close_file(self) -> None:
        code_editor = self.main_content.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_close)
        else:
            self.notify("No file to close. Please open a file first.", severity="error")

    def action_delete_file(self) -> None:
        code_editor = self.main_content.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_delete)
        else:
            self.notify(
                "No file to delete. Please open a file first.", severity="error"
            )

    def action_quit(self) -> None:
        if self.main_content.has_unsaved_pane():

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
        self.call_next(
            partial(
                self.main_content.action_open_code_editor, path=event.path, focus=True
            )
        )

    @on(CodeEditor.Saved)
    @on(CodeEditor.SavedAs)
    @on(CodeEditor.Deleted)
    def on_file_changed(
        self, event: CodeEditor.Saved | CodeEditor.SavedAs | CodeEditor.Deleted
    ):
        self.action_reload_explorer()

    @on(ReloadExplorerRequested)
    def reload_explorer_requested(self, event: ReloadExplorerRequested):
        self.action_reload_explorer()

    @property
    def main_content(self) -> MainContent:
        return self.query_one(MainContent)

    @property
    def sidebar(self) -> Sidebar:
        return self.query_one(Sidebar)

    @property
    def footer(self) -> Footer:
        return self.query_one(Footer)
