"""Modal dialog for a running ProgressToast.

Displays the operation label, current status, and Stop / Close buttons.
The modal does NOT self-dismiss — the owning ``ProgressToast`` dismisses
it via weakref when the worker reaches a terminal state.
"""

from __future__ import annotations

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, Label
from textual.worker import Worker, WorkerState


class ProgressToastModal(ModalScreen[None]):
    """Modal showing worker status with Stop and Close buttons."""

    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    def __init__(
        self,
        label: str,
        worker: Worker[Any],
        *,
        poll_interval: float = 0.25,
    ) -> None:
        super().__init__()
        self._label = label
        self._worker = worker
        self._poll_interval = poll_interval
        self._poll_timer: Timer | None = None
        self._status_label: Label | None = None
        self._last_state: WorkerState | None = None

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(self._label, id="title"),
            Label("Running\u2026", id="status"),
            Button("Stop", variant="warning", id="stop"),
            Button("Close", variant="default", id="close"),
            id="dialog",
        )

    def on_mount(self) -> None:
        self._status_label = self.query_one("#status", Label)
        self._poll_timer = self.set_interval(self._poll_interval, self._poll_status)

    def _poll_status(self) -> None:
        state = self._worker.state
        if state == self._last_state:
            return
        self._last_state = state
        assert self._status_label is not None
        if state == WorkerState.RUNNING or state == WorkerState.PENDING:
            self._status_label.update("Running\u2026")
        elif state == WorkerState.SUCCESS:
            self._status_label.update("\u2713 Completed")
            self._stop_polling()
        elif state == WorkerState.ERROR:
            err = str(self._worker.error) if self._worker.error else "Unknown error"
            self._status_label.update(f"\u2717 Error: {err}")
            self._stop_polling()
        elif state == WorkerState.CANCELLED:
            self._status_label.update("\u26a0 Cancelled")
            self._stop_polling()

    def _stop_polling(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None

    @on(Button.Pressed, "#stop")
    def _on_stop(self) -> None:
        self._worker.cancel()
        self.dismiss()

    @on(Button.Pressed, "#close")
    def action_close(self) -> None:
        self.dismiss()

    def on_unmount(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
