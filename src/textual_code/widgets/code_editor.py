from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from textual import on
from textual.app import ComposeResult
from textual.events import Mount
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Label, Static, TextArea

from textual_code.modals import (
    DeleteFileModalResult,
    DeleteFileModalScreen,
    SaveAsModalResult,
    SaveAsModalScreen,
    UnsavedChangeModalResult,
    UnsavedChangeModalScreen,
)


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

        self.set_reactive(CodeEditor.path, path)
        self.set_reactive(CodeEditor.language, language)

    def compose(self) -> ComposeResult:
        yield Label(
            str(self.path) if self.path else "",
            id="path",
        )
        yield Button(
            self.language or "plain",
            variant="default",
            id="language",
        )

    def watch_path(self, path: Path | None):
        self.path_view.update(str(path) if path else "")

    def watch_language(self, language: str | None):
        self.language_button.label = language or "plain"

    @property
    def path_view(self) -> Label:
        return self.query_one("#path", Label)

    @property
    def language_button(self) -> Button:
        return self.query_one("#language", Button)


class CodeEditor(Static):
    pane_id: reactive[str] = reactive("", init=False)
    path: reactive[Path | None] = reactive(None, init=False)
    initial_text: reactive[str] = reactive("", init=False)
    text: reactive[str] = reactive("", init=False)
    title: reactive[str] = reactive("...", init=False)
    language: reactive[str | None] = reactive(None, init=False)

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

    @dataclass
    class TitleChanged(Message):
        code_editor: "CodeEditor"

        @property
        def control(self) -> "CodeEditor":
            return self.code_editor

    @dataclass
    class Saved(Message):
        code_editor: "CodeEditor"

        @property
        def control(self) -> "CodeEditor":
            return self.code_editor

    @dataclass
    class SavedAs(Message):
        code_editor: "CodeEditor"

        @property
        def control(self) -> "CodeEditor":
            return self.code_editor

    @dataclass
    class Closed(Message):
        code_editor: "CodeEditor"

        @property
        def control(self) -> "CodeEditor":
            return self.code_editor

    @dataclass
    class Deleted(Message):
        code_editor: "CodeEditor"

        @property
        def control(self) -> "CodeEditor":
            return self.code_editor

    @classmethod
    def generate_pane_id(cls) -> str:
        return f"pane-code-editor-{uuid4().hex}"

    def __init__(self, pane_id: str, path: Path | None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
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
        yield TextArea.code_editor(
            text=self.initial_text,
            language=self.language,
        )
        yield CodeEditorFooter(
            path=self.path,
            language=self.language,
        )

    @on(Mount)
    def mounted(self, event: Mount):
        self.update_title()
        self.load_language_from_path(self.path)

    def update_title(self) -> None:
        is_changed = False
        if self.text != self.initial_text:
            is_changed = True
        name = "<Untitled>"
        if self.path is not None:
            name = self.path.name
        self.title = f"{name}{'*' if is_changed else ''}"

    def load_language_from_path(self, path: Path | None):
        if path is None:
            self.language = None
            return
        extension = path.suffix.lstrip(".")
        self.language = self.LANGUAGE_EXTENSIONS.get(extension, None)

    def replace_initial_text(self, initial_text: str):
        self.update_title()
        self.editor.replace(
            initial_text,
            self.editor.document.start,
            self.editor.document.end,
        )

    def watch_title(self, title: str):
        self.post_message(
            self.TitleChanged(
                code_editor=self,
            )
        )

    def watch_text(self, text: str):
        self.update_title()

    def watch_initial_text(self, initial_text: str):
        self.update_title()
        self.replace_initial_text(initial_text)

    def watch_path(self, path: Path | None):
        self.update_title()
        self.load_language_from_path(path)
        self.footer.path = path

    def watch_language(self, language: str | None):
        self.editor.language = language
        self.footer.language = language

    def action_save(self) -> None:
        if self.path is None:
            self.action_save_as()
        else:
            try:
                with self.path.open("w") as f:
                    f.write(self.text)
                self.initial_text = self.text
                self.notify("File saved", severity="information")
                self.post_message(
                    self.Saved(
                        code_editor=self,
                    )
                )
                return
            except Exception as e:
                self.notify(f"Error saving file: {e}", severity="error")
                return

    def action_save_as(self) -> None:
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
                self.post_message(
                    self.SavedAs(
                        code_editor=self,
                    )
                )
                self.notify(f"File saved: {self.path}", severity="information")
            except Exception as e:
                self.notify(f"Error saving file: {e}", severity="error")
                return

        self.app.push_screen(SaveAsModalScreen(), do_save_as)
        return

    def action_close(self) -> None:
        def do_unsaved_changes(result: UnsavedChangeModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return

            if result.should_save is None:
                self.notify("Please select an option", severity="error")
                return

            if result.should_save:
                self.action_save()
                if self.text == self.initial_text:
                    self.post_message(
                        self.Closed(
                            code_editor=self,
                        )
                    )
                    return
                else:
                    # file was not saved, so don't close the editor
                    return
            else:
                self.post_message(
                    self.Closed(
                        code_editor=self,
                    )
                )
                return

        if self.text != self.initial_text:
            # There are unsaved changes, ask the user if they want to save the changes
            self.app.push_screen(UnsavedChangeModalScreen(), do_unsaved_changes)
            return

        self.post_message(
            self.Closed(
                code_editor=self,
            )
        )
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
                    self.post_message(
                        self.Deleted(
                            code_editor=self,
                        )
                    )
                except Exception as e:
                    self.notify(f"Error deleting file: {e}", severity="error")

        self.app.push_screen(DeleteFileModalScreen(self.path), do_delete)

    def action_focus(self) -> None:
        self.editor.focus()

    @on(TextArea.Changed)
    def text_changed(self, event: TextArea.Changed):
        self.text = event.control.text

    @property
    def editor(self) -> TextArea:
        return self.query_one(TextArea)

    @property
    def footer(self) -> CodeEditorFooter:
        return self.query_one(CodeEditorFooter)
