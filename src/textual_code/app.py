from collections.abc import Iterable
from functools import partial
from pathlib import Path
from typing import cast
from uuid import uuid4

from textual import on
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.events import Mount
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Label,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from textual_code.modals import (
    DeleteFileModalResult,
    DeleteFileModalScreen,
    SaveAsModalResult,
    SaveAsModalScreen,
    UnsavedChangeModalResult,
    UnsavedChangeModalScreen,
    UnsavedChangeQuitModalResult,
    UnsavedChangeQuitModalScreen,
)


class Explorer(Static):
    class FileOpened(Message):
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path.resolve()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.directory_tree: DirectoryTree | None = None

    def compose(self) -> ComposeResult:
        self.directory_tree = DirectoryTree(Path())
        self.directory_tree.show_root = False
        yield self.directory_tree

    @on(DirectoryTree.FileSelected)
    def file_selected(self, event: DirectoryTree.FileSelected):
        event.stop()
        self.post_message(self.FileOpened(path=event.path.resolve()))


class Sidebar(Static):
    class FileOpened(Message):
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path.resolve()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tabbed_content: TabbedContent | None = None
        self.explorer_pane: TabPane | None = None
        self.explorer: Explorer | None = None

    def compose(self) -> ComposeResult:
        self.tabbed_content = TabbedContent()
        self.explorer_pane = TabPane("Explorer")
        self.explorer = Explorer(id="explorer")

        with self.tabbed_content, self.explorer_pane:
            yield self.explorer

    @on(Explorer.FileOpened)
    def file_opened(self, event: Explorer.FileOpened):
        event.stop()
        self.post_message(self.FileOpened(path=event.path))


