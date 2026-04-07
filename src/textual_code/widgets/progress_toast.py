"""Persistent progress toast connected to a Textual Worker.

Architecture::

    ProgressToastRack (Container, docked bottom, ``_toastrack`` layer)
        └─ ProgressToastHolder (alignment wrapper, delayed mount)
             └─ ProgressToast (Widget: LoadingIndicator + Label)
                   └─ click → push_screen(ProgressToastModal)
"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.events import Click
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Label, LoadingIndicator
from textual.worker import Worker, WorkerState

if TYPE_CHECKING:
    from textual.app import RenderResult

_MAX_ERROR_LEN = 80


class _ToastLoadingIndicator(LoadingIndicator, inherit_css=False):
    """LoadingIndicator that does not block input events.

    The base ``LoadingIndicator`` stops all ``InputEvent`` from bubbling,
    which prevents click events from reaching the parent ``ProgressToast``.
    """

    def _on_input_event(self, event: object) -> None:
        # Allow events to bubble to ProgressToast
        pass

    def render(self) -> RenderResult:
        """Render a compact spinner instead of 'Loading...'."""
        if self.app.animation_level == "none":
            return "\u25cf"  # ●
        return super().render()


class ProgressToast(Widget, inherit_css=False):
    """A persistent toast that tracks a Worker's lifecycle.

    Composes a ``LoadingIndicator`` and a ``Label``.  On terminal state the
    indicator is hidden and the label is updated with a status icon.
    """

    DEFAULT_CSS = """
    ProgressToast {
        width: 60;
        max-width: 50%;
        height: auto;
        margin-top: 1;
        padding: 1 1;
        background: $panel-lighten-1;
        layout: horizontal;
        visibility: visible;
    }

    ProgressToast _ToastLoadingIndicator {
        width: 2;
        height: 1;
        min-height: 1;
    }

    ProgressToast Label {
        width: 1fr;
        height: auto;
    }
    """

    def __init__(
        self,
        label: str,
        worker: Worker[Any],
        *,
        group: str = "",
        poll_interval: float = 0.25,
        success_timeout: float = 1.5,
        error_timeout: float = 3.0,
        cancel_timeout: float = 2.0,
    ) -> None:
        super().__init__()
        self._label_text = label
        self._worker = worker
        self._group = group
        self._poll_interval = poll_interval
        self._success_timeout = success_timeout
        self._error_timeout = error_timeout
        self._cancel_timeout = cancel_timeout
        self._poll_timer: Timer | None = None
        self._modal_ref: weakref.ref[Any] | None = None
        self._terminal = False

    def compose(self) -> ComposeResult:
        yield _ToastLoadingIndicator()
        yield Label(self._label_text)

    def on_mount(self) -> None:
        self._poll_timer = self.set_interval(self._poll_interval, self._poll_worker)
        self.app.log.info(
            "progress_toast [%s] %r: mounted", self._group, self._label_text
        )

    def _poll_worker(self) -> None:
        if not self.is_attached or self._terminal:
            return

        state = self._worker.state
        if state == WorkerState.SUCCESS:
            self._enter_terminal(f"\u2713 {self._label_text}", self._success_timeout)
        elif state == WorkerState.ERROR:
            err = str(self._worker.error) if self._worker.error else "Unknown error"
            if len(err) > _MAX_ERROR_LEN:
                err = err[:_MAX_ERROR_LEN] + "\u2026"
            self._enter_terminal(f"\u2717 {err}", self._error_timeout)
        elif state == WorkerState.CANCELLED:
            self._enter_terminal(f"\u26a0 {self._label_text}", self._cancel_timeout)

    def _enter_terminal(self, text: str, timeout: float) -> None:
        self._terminal = True
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
        self.app.log.info(
            "progress_toast [%s] %r: terminal → %s",
            self._group,
            self._label_text,
            text,
        )
        for indicator in self.query(_ToastLoadingIndicator):
            indicator.display = False
        self.query_one(Label).update(text)
        self._dismiss_modal()
        self.set_timer(timeout, self._dismiss)

    def _dismiss_modal(self) -> None:
        if self._modal_ref is None:
            return
        modal = self._modal_ref()
        if modal is not None and modal in self.app.screen_stack:
            modal.dismiss()
        self._modal_ref = None

    def _dismiss(self) -> None:
        if not self.is_attached:
            return
        self.app.log.info(
            "progress_toast [%s] %r: dismissed", self._group, self._label_text
        )
        holder = self.parent
        if isinstance(holder, ProgressToastHolder):
            holder.remove()
        else:
            self.remove()

    @on(Click)
    def _handle_click(self, event: Click) -> None:
        if self._terminal:
            return
        from textual_code.modals.progress_toast import ProgressToastModal

        modal = ProgressToastModal(
            self._label_text,
            self._worker,
            poll_interval=self._poll_interval,
        )
        self._modal_ref = weakref.ref(modal)
        self.app.push_screen(modal)


class ProgressToastHolder(Container, inherit_css=False):
    """Alignment wrapper that delays mounting the toast."""

    DEFAULT_CSS = """
    ProgressToastHolder {
        align-horizontal: right;
        width: 1fr;
        height: auto;
        visibility: hidden;
    }
    """

    def __init__(self, toast: ProgressToast, delay: float) -> None:
        super().__init__()
        self._toast = toast
        self._delay = delay
        self._delay_timer: Timer | None = None

    def on_mount(self) -> None:
        self._delay_timer = self.set_timer(self._delay, self._show_toast)

    def _show_toast(self) -> None:
        if not self.is_attached:
            return
        if self._toast._worker.is_finished:
            # Worker finished during delay — skip mounting, clean up
            self.remove()
            return
        self.mount(self._toast)

    def on_unmount(self) -> None:
        # Stop pending delay timer
        if self._delay_timer is not None:
            self._delay_timer.stop()
            self._delay_timer = None
        # Check if rack should hide (deferred so DOM is updated first)
        parent = self.parent
        if isinstance(parent, ProgressToastRack):
            parent.call_later(parent._check_empty)


class ProgressToastRack(Container, inherit_css=False):
    """Container for progress toasts. Shares ``_toastrack`` layer with
    Textual's built-in ``ToastRack``.
    """

    DEFAULT_CSS = """
    ProgressToastRack {
        display: none;
        layer: _toastrack;
        width: 1fr;
        height: auto;
        dock: bottom;
        align: right bottom;
        visibility: hidden;
        layout: vertical;
        overflow-y: scroll;
        margin-bottom: 1;
    }
    """

    def show(
        self,
        label: str,
        worker: Worker[Any],
        *,
        delay: float = 0.5,
        group: str = "",
        poll_interval: float = 0.25,
        success_timeout: float = 1.5,
        error_timeout: float = 3.0,
        cancel_timeout: float = 2.0,
    ) -> ProgressToast:
        """Show a progress toast connected to *worker*.

        Args:
            label: Human-readable description of the operation.
            worker: The worker to track.
            delay: Seconds to wait before showing the toast.
            group: Dedup key — a new toast with the same non-empty group
                replaces any existing toast in that group.
            poll_interval: How often to poll the worker state (seconds).
            success_timeout: Seconds to show success icon before dismiss.
            error_timeout: Seconds to show error icon before dismiss.
            cancel_timeout: Seconds to show cancel icon before dismiss.

        Returns:
            The ``ProgressToast`` instance (may not be mounted yet).
        """
        self.app.log.info("progress_toast [%s] %r: created", group, label)
        # Group dedup
        if group:
            for holder in list(self.query(ProgressToastHolder)):
                if holder._toast._group == group:
                    holder.remove()

        toast = ProgressToast(
            label=label,
            worker=worker,
            group=group,
            poll_interval=poll_interval,
            success_timeout=success_timeout,
            error_timeout=error_timeout,
            cancel_timeout=cancel_timeout,
        )
        holder = ProgressToastHolder(toast, delay)
        self.mount(holder)
        self.display = True
        return toast

    def _check_empty(self) -> None:
        """Hide the rack if no holders remain."""
        if len(self.query(ProgressToastHolder)) == 0:
            self.display = False
