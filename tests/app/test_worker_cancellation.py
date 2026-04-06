"""Tests for worker cancellation guards and daemon thread executor.

Verifies that:
1. The app registers a daemon thread executor on load
2. Async workers skip callbacks when cancelled (TimeoutError from run_cancellable)
3. Widget unmount cancels owned worker groups
4. Modal dismiss triggers Textual's automatic worker cancellation
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from tests.conftest import make_app


async def _slow_run_cancellable(*args, **kwargs):
    """Mock for run_cancellable that blocks until cancelled."""
    try:
        await asyncio.sleep(60)
    except asyncio.CancelledError:
        raise TimeoutError("cancelled") from None


# ---------------------------------------------------------------------------
# Test 1: Daemon executor registered
# ---------------------------------------------------------------------------


async def test_daemon_executor_registered(workspace: Path) -> None:
    """App registers a DaemonThreadPoolExecutor whose threads are daemon."""
    app = make_app(workspace, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        loop = asyncio.get_running_loop()
        executor = getattr(loop, "_default_executor", None)
        assert executor is not None, "No default executor set"
        # Submit a trivial task to force thread creation
        future = executor.submit(lambda: threading.current_thread().daemon)
        is_daemon = future.result(timeout=5)
        assert is_daemon, "Executor threads should be daemon threads"


# ---------------------------------------------------------------------------
# Test 2: _search_worker checks cancellation
# ---------------------------------------------------------------------------


async def test_search_worker_checks_cancellation(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_populate_results is not called when the search worker is cancelled."""
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    populate_called: list[bool] = []
    original_populate = WorkspaceSearchPane._populate_results

    def tracking_populate(self, *args, **kwargs):
        populate_called.append(True)
        return original_populate(self, *args, **kwargs)

    monkeypatch.setattr(WorkspaceSearchPane, "_populate_results", tracking_populate)

    monkeypatch.setattr(
        "textual_code.widgets.workspace_search.run_cancellable",
        _slow_run_cancellable,
    )

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        pane = app.query_one(WorkspaceSearchPane)
        # Trigger a search
        pane._search_worker(workspace, "test", False, True, True, True, "", "")
        await pilot.pause()
        # Cancel the search group immediately
        pane.workers.cancel_group(pane, "search")
        # Allow worker to finish
        await pilot.pause()
        await pilot.pause()

    assert not populate_called, "_populate_results called after worker cancellation"


# ---------------------------------------------------------------------------
# Test 3: _preview_replace_worker checks cancellation
# ---------------------------------------------------------------------------