class CodeEditorFooter(Static):
    path: reactive[Path | None] = reactive(None)
    language: reactive[str | None] = reactive(None)

    def __init__(
        self,
        path: Path | None,
        language: str | None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.path_view: Label | None = None
        self.language_button: Button | None = None

        self.set_reactive(CodeEditor.path, path)
        self.set_reactive(CodeEditor.language, language)

    def compose(self) -> ComposeResult:
        self.path_view = Label(str(self.path) if self.path else "", id="path")
        self.language_button = Button(
            self.language or "plain", variant="default", id="language"
        )
        yield self.path_view
        yield self.language_button

    def watch_path(self, path: Path | None):
        if self.path_view is not None:
            self.path_view.update(str(path) if path else "")

    def watch_language(self, language: str | None):
        if self.language_button is not None:
            self.language_button.label = language or "plain"


class CodeEditor(Static):
    pane_id: reactive[str] = reactive("")
    path: reactive[Path | None] = reactive(None)
    initial_text: reactive[str] = reactive("")
    text: reactive[str] = reactive("")
    title: reactive[str] = reactive("...")
    language: reactive[str | None] = reactive(None)

    LANGUAGE_EXTENSIONS = {
        "py": "python",
        "json": "json",
        "md": "markdown",
        "markdown": "markdown",
        "yaml": "yaml",
        "yml": "yaml",
        "toml": "toml",
        "rs": "rust",
        "html": "html",
        "htm": "html",
        "css": "css",
        "xml": "xml",
        "regex": "regex",
        "sql": "sql",
        "js": "javascript",
        "java": "java",
        "sh": "bash",
        "go": "go",
    }

    class TitleChanged(Message):
        def __init__(self, pane_id: str, title: str) -> None:
            super().__init__()
            self.pane_id = pane_id
            self.title = title

    class Saved(Message):
        def __init__(self, pane_id: str) -> None:
            super().__init__()
            self.pane_id = pane_id

    class SavedAs(Message):
        def __init__(self, pane_id: str, path: Path) -> None:
            super().__init__()
            self.pane_id = pane_id
            self.path = path

    class Closed(Message):
        def __init__(self, pane_id: str) -> None:
            super().__init__()
            self.pane_id = pane_id

    class Deleted(Message):
        def __init__(self, pane_id: str) -> None:
            super().__init__()
            self.pane_id = pane_id

    class FocusRequsted(Message):
        def __init__(self) -> None:
            super().__init__()

    class SaveRequested(Message):
        def __init__(self) -> None:
            super().__init__()

    class SaveAsRequested(Message):
        def __init__(self) -> None:
            super().__init__()

    class CloseRequested(Message):
        def __init__(self) -> None:
            super().__init__()

    class DeleteRequested(Message):
        def __init__(self) -> None:
            super().__init__()

    @classmethod
    def generate_pane_id(cls) -> str:
        return f"pane-code-editor-{uuid4().hex}"

    def __init__(self, pane_id: str, path: Path | None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.editor: TextArea | None = None
        self.footer: CodeEditorFooter | None = None

        self.set_reactive(CodeEditor.pane_id, pane_id)
        self.set_reactive(CodeEditor.path, path)
        if path is not None:
            try:
                with path.open() as f:
                    text = f.read()
            except Exception as e:
                text = ""
                self.notify(f"Error reading file: {e}", severity="error")
            self.set_reactive(CodeEditor.initial_text, text)
            self.set_reactive(CodeEditor.text, text)

    def compose(self) -> ComposeResult:
        self.editor = TextArea.code_editor(
            text=self.initial_text, language=self.language
        )
        self.footer = CodeEditorFooter(
            path=self.path,
            language=self.language,
        )
        yield self.editor
        yield self.footer

    @on(Mount)
    def mounted(self, event: Mount):
        # manually trigger the reactive properties to update the UI
        self.watch_path(self.path)

    def replace_initial_text(self, initial_text: str):
        if self.editor is not None:
            self.editor.replace(
                initial_text,
                self.editor.document.start,
                self.editor.document.end,
            )

    def compute_title(self) -> str:
        if not self.is_mounted:
            return "..."
        is_changed = False
        if self.text != self.initial_text:
            is_changed = True
        name = "<Untitled>"
        if self.path is not None:
            name = self.path.name
        return f"{name}{'*' if is_changed else ''}"

    def watch_initial_text(self, initial_text: str):
        self.replace_initial_text(initial_text)

    def watch_title(self, title: str):
        self.post_message(self.TitleChanged(pane_id=self.pane_id, title=title))

    def watch_path(self, path: Path | None):
        if self.footer is not None:
            self.footer.path = path

        if path is None:
            self.language = None
            return
        extension = path.suffix.lstrip(".")
        self.language = self.LANGUAGE_EXTENSIONS.get(extension, None)

    def watch_language(self, language: str | None):
        if self.editor is not None:
            self.editor.language = language
        if self.footer is not None:
            self.footer.language = language

    def action_save(self) -> None:
        """
        Save the file.
        Returns True if the file was saved successfully.
        """
        if self.path is None:
            self.action_save_as()
        else:
            try:
                with self.path.open("w") as f:
                    f.write(self.text)
                self.initial_text = self.text
                self.notify("File saved", severity="information")
                self.post_message(self.Saved(pane_id=self.pane_id))
                self.post_message(TextualCode.ReloadExplorerRequested())
                return
            except Exception as e:
                self.notify(f"Error saving file: {e}", severity="error")
                return

    def action_save_as(self) -> None:
        """
        Save the file as a new file.
        Returns True if the file was saved successfully.
        """

        def do_save_as(result: SaveAsModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return

            if result.file_path is None:
                self.notify("File path cannot be empty", severity="error")
                return

            new_path = Path(result.file_path).resolve()
            if new_path.exists():
                self.notify("File already exists", severity="error")
                return

            try:
                with open(new_path, "w") as f:
                    f.write(self.text)
                self.initial_text = self.text
                self.path = new_path
                self.post_message(self.SavedAs(pane_id=self.pane_id, path=new_path))
                self.post_message(TextualCode.ReloadExplorerRequested())
                self.notify(f"File saved: {self.path}", severity="information")
            except Exception as e:
                self.notify(f"Error saving file: {e}", severity="error")
                return

        self.app.push_screen(SaveAsModalScreen(), do_save_as)
        return

    def action_close(self) -> None:
        """
        Close the code editor.
        Returns True if the code editor was closed.
        """

        def do_unsaved_changes(result: UnsavedChangeModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return

            if result.should_save is None:
                self.notify("Please select an option", severity="error")
                return

            if result.should_save:
                self.action_save()
                if self.text == self.initial_text:
                    self.post_message(self.Closed(pane_id=self.pane_id))
                    return
                else:
                    # file was not saved, so don't close the editor
                    return
            else:
                self.post_message(self.Closed(pane_id=self.pane_id))
                return

        if self.text != self.initial_text:
            # There are unsaved changes, ask the user if they want to save the changes
            self.app.push_screen(UnsavedChangeModalScreen(), do_unsaved_changes)
            return

        self.post_message(self.Closed(pane_id=self.pane_id))
        return

    def action_delete(self) -> None:
        if not self.path:
            self.notify(
                "No file to delete. Please save the file first.", severity="error"
            )
            return

        def do_delete(result: DeleteFileModalResult | None):
            if not result or result.is_cancelled:
                return
            if not self.path:
                self.notify(
                    "No file to delete. Please save the file first.", severity="error"
                )
                return
            if result.should_delete:
                try:
                    self.path.unlink()
                    self.notify(f"File deleted: {self.path}", severity="information")
                    self.post_message(self.Deleted(pane_id=self.pane_id))
                    self.post_message(TextualCode.ReloadExplorerRequested())
                except Exception as e:
                    self.notify(f"Error deleting file: {e}", severity="error")

        self.app.push_screen(DeleteFileModalScreen(self.path), do_delete)

    @on(TextArea.Changed)
    def text_changed(self, event: TextArea.Changed):
        event.stop()
        self.text = event.text_area.text

    @on(FocusRequsted)
    def focus_requested(self, event: FocusRequsted):
        event.stop()
        if not self.is_mounted or self.editor is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return
        self.editor.focus()

    @on(SaveRequested)
    def save_requested(self, event: SaveRequested):
        event.stop()
        if not self.is_mounted or self.editor is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return
        self.action_save()

    @on(SaveAsRequested)
    def save_as_requested(self, event: SaveAsRequested):
        event.stop()
        if not self.is_mounted or self.editor is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return
        self.action_save_as()

    @on(CloseRequested)
    def close_requested(self, event: CloseRequested):
        event.stop()
        if not self.is_mounted or self.editor is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return
        self.action_close()

    @on(DeleteRequested)
    def delete_requested(self, event: DeleteRequested):
        event.stop()
        if not self.is_mounted:
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return
        self.action_delete()


class MainContent(Static):
    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+w", "close", "Close tab", priority=True),
    ]

    class OpenCodeEditorRequested(Message):
        def __init__(self, path: Path | None = None, focus: bool = True) -> None:
            super().__init__()
            self.path = path
            self.focus = focus

    class CloseCodeEditorRequested(Message):
        def __init__(self, pane_id: str) -> None:
            super().__init__()
            self.pane_id = pane_id

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tabbed_content: TabbedContent | None = None
        self.opened_pane_ids: set[str] = set()
        self.opened_files: dict[Path, str] = {}

    def compose(self) -> ComposeResult:
        self.tabbed_content = TabbedContent(id="tabs")
        yield self.tabbed_content

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
        if self.tabbed_content is None:
            raise ValueError("TabbedContent is not mounted")
        await self.tabbed_content.add_pane(pane)
        self.opened_pane_ids.add(pane_id)
        return True

    def close_pane(self, pane_id: str) -> None:
        if self.tabbed_content is None:
            raise ValueError("TabbedContent is not mounted")
        self.tabbed_content.remove_pane(pane_id)
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
        if self.tabbed_content is None:
            raise ValueError("TabbedContent is not mounted")
        active_pane_id = self.tabbed_content.active
        if not active_pane_id:
            return None
        active_pane = self.tabbed_content.get_pane(active_pane_id)
        return active_pane.query_one(CodeEditor)

    def has_unsaved_pane(self) -> bool:
        if self.tabbed_content is None:
            raise ValueError("TabbedContent is not mounted")
        for pane_id in list(self.opened_pane_ids):
            pane = self.tabbed_content.get_pane(pane_id)
            code_editor = pane.query_one(CodeEditor)
            if code_editor.text != code_editor.initial_text:
                return True
        return False

    async def action_open_code_editor(
        self, path: Path | None = None, focus: bool = True
    ) -> None:
        if self.tabbed_content is None:
            raise ValueError("TabbedContent is not mounted")

        pane_id = await self.add_code_editor_pane(path)
        self.tabbed_content.active = pane_id
        if focus:
            self.tabbed_content.get_pane(pane_id).query_one(CodeEditor).post_message(
                CodeEditor.FocusRequsted()
            )

    def action_close_code_editor(self, pane_id: str) -> None:
        self.close_pane(pane_id)

        # Remove the file from the opened_files dict
        self.opened_files = {k: v for k, v in self.opened_files.items() if v != pane_id}

    def action_save(self):
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.post_message(CodeEditor.SaveRequested())

    def action_close(self):
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.post_message(CodeEditor.CloseRequested())

    @on(CodeEditor.TitleChanged)
    def code_editor_title_changed(self, event: CodeEditor.TitleChanged):
        event.stop()
        if not self.is_mounted or self.tabbed_content is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return

        if self.is_opened_pane(event.pane_id):
            self.tabbed_content.get_tab(event.pane_id).label = event.title

    @on(CodeEditor.SavedAs)
    def code_editor_saved_as(self, event: CodeEditor.SavedAs):
        event.stop()
        self.opened_files[event.path] = event.pane_id

    @on(CodeEditor.Closed)
    def code_editor_closed(self, event: CodeEditor.Closed):
        event.stop()
        if not self.is_mounted or self.tabbed_content is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return

        self.post_message(self.CloseCodeEditorRequested(pane_id=event.pane_id))

    @on(CodeEditor.Deleted)
    def code_editor_deleted(self, event: CodeEditor.Deleted):
        event.stop()
        if not self.is_mounted or self.tabbed_content is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return

        self.post_message(self.CloseCodeEditorRequested(pane_id=event.pane_id))

    @on(OpenCodeEditorRequested)
    async def open_code_editor_requested(self, event: OpenCodeEditorRequested) -> None:
        """
        Open a code editor pane and activate it.

        If the path is already opened, use the existing one.
        """
        event.stop()
        if not self.is_mounted or self.tabbed_content is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return

        await self.action_open_code_editor(event.path, event.focus)

    @on(CloseCodeEditorRequested)
    def close_code_editor_requested(self, event: CloseCodeEditorRequested) -> None:
        event.stop()
        if not self.is_mounted or self.tabbed_content is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return

        self.action_close_code_editor(event.pane_id)


class TextualCode(App):
    class ReloadExplorerRequested(Message):
        def __init__(self) -> None:
            super().__init__()

    CSS_PATH = "style.tcss"

    BINDINGS = [Binding("ctrl+n", "new_editor", "New file")]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sidebar: Sidebar | None = None
        self.main_content: MainContent | None = None
        self.footer: Footer | None = None

    def compose(self) -> ComposeResult:
        self.sidebar = Sidebar(id="sidebar")
        self.main_content = MainContent(id="main")
        self.footer = Footer()

        yield self.sidebar
        yield self.main_content
        yield self.footer

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
        if self.sidebar is None:
            raise ValueError("Sidebar is not mounted")
        if self.sidebar.explorer is None:
            raise ValueError("Explorer is not mounted")
        if self.sidebar.explorer.directory_tree is None:
            raise ValueError("DirectoryTree is not mounted")

        self.sidebar.explorer.directory_tree.reload()

    def action_save_file(self) -> None:
        if self.main_content is None:
            raise ValueError("MainContent is not mounted")

        code_editor = self.main_content.get_active_code_editor()
        if code_editor is not None:
            code_editor.post_message(CodeEditor.SaveRequested())
        else:
            self.notify("No file to save. Please open a file first.", severity="error")

    def action_save_file_as(self) -> None:
        if self.main_content is None:
            raise ValueError("MainContent is not mounted")

        code_editor = self.main_content.get_active_code_editor()
        if code_editor is not None:
            code_editor.post_message(CodeEditor.SaveAsRequested())
        else:
            self.notify("No file to save. Please open a file first.", severity="error")

    def action_new_editor(self) -> None:
        if self.main_content is None:
            raise ValueError("MainContent is not mounted")

        self.main_content.post_message(
            MainContent.OpenCodeEditorRequested(path=None, focus=True)
        )

    def action_close_file(self) -> None:
        if self.main_content is None:
            raise ValueError("MainContent is not mounted")

        code_editor = self.main_content.get_active_code_editor()
        if code_editor is not None:
            code_editor.post_message(CodeEditor.CloseRequested())
        else:
            self.notify("No file to close. Please open a file first.", severity="error")

    def action_delete_file(self) -> None:
        if self.main_content is None:
            raise ValueError("MainContent is not mounted")

        code_editor = self.main_content.get_active_code_editor()
        if code_editor is not None:
            code_editor.post_message(CodeEditor.DeleteRequested())
        else:
            self.notify(
                "No file to delete. Please open a file first.", severity="error"
            )

    def action_quit(self) -> None:
        if self.query_one(MainContent).has_unsaved_pane():

            def do_force_quit(
                result: UnsavedChangeQuitModalResult | None,
            ) -> None:
                if result is None or not result.should_quit:
                    return
                self.exit()

            self.push_screen(UnsavedChangeQuitModalScreen(), do_force_quit)
            return
        self.exit()

    @on(Sidebar.FileOpened)
    def file_opened(self, event: Sidebar.FileOpened):
        event.stop()
        if not self.is_mounted or self.main_content is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return

        self.main_content.post_message(
            MainContent.OpenCodeEditorRequested(path=event.path, focus=True)
        )

    @on(ReloadExplorerRequested)
    def reload_explorer_requested(self, event: ReloadExplorerRequested):
        event.stop()
        if not self.is_mounted or self.main_content is None:
            # recycle event if the widget is not mounted yet
            callback = partial(self.post_message, event)
            self.set_timer(delay=0.1, callback=callback)
            return

        self.action_reload_explorer()
