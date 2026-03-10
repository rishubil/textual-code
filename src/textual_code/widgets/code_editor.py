from collections.abc import Callable
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
    ChangeLanguageModalResult,
    ChangeLanguageModalScreen,
    DeleteFileModalResult,
    DeleteFileModalScreen,
    FindModalResult,
    FindModalScreen,
    GotoLineModalResult,
    GotoLineModalScreen,
    ReplaceModalResult,
    ReplaceModalScreen,
    SaveAsModalResult,
    SaveAsModalScreen,
    UnsavedChangeModalResult,
    UnsavedChangeModalScreen,
)


def _text_offset_to_location(text: str, offset: int) -> tuple[int, int]:
    """Convert a character offset in *text* to a (row, col) location."""
    row = col = 0
    for ch in text[:offset]:
        if ch == "\n":
            row += 1
            col = 0
        else:
            col += 1
    return (row, col)


def _find_next(text: str, query: str, cursor_offset: int) -> int:
    """Return character offset of next match from cursor_offset, wrapping around.

    Returns -1 if not found.
    """
    idx = text.find(query, cursor_offset)
    if idx == -1:
        idx = text.find(query, 0)
    return idx


class CodeEditorFooter(Static):
    """
    Footer for the CodeEditor widget.

    It displays the information about the current file being edited.
    """

    # the path of the file
    path: reactive[Path | None] = reactive(None, init=False)
    # the language of the file
    language: reactive[str | None] = reactive(None, init=False)
    # the cursor location (row, col) — zero-based internally, displayed 1-based
    cursor_location: reactive[tuple[int, int]] = reactive((0, 0), init=False)

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
        yield Label(
            "Ln 1, Col 1",
            id="cursor",
        )
        yield Button(
            self.language or "plain",
            variant="default",
            id="language",
        )

    def watch_path(self, path: Path | None) -> None:
        # update the path view with the new path
        self.path_view.update(str(path) if path else "")

    def watch_language(self, language: str | None) -> None:
        # update the language button with the new language
        self.language_button.label = language or "plain"

    def watch_cursor_location(self, location: tuple[int, int]) -> None:
        row, col = location
        self.cursor_view.update(f"Ln {row + 1}, Col {col + 1}")

    @property
    def path_view(self) -> Label:
        return self.query_one("#path", Label)

    @property
    def cursor_view(self) -> Label:
        return self.query_one("#cursor", Label)

    @property
    def language_button(self) -> Button:
        return self.query_one("#language", Button)


