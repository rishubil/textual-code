from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
)


@dataclass
class SidebarResizeModalResult:
    """
    The result of the Sidebar Resize modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The raw user input string, or None if cancelled.
    value: str | None


class SidebarResizeModalScreen(ModalScreen[SidebarResizeModalResult]):
    """
    Modal dialog for resizing the sidebar.
    Accepts: absolute ("30"), relative ("+5" or "-3"), or percentage ("30%").
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Resize Sidebar", id="title"),
            Input(placeholder="e.g. 30  or  +5  or  30%", id="value"),
            Button("Resize", variant="primary", id="submit"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Input.Submitted, "#value")
    @on(Button.Pressed, "#submit")
    def on_submit(self) -> None:
        self.dismiss(
            SidebarResizeModalResult(
                is_cancelled=False, value=self.query_one(Input).value
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(SidebarResizeModalResult(is_cancelled=True, value=None))


@dataclass
class SplitResizeModalResult:
    """
    The result of the Split Resize modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The raw user input string, or None if cancelled.
    value: str | None


class SplitResizeModalScreen(ModalScreen[SplitResizeModalResult]):
    """
    Modal dialog for resizing the split view left panel.
    Accepts: absolute ("50"), relative ("+10" or "-5"), or percentage ("40%").
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Resize Split", id="title"),
            Input(placeholder="e.g. 50  or  +10  or  40%", id="value"),
            Button("Resize", variant="primary", id="submit"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Input.Submitted, "#value")
    @on(Button.Pressed, "#submit")
    def on_submit(self) -> None:
        self.dismiss(
            SplitResizeModalResult(
                is_cancelled=False, value=self.query_one(Input).value
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(SplitResizeModalResult(is_cancelled=True, value=None))
