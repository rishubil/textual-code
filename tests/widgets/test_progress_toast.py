"""Tests for ProgressToast, ProgressToastRack, and ProgressToastModal."""

from __future__ import annotations

import asyncio

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Label
from textual.worker import Worker

from tests.conftest import wait_for_condition
from textual_code.modals.progress_toast import ProgressToastModal
from textual_code.widgets.progress_toast import (
    ProgressToast,
    ProgressToastRack,
)


class _ProgressApp(App):
    """Minimal app with ProgressToastRack for testing."""

    def compose(self) -> ComposeResult:
        yield Label("test")
        yield ProgressToastRack()

    def _make_controlled_worker(self, gate: asyncio.Event) -> Worker[None]:
        """Create a worker that blocks until gate is set."""

        async def _wait() -> None:
            await gate.wait()

        return self.run_worker(_wait(), exit_on_error=False)

    def show_progress(
        self,
        label: str,
        worker: Worker[None],
        *,
        delay: float = 0.01,
        group: str = "",
        poll_interval: float = 0.02,
        success_timeout: float = 0.5,
        error_timeout: float = 0.5,
        cancel_timeout: float = 0.5,
    ) -> ProgressToast:
        """Convenience wrapper for ProgressToastRack.show() with fast defaults."""
        return self.query_one(ProgressToastRack).show(
            label,
            worker,
            delay=delay,
            group=group,
            poll_interval=poll_interval,
            success_timeout=success_timeout,
            error_timeout=error_timeout,
            cancel_timeout=cancel_timeout,
        )


def _has_toast(app: _ProgressApp) -> bool:
    return len(app.query_one(ProgressToastRack).query(ProgressToast)) > 0


def _no_toast(app: _ProgressApp) -> bool:
    return len(app.query_one(ProgressToastRack).query(ProgressToast)) == 0


# ── Rack & Toast basics ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_progress_toast_rack_mounts():
    """ProgressToastRack can be mounted in an app."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        rack = app.query_one(ProgressToastRack)
        assert rack is not None


@pytest.mark.asyncio
async def test_progress_toast_compose():
    """ProgressToast renders a LoadingIndicator and a Label."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Testing...", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        toast = app.query_one(ProgressToastRack).query_one(ProgressToast)
        from textual_code.widgets.progress_toast import _ToastLoadingIndicator

        assert len(toast.query(_ToastLoadingIndicator)) == 1
        assert toast.query_one(Label).content == "Testing..."
        gate.set()


# ── Delay mechanism ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_toast_not_mounted_before_delay():
    """ProgressToast is not visible before the delay threshold."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Slow op", worker, delay=10.0)
        await pilot.wait_for_scheduled_animations()
        assert _no_toast(app)
        gate.set()


@pytest.mark.asyncio
async def test_toast_mounts_after_delay():
    """ProgressToast becomes visible after the delay threshold passes."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Working...", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        toasts = app.query_one(ProgressToastRack).query(ProgressToast)
        assert len(toasts) == 1
        assert toasts.first().query_one(Label).content == "Working..."
        gate.set()


@pytest.mark.asyncio
async def test_toast_skipped_when_worker_fast():
    """ProgressToast is never shown if the worker finishes before delay."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Quick op", worker, delay=0.3)
        gate.set()
        await asyncio.sleep(0.4)
        await pilot.wait_for_scheduled_animations()
        assert _no_toast(app)


# ── Terminal states ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_worker_success_shows_checkmark():
    """When worker succeeds, toast shows success indicator then auto-removes."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Upload", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        gate.set()
        await wait_for_condition(
            pilot,
            lambda: (
                "\u2713"
                in str(
                    app.query_one(ProgressToastRack)
                    .query_one(ProgressToast)
                    .query_one(Label)
                    .content
                )
            ),
        )
        await wait_for_condition(pilot, lambda: _no_toast(app))