class CodeEditor(Static):
    """
    Code editor widget.

    It allows the user to edit code in a text area, with syntax highlighting.
    """

    # the unique ID of the pane.
    # this is used to identify the pane in the MainView.
    pane_id: reactive[str] = reactive("", init=False)
    # the path of the file
    path: reactive[Path | None] = reactive(None, init=False)
    # the initial text of the editor.
    # this is the text that was loaded from the file.
    # if the text is change from the initial text, the editor is considered to have
    # unsaved changes.
    initial_text: reactive[str] = reactive("", init=False)
    # the current text of the editor
    text: reactive[str] = reactive("", init=False)
    # the title of the editor.
    # it will be displayed in the tab of the pane.
    title: reactive[str] = reactive("...", init=False)
    # the language of the file
    language: reactive[str | None] = reactive(None, init=False)

    # mapping of file extensions to language names
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
        """
        Message to notify that the title of the editor has changed.
        """

        code_editor: "CodeEditor"

        @property
        def control(self) -> "CodeEditor":
            return self.code_editor

    @dataclass
    class Saved(Message):
        """
        Message to notify that the file has been saved.
        """

        code_editor: "CodeEditor"

        @property
        def control(self) -> "CodeEditor":
            return self.code_editor

    @dataclass
    class SavedAs(Message):
        """
        Message to notify that the file has been saved as a new file.
        """

        code_editor: "CodeEditor"

        @property
        def control(self) -> "CodeEditor":
            return self.code_editor

    @dataclass
    class Closed(Message):
        """
        Message to notify that the editor has been closed.
        """

        code_editor: "CodeEditor"

        @property
        def control(self) -> "CodeEditor":
            return self.code_editor

    @dataclass
    class Deleted(Message):
        """
        Message to notify that the file has been deleted.
        """

        code_editor: "CodeEditor"

        @property
        def control(self) -> "CodeEditor":
            return self.code_editor

    @classmethod
    def generate_pane_id(cls) -> str:
        """
        Generate a unique pane ID.
        """
        return f"pane-code-editor-{uuid4().hex}"

    def __init__(self, pane_id: str, path: Path | None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.set_reactive(CodeEditor.pane_id, pane_id)
        self.set_reactive(CodeEditor.path, path)

        # if a path is provided, load the file content
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
    def on_mount(self, event: Mount) -> None:
        # update the title of the editor
        self.update_title()
        # update the language of the editor
        self.load_language_from_path(self.path)

    def update_title(self) -> None:
        """
        Update the title of the editor.

        The title is the name of the file, with an asterisk (*) if there are unsaved.
        If the file path is not set, the title is "<Untitled>".
        """
        is_changed = False
        if self.text != self.initial_text:
            is_changed = True
        name = "<Untitled>"
        if self.path is not None:
            name = self.path.name
        self.title = f"{name}{'*' if is_changed else ''}"

    def load_language_from_path(self, path: Path | None) -> None:
        """
        Update the language of the editor based on the file extension.
        """
        if path is None:
            self.language = None
            return
        extension = path.suffix.lstrip(".")
        self.language = self.LANGUAGE_EXTENSIONS.get(extension, None)

    def replace_editor_text(self, text: str) -> None:
        """
        Replace the text in the editor with the new text.
        """

        self.editor.replace(
            text,
            self.editor.document.start,
            self.editor.document.end,
        )

    def watch_title(self, title: str) -> None:
        # notify that the title has changed
        # this will update the tab title in the MainView
        self.post_message(
            self.TitleChanged(
                code_editor=self,
            )
        )

    def watch_text(self, text: str) -> None:
        # update the title, as the text has changed
        self.update_title()

    def watch_initial_text(self, initial_text: str) -> None:
        # update the title, as the initial text has changed
        self.update_title()
        # replace the text in the editor with the new initial text
        self.replace_editor_text(initial_text)

    def watch_path(self, path: Path | None) -> None:
        # update the title, as the path has changed
        self.update_title()

        # update the language based on the new path
        self.load_language_from_path(path)

        # update the path in the footer
        self.footer.path = path

    def watch_language(self, language: str | None):
        # update the language in the editor
        self.editor.language = language
        # update the language in the footer
        self.footer.language = language

    def action_save(self) -> None:
        """
        Save the current text to the file.
        """
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

    def action_save_as(self, *, on_complete: Callable | None = None) -> None:
        """
        Save the current text to a new file.
        """

        def do_save_as(result: SaveAsModalResult | None) -> None:
            if result is None or result.is_cancelled:
                if on_complete:
                    on_complete()
                return

            if result.file_path is None:
                self.notify("File path cannot be empty", severity="error")
                if on_complete:
                    on_complete()
                return

            new_path = Path(result.file_path).resolve()
            if new_path.exists():
                self.notify("File already exists", severity="error")
                if on_complete:
                    on_complete()
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
                if on_complete:
                    on_complete()
                return

            if on_complete:
                on_complete()

        self.app.push_screen(SaveAsModalScreen(), do_save_as)
        return

    def action_close(
        self, *, on_complete: Callable[[bool], None] | None = None
    ) -> None:
        """
        Close the editor.
        """

        def do_unsaved_changes(result: UnsavedChangeModalResult | None) -> None:
            if result is None or result.is_cancelled:
                if on_complete:
                    on_complete(False)
                return

            if result.should_save is None:
                self.notify("Please select an option", severity="error")
                if on_complete:
                    on_complete(False)
                return

            if result.should_save:
                if self.path is None:
                    self.notify(
                        "Cannot save: no file path. Use 'Save As' first.",
                        severity="error",
                    )
                    if on_complete:
                        on_complete(False)
                    return
                self.action_save()
                if self.text == self.initial_text:
                    self.post_message(self.Closed(code_editor=self))
                    if on_complete:
                        on_complete(True)
                    return
                else:
                    if on_complete:
                        on_complete(False)
                    return
            else:
                self.post_message(self.Closed(code_editor=self))
                if on_complete:
                    on_complete(True)
                return

        if self.text != self.initial_text:
            self.app.push_screen(UnsavedChangeModalScreen(), do_unsaved_changes)
            return

        self.post_message(self.Closed(code_editor=self))
        if on_complete:
            on_complete(True)

    def action_delete(self) -> None:
        """
        Delete the file.
        """
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

    def action_goto_line(self) -> None:
        """
        Open the Goto Line modal and move the cursor to the specified location.
        """

        def do_goto(result: GotoLineModalResult | None) -> None:
            if not result or result.is_cancelled or not result.value:
                return
            try:
                parts = result.value.split(":")
                row = int(parts[0]) - 1
                col = int(parts[1]) - 1 if len(parts) > 1 else 0
            except ValueError:
                self.notify(
                    "Invalid location format. Use 'line' or 'line:col'.",
                    severity="error",
                )
                return
            line_count = len(self.editor.document.lines)
            if row < 0 or row >= line_count:
                self.notify(
                    f"Line {row + 1} is out of range (1–{line_count}).",
                    severity="error",
                )
                return
            col = max(0, col)
            self.editor.cursor_location = (row, col)

        self.app.push_screen(GotoLineModalScreen(), do_goto)

    def action_find(self) -> None:
        """
        Open the Find modal and select the first match in the current file.

        Searches from the current cursor position forward. If no match is
        found after the cursor, wraps around to the beginning of the file.
        """

        def do_find(result: FindModalResult | None) -> None:
            if result is None or result.is_cancelled or not result.query:
                return

            query = result.query
            text = self.text

            # Convert cursor position to a character offset
            cursor_row, cursor_col = self.editor.cursor_location
            lines = text.split("\n")
            cursor_offset = (
                sum(len(lines[i]) + 1 for i in range(cursor_row)) + cursor_col
            )

            idx = _find_next(text, query, cursor_offset)

            if idx == -1:
                self.notify(f"'{query}' not found", severity="warning")
                return

            from textual.widgets.text_area import Selection

            self.editor.selection = Selection(
                start=_text_offset_to_location(text, idx),
                end=_text_offset_to_location(text, idx + len(query)),
            )

        self.app.push_screen(FindModalScreen(), do_find)

    def action_replace(self) -> None:
        """
        Open the Replace modal and replace occurrences in the current file.
        """

        def do_replace(result: ReplaceModalResult | None) -> None:
            if result is None or result.is_cancelled or not result.find_query:
                return

            from textual.widgets.text_area import Selection

            find_query = result.find_query
            replace_text = result.replace_text or ""

            if result.action == "replace_all":
                count = self.text.count(find_query)
                if count == 0:
                    self.notify(f"'{find_query}' not found", severity="warning")
                    return
                new_text = self.text.replace(find_query, replace_text)
                self.replace_editor_text(new_text)
                self.notify(f"Replaced {count} occurrence(s)", severity="information")
                return

            # Replace (single): if current selection matches, replace then find next
            sel = self.editor.selection
            text = self.text
            lines = text.split("\n")
            start_offset = (
                sum(len(lines[i]) + 1 for i in range(sel.start[0])) + sel.start[1]
            )
            end_offset = sum(len(lines[i]) + 1 for i in range(sel.end[0])) + sel.end[1]
            selected_text = text[start_offset:end_offset]

            if selected_text == find_query:
                new_text = text[:start_offset] + replace_text + text[end_offset:]
                search_from = start_offset + len(replace_text)
                idx = _find_next(new_text, find_query, search_from)
                self.replace_editor_text(new_text)
                if idx != -1:
                    self.editor.selection = Selection(
                        start=_text_offset_to_location(new_text, idx),
                        end=_text_offset_to_location(new_text, idx + len(find_query)),
                    )
            else:
                # Selection doesn't match — just find next occurrence
                cursor_row, cursor_col = self.editor.cursor_location
                lines = text.split("\n")
                cursor_offset = (
                    sum(len(lines[i]) + 1 for i in range(cursor_row)) + cursor_col
                )
                idx = _find_next(text, find_query, cursor_offset)
                if idx == -1:
                    self.notify(f"'{find_query}' not found", severity="warning")
                    return
                self.editor.selection = Selection(
                    start=_text_offset_to_location(text, idx),
                    end=_text_offset_to_location(text, idx + len(find_query)),
                )

        self.app.push_screen(ReplaceModalScreen(), do_replace)

    def action_change_language(self) -> None:
        """
        Open the Change Language modal and update the syntax highlighting language.
        """
        languages = sorted(set(self.LANGUAGE_EXTENSIONS.values()))

        def do_change(result: ChangeLanguageModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            self.language = result.language

        self.app.push_screen(
            ChangeLanguageModalScreen(
                languages=languages,
                current_language=self.language,
            ),
            do_change,
        )

    @on(Button.Pressed, "#language")
    def on_language_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_change_language()

    def action_focus(self) -> None:
        """
        Focus the editor.
        """
        self.editor.focus()

    @on(TextArea.Changed)
    def on_text_changed(self, event: TextArea.Changed):
        event.stop()

        # update the text when editor's text changes
        self.text = event.control.text

    @on(TextArea.SelectionChanged)
    def on_selection_changed(self, event: TextArea.SelectionChanged):
        event.stop()

        # update the cursor position in the footer
        self.footer.cursor_location = event.selection.end

    @property
    def editor(self) -> TextArea:
        return self.query_one(TextArea)

    @property
    def footer(self) -> CodeEditorFooter:
        return self.query_one(CodeEditorFooter)