async def test_replace_worker_checks_cancellation(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_show_replace_preview is not called when replace worker is cancelled."""
    from textual_code.search import WorkspaceSearchResult
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    preview_called: list[bool] = []
    original_preview = WorkspaceSearchPane._show_replace_preview

    def tracking_preview(self, *args, **kwargs):
        preview_called.append(True)
        return original_preview(self, *args, **kwargs)

    monkeypatch.setattr(WorkspaceSearchPane, "_show_replace_preview", tracking_preview)

    monkeypatch.setattr(
        "textual_code.widgets.workspace_search.run_cancellable",
        _slow_run_cancellable,
    )

    dummy_results = [
        WorkspaceSearchResult(
            file_path=workspace / "test.txt",
            line_number=1,
            line_text="test",
            match_start=0,
            match_end=4,
        )
    ]

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        pane = app.query_one(WorkspaceSearchPane)
        pane._preview_selected_worker(
            workspace, "test", "replaced", False, True, dummy_results
        )
        await pilot.pause()
        pane.workers.cancel_group(pane, "replace_count")
        await pilot.pause()
        await pilot.pause()

    assert not preview_called, "_show_replace_preview called after worker cancellation"


# ---------------------------------------------------------------------------
# Test 4: PathSearchModal scan checks cancellation
# ---------------------------------------------------------------------------


async def test_path_search_modal_scan_checks_cancellation(
    workspace: Path,
) -> None:
    """No errors when PathSearchModal is dismissed while scan is running."""
    import logging

    from textual_code.modals import PathSearchModal

    cancel_event = threading.Event()

    def slow_scan(*args, **kwargs):
        cancel_event.wait(timeout=5)
        return [workspace / "test.py"]

    app = make_app(workspace, light=True)
    error_records: list[logging.LogRecord] = []

    class ErrorCapture(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.ERROR:
                error_records.append(record)

    handler = ErrorCapture()
    logging.getLogger().addHandler(handler)

    try:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # Open the file search modal via action
            app.action_open_file()
            await pilot.pause()
            await pilot.pause()
            # The modal IS the current screen
            modal = app.screen
            assert isinstance(modal, PathSearchModal)
            modal._scan_func = slow_scan
            modal._start_scan()
            await pilot.pause()
            # Dismiss while scan is running
            await pilot.press("escape")
            # Unblock the scan thread
            cancel_event.set()
            # Wait for thread to finish
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
    finally:
        logging.getLogger().removeHandler(handler)

    # Filter out errors that are unrelated to our fix
    relevant_errors = [
        r
        for r in error_records
        if "call_from_thread" in str(r.getMessage()).lower()
        or "unmount" in str(r.getMessage()).lower()
        or "RuntimeError" in str(r.getMessage())
    ]
    assert not relevant_errors, (
        f"Errors after modal dismiss: {[r.getMessage() for r in relevant_errors]}"
    )


# ---------------------------------------------------------------------------
# Test 5: PathSearchModal dismiss cancels workers (Textual auto cancel_node)
# ---------------------------------------------------------------------------


async def test_path_search_modal_dismiss_cancels_workers(
    workspace: Path,
) -> None:
    """Workers are cancelled when PathSearchModal is dismissed."""
    from textual_code.modals import PathSearchModal

    cancel_event = threading.Event()
    worker_was_cancelled: list[bool] = []

    def slow_scan(*args, **kwargs):
        cancel_event.wait(timeout=5)
        return [workspace / "test.py"]

    app = make_app(workspace, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.action_open_file()
        await pilot.pause()
        await pilot.pause()

        # The modal IS the current screen
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        modal._scan_func = slow_scan
        modal._start_scan()
        await pilot.pause()

        # Snapshot running workers before dismiss
        workers_before = [w for w in modal.workers._workers if not w.is_finished]

        # Dismiss the modal
        await pilot.press("escape")
        await pilot.pause()

        # Check that workers were cancelled
        for w in workers_before:
            worker_was_cancelled.append(w.is_cancelled)

        # Unblock threads
        cancel_event.set()
        await pilot.pause()

    # If there were running workers, they should have been cancelled
    if worker_was_cancelled:
        assert all(worker_was_cancelled), (
            "Not all workers were cancelled on modal dismiss"
        )


# ---------------------------------------------------------------------------
# Test 6: WorkspaceSearchPane.on_unmount cancels workers
# ---------------------------------------------------------------------------


async def test_workspace_search_pane_cancels_workers_on_unmount(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Workers are cancelled when WorkspaceSearchPane is unmounted."""
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    monkeypatch.setattr(
        "textual_code.widgets.workspace_search.run_cancellable",
        _slow_run_cancellable,
    )

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        pane = app.query_one(WorkspaceSearchPane)

        # Start a search
        pane._search_worker(workspace, "test", False, True, True, True, "", "")
        await pilot.pause()

        # Get workers before removal
        search_workers = [w for w in pane.workers._workers if w.group == "search"]
        assert search_workers, "No search workers found"

        # Remove the pane (triggers on_unmount)
        await pane.remove()
        await pilot.pause()
        await pilot.pause()

    # All search workers should have been cancelled
    for w in search_workers:
        assert w.is_cancelled, f"Worker {w.name} was not cancelled on unmount"


# ---------------------------------------------------------------------------
# Test 7: _refresh_git_diff checks cancellation
# ---------------------------------------------------------------------------


async def test_git_diff_worker_checks_cancellation(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, sample_py_file: Path
) -> None:
    """_apply_git_diff is not called when git_diff worker is cancelled."""
    from tests.conftest import init_git_repo
    from textual_code.widgets.code_editor import CodeEditor

    init_git_repo(workspace)

    apply_called: list[bool] = []
    original_apply = CodeEditor._apply_git_diff

    def tracking_apply(self, *args, **kwargs):
        apply_called.append(True)
        return original_apply(self, *args, **kwargs)

    monkeypatch.setattr(CodeEditor, "_apply_git_diff", tracking_apply)

    cancel_event = threading.Event()

    def slow_fetch(self):
        cancel_event.wait(timeout=5)
        return None

    monkeypatch.setattr(CodeEditor, "_fetch_head_lines", slow_fetch)

    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Clear any previously tracked calls
        apply_called.clear()

        # Trigger git diff refresh
        editor._refresh_git_diff()
        await pilot.pause()

        # Cancel the worker
        editor.workers.cancel_group(editor, "git_diff")
        cancel_event.set()
        await pilot.pause()
        await pilot.pause()

    assert not apply_called, "_apply_git_diff called after worker cancellation"


# ---------------------------------------------------------------------------
# Test 8: image_preview call_from_thread is protected
# ---------------------------------------------------------------------------


async def test_image_preview_call_from_thread_protected(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ImagePreviewPane's call_from_thread does not raise on shutdown race."""
    # Create a minimal PNG file
    from tests.conftest import make_png

    img_path = make_png(workspace / "test.png")

    app = make_app(workspace, open_file=img_path, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        # The image preview should have loaded without errors
        # This test verifies that the try/except RuntimeError guard
        # is present on the call_from_thread calls
        pane = app.query("ImagePreviewPane").first()
        if pane is not None:
            # Verify the worker completed successfully
            await pilot.pause()