@pytest.mark.asyncio
async def test_worker_error_shows_error():
    """When worker errors, toast shows error indicator."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()

        async def _failing() -> None:
            await gate.wait()
            raise ValueError("disk full")

        worker = app.run_worker(_failing(), exit_on_error=False)
        app.show_progress("Upload", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        gate.set()
        await wait_for_condition(
            pilot,
            lambda: (
                "\u2717"
                in str(
                    app.query_one(ProgressToastRack)
                    .query_one(ProgressToast)
                    .query_one(Label)
                    .content
                )
            ),
        )
        label_text = str(
            app.query_one(ProgressToastRack)
            .query_one(ProgressToast)
            .query_one(Label)
            .content
        )
        assert "disk full" in label_text


@pytest.mark.asyncio
async def test_worker_cancelled_shows_warning():
    """When worker is cancelled, toast shows warning indicator."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Upload", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        worker.cancel()
        await wait_for_condition(
            pilot,
            lambda: (
                "\u26a0"
                in str(
                    app.query_one(ProgressToastRack)
                    .query_one(ProgressToast)
                    .query_one(Label)
                    .content
                )
            ),
        )
        gate.set()


# ── Group dedup ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_group_dedup_replaces_previous():
    """A new toast with the same group replaces the previous one."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate1 = asyncio.Event()
        worker1 = app._make_controlled_worker(gate1)
        app.show_progress("First", worker1, group="ops")
        await wait_for_condition(pilot, lambda: _has_toast(app))

        gate2 = asyncio.Event()
        worker2 = app._make_controlled_worker(gate2)
        app.show_progress("Second", worker2, group="ops")
        await wait_for_condition(
            pilot,
            lambda: (
                "Second"
                in str(
                    app.query_one(ProgressToastRack)
                    .query(ProgressToast)
                    .first()
                    .query_one(Label)
                    .content
                )
            ),
        )
        toasts = list(app.query_one(ProgressToastRack).query(ProgressToast))
        assert len(toasts) == 1
        gate1.set()
        gate2.set()


# ── Modal interactions ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_click_opens_modal():
    """Clicking a ProgressToast pushes a ProgressToastModal screen."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Deleting...", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        toast = app.query_one(ProgressToastRack).query_one(ProgressToast)
        await pilot.click(toast)
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, ProgressToastModal)
        gate.set()


@pytest.mark.asyncio
async def test_modal_stop_cancels_worker():
    """Pressing Stop in the modal cancels the worker."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Deleting...", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        toast = app.query_one(ProgressToastRack).query_one(ProgressToast)
        await pilot.click(toast)
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#stop")
        await pilot.wait_for_scheduled_animations()
        assert worker.is_cancelled
        gate.set()


@pytest.mark.asyncio
async def test_modal_close_keeps_toast():
    """Closing the modal via Close button does not remove the toast."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Working...", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        await pilot.click(app.query_one(ProgressToast))
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#close")
        await pilot.wait_for_scheduled_animations()
        assert not isinstance(app.screen, ProgressToastModal)
        assert _has_toast(app)
        gate.set()


@pytest.mark.asyncio
async def test_modal_escape_keeps_toast():
    """Pressing Escape in the modal dismisses it but toast persists."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Working...", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        await pilot.click(app.query_one(ProgressToast))
        await pilot.wait_for_scheduled_animations()
        await pilot.press("escape")
        await pilot.wait_for_scheduled_animations()
        assert not isinstance(app.screen, ProgressToastModal)
        assert _has_toast(app)
        gate.set()


@pytest.mark.asyncio
async def test_modal_auto_closes_on_worker_finish():
    """Modal auto-dismisses when the worker finishes while modal is open."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Working...", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        await pilot.click(app.query_one(ProgressToast))
        await wait_for_condition(
            pilot, lambda: isinstance(app.screen, ProgressToastModal)
        )
        gate.set()
        await wait_for_condition(
            pilot, lambda: not isinstance(app.screen, ProgressToastModal)
        )


# ── Rack lifecycle ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rack_hides_when_empty():
    """ProgressToastRack display goes to False when last toast is removed."""
    app = _ProgressApp()
    async with app.run_test(size=(80, 24)) as pilot:
        gate = asyncio.Event()
        worker = app._make_controlled_worker(gate)
        app.show_progress("Work", worker)
        await wait_for_condition(pilot, lambda: _has_toast(app))
        rack = app.query_one(ProgressToastRack)
        assert rack.display is True
        gate.set()
        await wait_for_condition(pilot, lambda: rack.display is False)


# ── Real app integration ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_real_app_has_progress_toast_rack(tmp_path):
    """The full TextualCode app mounts a ProgressToastRack."""
    from tests.conftest import make_app

    app = make_app(tmp_path, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        rack = app.query_one(ProgressToastRack)
        assert rack is not None
